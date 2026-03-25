"""
WasteIQ — Oracle Fusion Cloud Procurement Integration.

Pushes WasteIQ-optimized material quantities as Purchase Requisitions
directly into Oracle Fusion via REST API.

Oracle Fusion REST API docs:
  https://docs.oracle.com/en/cloud/saas/procurement/24b/farpr/

Authentication: OAuth 2.0 Client Credentials flow
Endpoint: POST /fscmRestApi/resources/11.13.18.05/purchaseRequisitions
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.db_models import User, Project, MaterialLineItem
from app.config import settings

router = APIRouter(prefix="/oracle", tags=["oracle"])

# Maps WasteIQ material types to Oracle item categories (customize per deployment)
MATERIAL_CATEGORY_MAP = {
    "concrete":    "Construction.Concrete",
    "steel_rebar": "Construction.Steel",
    "lumber":      "Construction.Lumber",
    "drywall":     "Construction.Drywall",
    "tiles":       "Construction.Tiles",
    "pipe":        "Construction.Plumbing",
    "insulation":  "Construction.Insulation",
    "brick":       "Construction.Masonry",
    "glass":       "Construction.Glass",
    "other":       "Construction.General",
}

UNIT_OF_MEASURE_MAP = {
    "m3": "M3",
    "kg": "KG",
    "pcs": "EA",
    "sheets": "EA",
    "sqm": "M2",
    "m": "M",
    "lm": "M",
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class OraclePushRequest(BaseModel):
    project_id: str
    requester_name: Optional[str] = None       # Oracle employee name
    deliver_to_location: Optional[str] = None  # Oracle location code
    need_by_date: Optional[str] = None         # ISO date string

class OraclePushResult(BaseModel):
    success: bool
    requisition_number: Optional[str]
    requisition_id: Optional[str]
    lines_created: int
    total_amount: Optional[float]
    oracle_url: Optional[str]
    error: Optional[str]
    dry_run: bool  # True when Oracle credentials not configured — shows payload only
    payload_preview: Optional[dict]


# ── Oracle OAuth2 helper ──────────────────────────────────────────────────────

_token_cache: dict = {}

async def _get_oracle_token() -> str:
    """Fetch OAuth2 access token from Oracle Identity Cloud, with caching."""
    now = datetime.utcnow()
    cached = _token_cache.get("token")
    expires = _token_cache.get("expires", now)

    if cached and now < expires:
        return cached

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            settings.oracle_token_url,
            data={
                "grant_type": "client_credentials",
                "scope": "https://procurement.us2.oraclecloud.com/",
            },
            auth=(settings.oracle_client_id, settings.oracle_client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["access_token"]
        _token_cache["token"] = token
        _token_cache["expires"] = now + timedelta(seconds=data.get("expires_in", 3600) - 60)
        return token


# ── Payload builder ───────────────────────────────────────────────────────────

def _build_requisition_payload(
    project: Project,
    materials: List[MaterialLineItem],
    requester_name: str,
    deliver_to_location: str,
    need_by_date: str,
) -> dict:
    """
    Build Oracle Fusion Purchase Requisition payload.
    Maps WasteIQ recommended quantities to Oracle line items.
    """
    lines = []
    for i, mat in enumerate(materials, start=1):
        if not mat.prediction:
            continue

        rec_qty = mat.prediction.recommended_order_qty
        category = MATERIAL_CATEGORY_MAP.get(mat.material_type.value, "Construction.General")
        uom = UNIT_OF_MEASURE_MAP.get(mat.unit.lower(), mat.unit.upper())
        mat_name = mat.material_type.value.replace("_", " ").title()

        line = {
            "LineNumber": i,
            "LineTypeCode": "Goods",
            "Description": f"{mat_name} — WasteIQ optimized qty for {project.name}",
            "CategoryName": category,
            "Quantity": rec_qty,
            "UOMCode": uom,
            "NeedByDate": need_by_date,
            "DeliverToLocationCode": deliver_to_location,
            "WasteIQNote": (
                f"AI-recommended: {rec_qty} {mat.unit} "
                f"(predicted waste: {mat.prediction.predicted_waste_pct:.1f}%, "
                f"vs 15% flat buffer: {round(mat.estimated_quantity * 1.15, 2)} {mat.unit})"
            ),
        }

        if mat.unit_price:
            line["UnitPrice"] = mat.unit_price
            line["Amount"] = round(rec_qty * mat.unit_price, 2)

        lines.append(line)

    return {
        "RequisitioningBUName": settings.oracle_bu_id or "Construction Business Unit",
        "Description": f"WasteIQ Purchase Requisition — {project.name}",
        "RequesterName": requester_name,
        "SourceApplicationCode": "WasteIQ",
        "RequisitionLines": lines,
    }


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/push-requisition", response_model=OraclePushResult)
async def push_to_oracle(
    payload: OraclePushRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Push WasteIQ-optimized material quantities to Oracle Fusion
    as a Purchase Requisition.

    If Oracle credentials are not configured, returns a dry-run preview
    of the exact payload that would be sent.
    """
    project = (
        db.query(Project)
        .options(selectinload(Project.materials).selectinload(MaterialLineItem.prediction))
        .filter(Project.id == payload.project_id, Project.company_id == current_user.company_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    materials_with_pred = [m for m in project.materials if m.prediction]
    if not materials_with_pred:
        raise HTTPException(status_code=400, detail="Generate predictions first before pushing to Oracle")

    need_by = payload.need_by_date or (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d")
    requester = payload.requester_name or current_user.full_name or "WasteIQ User"
    location = payload.deliver_to_location or project.location or "Main Site"

    req_payload = _build_requisition_payload(
        project, materials_with_pred, requester, location, need_by
    )

    # ── Dry run if Oracle not configured ──────────────────────────────────────
    oracle_configured = all([
        settings.oracle_host,
        settings.oracle_client_id,
        settings.oracle_client_secret,
        settings.oracle_token_url,
    ])

    if not oracle_configured:
        total = sum(
            (m.prediction.recommended_order_qty * (m.unit_price or 0))
            for m in materials_with_pred
        )
        return OraclePushResult(
            success=True,
            requisition_number=None,
            requisition_id=None,
            lines_created=len(req_payload["RequisitionLines"]),
            total_amount=round(total, 2) if total else None,
            oracle_url=None,
            error=None,
            dry_run=True,
            payload_preview=req_payload,
        )

    # ── Live Oracle API call ──────────────────────────────────────────────────
    try:
        token = await _get_oracle_token()
        url = f"https://{settings.oracle_host}/fscmRestApi/resources/11.13.18.05/purchaseRequisitions"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                url,
                json=req_payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        req_number = data.get("RequisitionNumber") or data.get("requisitionNumber")
        req_id = data.get("RequisitionHeaderId") or data.get("requisitionHeaderId")

        return OraclePushResult(
            success=True,
            requisition_number=req_number,
            requisition_id=str(req_id) if req_id else None,
            lines_created=len(req_payload["RequisitionLines"]),
            total_amount=data.get("TotalAmount"),
            oracle_url=f"https://{settings.oracle_host}/fscmUI/faces/FuseWelcome",
            error=None,
            dry_run=False,
            payload_preview=None,
        )

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Oracle API error {e.response.status_code}: {e.response.text[:300]}"
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Oracle connection failed: {str(e)}")
