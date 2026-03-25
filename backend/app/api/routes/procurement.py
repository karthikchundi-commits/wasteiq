"""
WasteIQ Procurement Middleware.

ERP-agnostic staging layer between WasteIQ predictions and any ERP system.

Flow:
  1. POST /procurement/stage/{project_id}  — create staging requisition from predictions
  2. GET  /procurement/{project_id}        — view staged grid (items, qty, need_by_date)
  3. PUT  /procurement/lines/{line_id}     — edit a line before push (qty, date, location)
  4. POST /procurement/push/{req_id}       — push to configured ERP/middleware endpoint
  5. GET  /procurement/export/{req_id}     — export as JSON or CSV

Supports: Oracle Fusion, SAP, MS Dynamics, or any custom REST/webhook endpoint.
"""
import csv
import io
import json
import httpx
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, selectinload
from pydantic import BaseModel

from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.db_models import (
    User, Project, MaterialLineItem,
    ProcurementRequisition, ProcurementLine,
    RequisitionStatus, ERPType
)

router = APIRouter(prefix="/procurement", tags=["procurement"])

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

UOM_MAP = {
    "m3": "M3", "kg": "KG", "pcs": "EA", "sheets": "EA",
    "sqm": "M2", "m": "M", "lm": "M",
}


# ── Schemas ───────────────────────────────────────────────────────────────────

class ProcurementLineOut(BaseModel):
    id: str
    line_number: int
    item_description: str
    item_category: Optional[str]
    material_type: str
    ai_recommended_qty: Optional[float]
    requested_qty: float
    unit_of_measure: Optional[str]
    unit_price: Optional[float]
    total_amount: Optional[float]
    need_by_date: Optional[datetime]
    deliver_to_location: Optional[str]
    requester_name: Optional[str]
    erp_item_code: Optional[str]
    flat_buffer_qty: Optional[float]
    savings_qty: Optional[float]
    savings_amount: Optional[float]

    class Config:
        from_attributes = True


class ProcurementRequisitionOut(BaseModel):
    id: str
    project_id: str
    status: str
    erp_type: Optional[str]
    erp_requisition_id: Optional[str]
    erp_requisition_number: Optional[str]
    push_url: Optional[str]
    created_at: datetime
    pushed_at: Optional[datetime]
    notes: Optional[str]
    lines: List[ProcurementLineOut]

    class Config:
        from_attributes = True


class StageRequest(BaseModel):
    erp_type: Optional[ERPType] = None
    push_url: Optional[str] = None
    default_need_by_days: int = 14       # days from today
    deliver_to_location: Optional[str] = None
    requester_name: Optional[str] = None
    notes: Optional[str] = None


class UpdateLineRequest(BaseModel):
    requested_qty: Optional[float] = None
    need_by_date: Optional[datetime] = None
    deliver_to_location: Optional[str] = None
    requester_name: Optional[str] = None
    erp_item_code: Optional[str] = None
    unit_price: Optional[float] = None


class PushRequest(BaseModel):
    push_url: Optional[str] = None   # override stored URL
    erp_type: Optional[ERPType] = None
    auth_header: Optional[str] = None  # e.g. "Bearer <token>" or "Basic <b64>"


class PushResult(BaseModel):
    success: bool
    requisition_id: str
    erp_requisition_id: Optional[str]
    erp_requisition_number: Optional[str]
    lines_pushed: int
    total_amount: Optional[float]
    erp_response: Optional[dict]
    error: Optional[str]
    dry_run: bool
    payload: Optional[dict]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_middleware_payload(req: ProcurementRequisition, project: Project) -> dict:
    """
    Standard WasteIQ middleware payload — ERP-agnostic JSON.
    Middleware/integration layer maps this to target ERP format.
    """
    return {
        "source": "WasteIQ",
        "version": "1.0",
        "requisition": {
            "id": req.id,
            "project_id": project.id,
            "project_name": project.name,
            "project_type": project.type.value,
            "location": project.location,
            "erp_type": req.erp_type.value if req.erp_type else "custom",
            "created_at": req.created_at.isoformat(),
            "notes": req.notes,
        },
        "lines": [
            {
                "line_number": line.line_number,
                "item_description": line.item_description,
                "item_category": line.item_category,
                "material_type": line.material_type,
                "erp_item_code": line.erp_item_code,
                "requested_qty": line.requested_qty,
                "ai_recommended_qty": line.ai_recommended_qty,
                "unit_of_measure": line.unit_of_measure,
                "unit_price": line.unit_price,
                "total_amount": line.total_amount,
                "need_by_date": line.need_by_date.strftime("%Y-%m-%d") if line.need_by_date else None,
                "deliver_to_location": line.deliver_to_location,
                "requester_name": line.requester_name,
                "wasteiq_savings": {
                    "flat_buffer_qty": line.flat_buffer_qty,
                    "savings_qty": line.savings_qty,
                    "savings_amount": line.savings_amount,
                },
            }
            for line in req.lines
        ],
        "summary": {
            "total_lines": len(req.lines),
            "total_requested_qty_by_material": {
                line.material_type: line.requested_qty for line in req.lines
            },
            "total_amount": sum(l.total_amount or 0 for l in req.lines),
            "total_savings_vs_flat_buffer": sum(l.savings_amount or 0 for l in req.lines),
        },
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/stage/{project_id}", response_model=ProcurementRequisitionOut)
def stage_requisition(
    project_id: str,
    body: StageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a procurement staging requisition from WasteIQ predictions.
    Populates the editable grid with AI-recommended quantities and default dates.
    """
    project = (
        db.query(Project)
        .options(selectinload(Project.materials).selectinload(MaterialLineItem.prediction))
        .filter(Project.id == project_id, Project.company_id == current_user.company_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    materials = [m for m in project.materials if m.prediction]
    if not materials:
        raise HTTPException(status_code=400, detail="Generate predictions first")

    # Delete any existing draft for this project
    existing = db.query(ProcurementRequisition).filter(
        ProcurementRequisition.project_id == project_id,
        ProcurementRequisition.status == RequisitionStatus.draft,
    ).first()
    if existing:
        db.delete(existing)
        db.flush()

    default_need_by = datetime.utcnow() + timedelta(days=body.default_need_by_days)

    req = ProcurementRequisition(
        project_id=project.id,
        company_id=current_user.company_id,
        status=RequisitionStatus.draft,
        erp_type=body.erp_type,
        push_url=body.push_url,
        notes=body.notes,
    )
    db.add(req)
    db.flush()

    for i, mat in enumerate(materials, start=1):
        pred = mat.prediction
        rec_qty = pred.recommended_order_qty
        flat_qty = round(mat.estimated_quantity * 1.15, 2)
        savings_qty = round(flat_qty - rec_qty, 2)
        savings_amt = round(savings_qty * mat.unit_price, 2) if mat.unit_price else None
        total = round(rec_qty * mat.unit_price, 2) if mat.unit_price else None
        uom = UOM_MAP.get(mat.unit.lower(), mat.unit.upper())
        mat_name = mat.material_type.value.replace("_", " ").title()

        line = ProcurementLine(
            requisition_id=req.id,
            material_line_item_id=mat.id,
            line_number=i,
            item_description=f"{mat_name} — {project.name}",
            item_category=MATERIAL_CATEGORY_MAP.get(mat.material_type.value, "Construction.General"),
            material_type=mat.material_type.value,
            ai_recommended_qty=rec_qty,
            requested_qty=rec_qty,       # user can edit this
            unit_of_measure=uom,
            unit_price=mat.unit_price,
            total_amount=total,
            need_by_date=default_need_by,
            deliver_to_location=body.deliver_to_location or project.location,
            requester_name=body.requester_name or current_user.full_name,
            flat_buffer_qty=flat_qty,
            savings_qty=savings_qty,
            savings_amount=savings_amt,
        )
        db.add(line)

    db.commit()
    db.refresh(req)
    return req


@router.get("/{project_id}", response_model=ProcurementRequisitionOut)
def get_requisition(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the current procurement staging requisition for a project."""
    req = (
        db.query(ProcurementRequisition)
        .options(selectinload(ProcurementRequisition.lines))
        .filter(
            ProcurementRequisition.project_id == project_id,
            ProcurementRequisition.company_id == current_user.company_id,
        )
        .order_by(ProcurementRequisition.created_at.desc())
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="No requisition found — stage one first")
    return req


@router.put("/lines/{line_id}", response_model=ProcurementLineOut)
def update_line(
    line_id: str,
    body: UpdateLineRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit a procurement line — adjust quantity, need-by date, location, item code."""
    line = (
        db.query(ProcurementLine)
        .join(ProcurementRequisition)
        .filter(
            ProcurementLine.id == line_id,
            ProcurementRequisition.company_id == current_user.company_id,
        )
        .first()
    )
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")

    if body.requested_qty is not None:
        line.requested_qty = body.requested_qty
        if line.unit_price:
            line.total_amount = round(body.requested_qty * line.unit_price, 2)
    if body.need_by_date is not None:
        line.need_by_date = body.need_by_date
    if body.deliver_to_location is not None:
        line.deliver_to_location = body.deliver_to_location
    if body.requester_name is not None:
        line.requester_name = body.requester_name
    if body.erp_item_code is not None:
        line.erp_item_code = body.erp_item_code
    if body.unit_price is not None:
        line.unit_price = body.unit_price
        line.total_amount = round(line.requested_qty * body.unit_price, 2)

    # Mark requisition as reviewed if it was draft
    req = line.requisition
    if req and req.status == RequisitionStatus.draft:
        req.status = RequisitionStatus.reviewed

    db.commit()
    db.refresh(line)
    return line


@router.post("/push/{requisition_id}", response_model=PushResult)
async def push_to_erp(
    requisition_id: str,
    body: PushRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Push the staged requisition to the configured ERP/middleware endpoint.

    Sends the WasteIQ standard JSON payload to the push_url via POST.
    If no push_url is configured, returns a dry-run with the full payload.
    """
    req = (
        db.query(ProcurementRequisition)
        .options(selectinload(ProcurementRequisition.lines))
        .filter(
            ProcurementRequisition.id == requisition_id,
            ProcurementRequisition.company_id == current_user.company_id,
        )
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Requisition not found")

    project = db.query(Project).filter(Project.id == req.project_id).first()
    payload = _build_middleware_payload(req, project)

    push_url = body.push_url or req.push_url
    total_amount = sum(l.total_amount or 0 for l in req.lines)

    # ── Dry run if no endpoint configured ─────────────────────────────────────
    if not push_url:
        return PushResult(
            success=True,
            requisition_id=req.id,
            erp_requisition_id=None,
            erp_requisition_number=None,
            lines_pushed=len(req.lines),
            total_amount=round(total_amount, 2),
            erp_response=None,
            error=None,
            dry_run=True,
            payload=payload,
        )

    # ── Live push ──────────────────────────────────────────────────────────────
    headers = {"Content-Type": "application/json", "X-Source": "WasteIQ"}
    if body.auth_header:
        headers["Authorization"] = body.auth_header

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(push_url, json=payload, headers=headers)
            resp.raise_for_status()
            erp_data = resp.json() if resp.text else {}

        erp_id = erp_data.get("id") or erp_data.get("requisitionId") or erp_data.get("RequisitionHeaderId")
        erp_num = erp_data.get("number") or erp_data.get("requisitionNumber") or erp_data.get("RequisitionNumber")

        req.status = RequisitionStatus.pushed
        req.push_url = push_url
        req.erp_requisition_id = str(erp_id) if erp_id else None
        req.erp_requisition_number = str(erp_num) if erp_num else None
        req.push_response = erp_data
        req.pushed_at = datetime.utcnow()
        db.commit()

        return PushResult(
            success=True,
            requisition_id=req.id,
            erp_requisition_id=req.erp_requisition_id,
            erp_requisition_number=req.erp_requisition_number,
            lines_pushed=len(req.lines),
            total_amount=round(total_amount, 2),
            erp_response=erp_data,
            error=None,
            dry_run=False,
            payload=None,
        )

    except httpx.HTTPStatusError as e:
        req.status = RequisitionStatus.failed
        db.commit()
        raise HTTPException(status_code=502, detail=f"ERP endpoint error {e.response.status_code}: {e.response.text[:300]}")
    except Exception as e:
        req.status = RequisitionStatus.failed
        db.commit()
        raise HTTPException(status_code=502, detail=f"Push failed: {str(e)}")


@router.get("/export/{requisition_id}")
def export_requisition(
    requisition_id: str,
    format: str = Query("json", enum=["json", "csv"]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export the requisition as JSON or CSV for manual upload to any ERP."""
    req = (
        db.query(ProcurementRequisition)
        .options(selectinload(ProcurementRequisition.lines))
        .filter(
            ProcurementRequisition.id == requisition_id,
            ProcurementRequisition.company_id == current_user.company_id,
        )
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Requisition not found")

    project = db.query(Project).filter(Project.id == req.project_id).first()

    if format == "json":
        payload = _build_middleware_payload(req, project)
        content = json.dumps(payload, indent=2, default=str)
        return StreamingResponse(
            io.StringIO(content),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=wasteiq-requisition-{req.id[:8]}.json"},
        )

    # CSV export
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Line#", "Item Description", "Category", "Material Type",
        "ERP Item Code", "Requested Qty", "AI Recommended Qty",
        "Unit", "Unit Price", "Total Amount",
        "Need By Date", "Deliver To", "Requester",
        "Flat Buffer Qty", "Savings Qty", "Savings Amount ($)",
    ])
    for line in req.lines:
        writer.writerow([
            line.line_number, line.item_description, line.item_category,
            line.material_type, line.erp_item_code or "",
            line.requested_qty, line.ai_recommended_qty,
            line.unit_of_measure, line.unit_price or "", line.total_amount or "",
            line.need_by_date.strftime("%Y-%m-%d") if line.need_by_date else "",
            line.deliver_to_location or "", line.requester_name or "",
            line.flat_buffer_qty or "", line.savings_qty or "", line.savings_amount or "",
        ])
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=wasteiq-requisition-{req.id[:8]}.csv"},
    )
