from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.db_models import (
    User, Project, MaterialLineItem, WastePrediction,
    CrewProfile, ProjectPhase
)
from app.models.schemas import PredictRequest, PredictionSummary
from app.ml.predictor import WastePredictor

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("/generate", response_model=List[PredictionSummary])
def generate_predictions(
    payload: PredictRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == payload.project_id,
        Project.company_id == current_user.company_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    materials = db.query(MaterialLineItem).filter(
        MaterialLineItem.project_id == project.id
    ).all()

    if not materials:
        raise HTTPException(status_code=400, detail="No materials found for this project")

    # Compute company historical waste average
    from sqlalchemy import func
    from app.models.db_models import WasteActual
    hist_avg = db.query(func.avg(WasteActual.actual_waste_pct)).join(
        MaterialLineItem
    ).join(Project).filter(
        Project.company_id == current_user.company_id
    ).scalar()

    predictor = WastePredictor(company_id=current_user.company_id)
    results = []

    for mat in materials:
        crew: CrewProfile = mat.crew_profile
        phase: ProjectPhase = mat.phase

        result = predictor.predict(
            material_type=mat.material_type.value,
            estimated_quantity=mat.estimated_quantity,
            phase_name=phase.phase_name.value if phase else None,
            crew_size=crew.size if crew else 10,
            avg_experience_years=crew.avg_experience_years if crew else 5.0,
            location=project.location,
            company_historical_waste_pct=hist_avg,
        )

        # Upsert prediction record
        existing = db.query(WastePrediction).filter(
            WastePrediction.material_line_item_id == mat.id
        ).first()

        if existing:
            existing.predicted_waste_pct = result["predicted_waste_pct"]
            existing.ci_low = result["ci_low"]
            existing.ci_high = result["ci_high"]
            existing.recommended_order_qty = result["recommended_order_qty"]
            existing.model_version = result["model_version"]
            existing.feature_snapshot = result["feature_snapshot"]
            existing.shap_values = result["shap_values"]
        else:
            pred = WastePrediction(
                material_line_item_id=mat.id,
                predicted_waste_pct=result["predicted_waste_pct"],
                ci_low=result["ci_low"],
                ci_high=result["ci_high"],
                recommended_order_qty=result["recommended_order_qty"],
                model_version=result["model_version"],
                feature_snapshot=result["feature_snapshot"],
                shap_values=result["shap_values"],
            )
            db.add(pred)

        predicted_waste_cost = None
        if mat.unit_price:
            waste_qty = result["recommended_order_qty"] - mat.estimated_quantity
            predicted_waste_cost = round(waste_qty * mat.unit_price, 2)

        results.append(PredictionSummary(
            material_id=mat.id,
            material_type=mat.material_type.value,
            estimated_quantity=mat.estimated_quantity,
            unit=mat.unit,
            predicted_waste_pct=result["predicted_waste_pct"],
            ci_low=result["ci_low"],
            ci_high=result["ci_high"],
            recommended_order_qty=result["recommended_order_qty"],
            predicted_waste_cost=predicted_waste_cost,
            top_drivers=result["shap_values"] or [],
        ))

    db.commit()
    return results


@router.get("/{project_id}", response_model=List[PredictionSummary])
def get_predictions(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = db.query(Project).filter(
        Project.id == project_id,
        Project.company_id == current_user.company_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    materials = db.query(MaterialLineItem).filter(
        MaterialLineItem.project_id == project_id
    ).all()

    results = []
    for mat in materials:
        if not mat.prediction:
            continue
        pred = mat.prediction
        predicted_waste_cost = None
        if mat.unit_price:
            waste_qty = pred.recommended_order_qty - mat.estimated_quantity
            predicted_waste_cost = round(waste_qty * mat.unit_price, 2)

        results.append(PredictionSummary(
            material_id=mat.id,
            material_type=mat.material_type.value,
            estimated_quantity=mat.estimated_quantity,
            unit=mat.unit,
            predicted_waste_pct=pred.predicted_waste_pct,
            ci_low=pred.ci_low,
            ci_high=pred.ci_high,
            recommended_order_qty=pred.recommended_order_qty,
            predicted_waste_cost=predicted_waste_cost,
            top_drivers=pred.shap_values or [],
        ))

    return results
