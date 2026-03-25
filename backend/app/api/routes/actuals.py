from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.db_models import (
    User, MaterialLineItem, WasteActual, WastePrediction,
    ModelFeedbackLog, Project, ProjectPhase, CrewProfile,
    MaterialTypeEnum, ProjectType, ProjectPhaseEnum
)
from app.models.schemas import ActualCreate, WasteActualOut

router = APIRouter(prefix="/actuals", tags=["actuals"])


@router.post("/", response_model=WasteActualOut)
def record_actual(
    payload: ActualCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    mat = db.query(MaterialLineItem).join(Project).filter(
        MaterialLineItem.id == payload.material_line_item_id,
        Project.company_id == current_user.company_id,
    ).first()
    if not mat:
        raise HTTPException(status_code=404, detail="Material not found")

    # Compute actual waste %
    actual_waste_pct = None
    if mat.estimated_quantity > 0:
        actual_waste_pct = round((payload.actual_waste_qty / mat.estimated_quantity) * 100, 2)

    # Upsert actual
    existing = db.query(WasteActual).filter(
        WasteActual.material_line_item_id == mat.id
    ).first()

    if existing:
        existing.actual_waste_qty = payload.actual_waste_qty
        existing.actual_waste_pct = actual_waste_pct
        existing.notes = payload.notes
        actual = existing
    else:
        actual = WasteActual(
            material_line_item_id=mat.id,
            actual_waste_qty=payload.actual_waste_qty,
            actual_waste_pct=actual_waste_pct,
            recorded_by=current_user.id,
            notes=payload.notes,
        )
        db.add(actual)

    db.flush()

    # Log the delta for the feedback loop
    prediction = db.query(WastePrediction).filter(
        WastePrediction.material_line_item_id == mat.id
    ).first()

    if prediction and actual_waste_pct is not None:
        delta = actual_waste_pct - prediction.predicted_waste_pct
        log = ModelFeedbackLog(
            company_id=current_user.company_id,
            prediction_id=prediction.id,
            actual_id=actual.id,
            delta_pct=round(delta, 2),
        )
        db.add(log)

    db.commit()
    db.refresh(actual)

    # Trigger async retraining check
    _maybe_trigger_retraining(current_user.company_id, db)

    return actual


# ── Historical Import ─────────────────────────────────────────────────────────

class HistoricalRecord(BaseModel):
    material_type: MaterialTypeEnum
    phase_name: ProjectPhaseEnum
    project_type: ProjectType = ProjectType.residential
    crew_size: int = 8
    avg_experience_years: float = 5.0
    location: Optional[str] = None
    estimated_quantity: float
    unit: str
    actual_waste_qty: float
    notes: Optional[str] = None


class ImportResult(BaseModel):
    imported: int
    project_id: str
    project_name: str
    retraining_triggered: bool
    message: str


@router.post("/import-historical", response_model=ImportResult)
def import_historical(
    records: List[HistoricalRecord],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk-import historical project waste data to seed the company model.
    Creates a 'Historical Import' project with one material per record,
    attaches actuals, and triggers company model retraining.
    """
    if not records:
        raise HTTPException(status_code=400, detail="No records provided")
    if len(records) > 500:
        raise HTTPException(status_code=400, detail="Maximum 500 records per import")

    # Create a single historical import project to house all records
    batch_name = f"Historical Import — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    project = Project(
        company_id=current_user.company_id,
        name=batch_name,
        type=ProjectType.residential,  # default; individual records may vary
        location="Various",
        status="completed",
    )
    db.add(project)
    db.flush()

    # Create one phase per phase_name used (deduplicated)
    phase_names_used = set(r.phase_name for r in records)
    phase_map: dict = {}
    for pn in phase_names_used:
        phase = ProjectPhase(project_id=project.id, phase_name=pn)
        db.add(phase)
        db.flush()
        phase_map[pn] = phase.id

    imported = 0
    for rec in records:
        # Resolve or create crew profile
        crew = db.query(CrewProfile).filter(
            CrewProfile.company_id == current_user.company_id,
            CrewProfile.size == rec.crew_size,
        ).first()
        if not crew:
            from app.ml.features import compute_experience_index
            exp_idx = compute_experience_index(rec.avg_experience_years)
            crew = CrewProfile(
                company_id=current_user.company_id,
                name=f"Imported Crew ({rec.avg_experience_years:.0f} yrs)",
                size=rec.crew_size,
                avg_experience_years=rec.avg_experience_years,
                experience_index=exp_idx,
            )
            db.add(crew)
            db.flush()

        mat = MaterialLineItem(
            project_id=project.id,
            phase_id=phase_map[rec.phase_name],
            crew_profile_id=crew.id,
            material_type=rec.material_type,
            estimated_quantity=rec.estimated_quantity,
            unit=rec.unit,
        )
        db.add(mat)
        db.flush()

        actual_waste_pct = None
        if rec.estimated_quantity > 0:
            actual_waste_pct = round((rec.actual_waste_qty / rec.estimated_quantity) * 100, 2)

        actual = WasteActual(
            material_line_item_id=mat.id,
            actual_waste_qty=rec.actual_waste_qty,
            actual_waste_pct=actual_waste_pct,
            recorded_by=current_user.id,
            notes=rec.notes or "Imported from historical data",
        )
        db.add(actual)
        imported += 1

    db.commit()

    # Trigger retraining — bypass the threshold for historical imports
    retraining_triggered = False
    try:
        from app.ml.trainer import retrain_company_model
        retrain_company_model(current_user.company_id, db)
        retraining_triggered = True
    except Exception as e:
        print(f"Retraining after import failed: {e}")

    total_actuals = (
        db.query(ModelFeedbackLog)
        .filter(ModelFeedbackLog.company_id == current_user.company_id)
        .count()
    ) or imported

    msg = (
        f"{imported} records imported and company model retrained."
        if retraining_triggered
        else f"{imported} records imported. Company model needs 10+ actuals to train (you have {imported} so far)."
    )

    return ImportResult(
        imported=imported,
        project_id=project.id,
        project_name=batch_name,
        retraining_triggered=retraining_triggered,
        message=msg,
    )


def _maybe_trigger_retraining(company_id: str, db: Session):
    """Trigger background retraining if threshold is met."""
    try:
        from app.ml.trainer import should_retrain, retrain_company_model
        if should_retrain(company_id, db):
            # In production this would be a Celery task
            # For MVP: run synchronously (acceptable for small datasets)
            retrain_company_model(company_id, db)
    except Exception as e:
        print(f"Retraining trigger failed: {e}")


@router.get("/project/{project_id}", response_model=List[WasteActualOut])
def get_project_actuals(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    materials = db.query(MaterialLineItem).join(Project).filter(
        MaterialLineItem.project_id == project_id,
        Project.company_id == current_user.company_id,
    ).all()

    actuals = []
    for mat in materials:
        if mat.actual:
            actuals.append(mat.actual)
    return actuals
