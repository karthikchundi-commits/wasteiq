from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.db_models import (
    User, MaterialLineItem, WasteActual, WastePrediction,
    ModelFeedbackLog, Project
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
