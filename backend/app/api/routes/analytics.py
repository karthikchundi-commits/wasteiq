from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.db_models import (
    User, Project, MaterialLineItem, WastePrediction,
    WasteActual, ModelFeedbackLog, CrewProfile
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsSummary(BaseModel):
    total_projects: int
    projects_with_actuals: int
    total_predictions: int
    total_actuals: int
    avg_model_accuracy_pct: Optional[float]   # 100 - mean(abs(delta))
    total_predicted_waste_cost: Optional[float]


class MaterialAccuracy(BaseModel):
    material_type: str
    avg_predicted_pct: float
    avg_actual_pct: Optional[float]
    count_predictions: int
    count_actuals: int


class CrewPerformance(BaseModel):
    crew_name: str
    avg_actual_pct: float
    count: int


class ProjectAccuracy(BaseModel):
    project_name: str
    project_type: str
    avg_predicted_pct: Optional[float]
    avg_actual_pct: Optional[float]
    material_count: int
    actuals_count: int


class AnalyticsOverview(BaseModel):
    summary: AnalyticsSummary
    material_accuracy: List[MaterialAccuracy]
    crew_performance: List[CrewPerformance]
    project_accuracy: List[ProjectAccuracy]


@router.get("/overview", response_model=AnalyticsOverview)
def get_analytics_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company_id = current_user.company_id

    # ── Summary ──────────────────────────────────────────────────────────────

    total_projects = db.query(func.count(Project.id)).filter(
        Project.company_id == company_id
    ).scalar() or 0

    # Projects that have at least one actual recorded
    projects_with_actuals = (
        db.query(func.count(func.distinct(MaterialLineItem.project_id)))
        .join(WasteActual, WasteActual.material_line_item_id == MaterialLineItem.id)
        .join(Project, Project.id == MaterialLineItem.project_id)
        .filter(Project.company_id == company_id)
        .scalar() or 0
    )

    total_predictions = (
        db.query(func.count(WastePrediction.id))
        .join(MaterialLineItem, MaterialLineItem.id == WastePrediction.material_line_item_id)
        .join(Project, Project.id == MaterialLineItem.project_id)
        .filter(Project.company_id == company_id)
        .scalar() or 0
    )

    total_actuals = (
        db.query(func.count(WasteActual.id))
        .join(MaterialLineItem, MaterialLineItem.id == WasteActual.material_line_item_id)
        .join(Project, Project.id == MaterialLineItem.project_id)
        .filter(Project.company_id == company_id)
        .scalar() or 0
    )

    # avg model accuracy = 100 - mean(abs(delta_pct))
    avg_abs_delta = (
        db.query(func.avg(func.abs(ModelFeedbackLog.delta_pct)))
        .filter(ModelFeedbackLog.company_id == company_id)
        .scalar()
    )
    avg_model_accuracy_pct = round(100 - avg_abs_delta, 1) if avg_abs_delta is not None else None

    # Total predicted waste cost across all projects
    total_predicted_waste_cost = None
    materials_with_pred = (
        db.query(MaterialLineItem, WastePrediction)
        .join(WastePrediction, WastePrediction.material_line_item_id == MaterialLineItem.id)
        .join(Project, Project.id == MaterialLineItem.project_id)
        .filter(Project.company_id == company_id, MaterialLineItem.unit_price.isnot(None))
        .all()
    )
    if materials_with_pred:
        total = sum(
            (pred.recommended_order_qty - mat.estimated_quantity) * mat.unit_price
            for mat, pred in materials_with_pred
            if pred.recommended_order_qty is not None
        )
        total_predicted_waste_cost = round(total, 2)

    summary = AnalyticsSummary(
        total_projects=total_projects,
        projects_with_actuals=projects_with_actuals,
        total_predictions=total_predictions,
        total_actuals=total_actuals,
        avg_model_accuracy_pct=avg_model_accuracy_pct,
        total_predicted_waste_cost=total_predicted_waste_cost,
    )

    # ── Material Accuracy ─────────────────────────────────────────────────────

    # All predictions grouped by material_type
    pred_rows = (
        db.query(
            MaterialLineItem.material_type,
            func.avg(WastePrediction.predicted_waste_pct).label("avg_pred"),
            func.count(WastePrediction.id).label("cnt_pred"),
        )
        .join(WastePrediction, WastePrediction.material_line_item_id == MaterialLineItem.id)
        .join(Project, Project.id == MaterialLineItem.project_id)
        .filter(Project.company_id == company_id)
        .group_by(MaterialLineItem.material_type)
        .all()
    )

    actual_rows = (
        db.query(
            MaterialLineItem.material_type,
            func.avg(WasteActual.actual_waste_pct).label("avg_actual"),
            func.count(WasteActual.id).label("cnt_actual"),
        )
        .join(WasteActual, WasteActual.material_line_item_id == MaterialLineItem.id)
        .join(Project, Project.id == MaterialLineItem.project_id)
        .filter(Project.company_id == company_id)
        .group_by(MaterialLineItem.material_type)
        .all()
    )

    actual_map = {r.material_type: (r.avg_actual, r.cnt_actual) for r in actual_rows}

    material_accuracy = [
        MaterialAccuracy(
            material_type=r.material_type.value if hasattr(r.material_type, "value") else str(r.material_type),
            avg_predicted_pct=round(r.avg_pred, 2),
            avg_actual_pct=round(actual_map[r.material_type][0], 2) if r.material_type in actual_map else None,
            count_predictions=r.cnt_pred,
            count_actuals=actual_map[r.material_type][1] if r.material_type in actual_map else 0,
        )
        for r in pred_rows
    ]

    # ── Crew Performance ──────────────────────────────────────────────────────

    crew_rows = (
        db.query(
            CrewProfile.name.label("crew_name"),
            func.avg(WasteActual.actual_waste_pct).label("avg_actual"),
            func.count(WasteActual.id).label("cnt"),
        )
        .join(MaterialLineItem, MaterialLineItem.crew_profile_id == CrewProfile.id)
        .join(WasteActual, WasteActual.material_line_item_id == MaterialLineItem.id)
        .join(Project, Project.id == MaterialLineItem.project_id)
        .filter(Project.company_id == company_id)
        .group_by(CrewProfile.id, CrewProfile.name)
        .order_by(func.avg(WasteActual.actual_waste_pct))
        .all()
    )

    crew_performance = [
        CrewPerformance(
            crew_name=r.crew_name,
            avg_actual_pct=round(r.avg_actual, 2),
            count=r.cnt,
        )
        for r in crew_rows
    ]

    # ── Project Accuracy ──────────────────────────────────────────────────────

    projects = (
        db.query(Project)
        .filter(Project.company_id == company_id)
        .order_by(Project.created_at.desc())
        .all()
    )

    project_accuracy = []
    for proj in projects:
        mat_ids = [m.id for m in proj.materials]
        if not mat_ids:
            continue

        avg_pred = (
            db.query(func.avg(WastePrediction.predicted_waste_pct))
            .filter(WastePrediction.material_line_item_id.in_(mat_ids))
            .scalar()
        )
        avg_actual = (
            db.query(func.avg(WasteActual.actual_waste_pct))
            .filter(WasteActual.material_line_item_id.in_(mat_ids))
            .scalar()
        )
        cnt_actuals = (
            db.query(func.count(WasteActual.id))
            .filter(WasteActual.material_line_item_id.in_(mat_ids))
            .scalar() or 0
        )

        project_accuracy.append(ProjectAccuracy(
            project_name=proj.name,
            project_type=proj.type.value if hasattr(proj.type, "value") else str(proj.type),
            avg_predicted_pct=round(avg_pred, 2) if avg_pred is not None else None,
            avg_actual_pct=round(avg_actual, 2) if avg_actual is not None else None,
            material_count=len(proj.materials),
            actuals_count=cnt_actuals,
        ))

    return AnalyticsOverview(
        summary=summary,
        material_accuracy=material_accuracy,
        crew_performance=crew_performance,
        project_accuracy=project_accuracy,
    )
