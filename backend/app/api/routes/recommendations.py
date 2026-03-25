"""
WasteIQ Recommendation Engine.

Converts waste predictions into actionable procurement recommendations
and compares against the industry-standard 15% flat buffer to show savings.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.db_models import (
    User, Project, MaterialLineItem, WastePrediction, WasteActual
)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

INDUSTRY_BUFFER_PCT = 0.15  # 15% flat buffer — construction industry standard


# ── Schemas ──────────────────────────────────────────────────────────────────

class MaterialRecommendation(BaseModel):
    material_id: str
    material_type: str
    unit: str
    estimated_quantity: float
    unit_price: Optional[float]

    # WasteIQ recommended order
    predicted_waste_pct: float
    recommended_order_qty: float

    # Industry flat buffer comparison
    flat_buffer_qty: float          # estimated * 1.15
    flat_buffer_waste_qty: float    # flat buffer - estimated

    # Savings
    ai_waste_qty: float             # recommended - estimated
    savings_qty: float              # flat_buffer_qty - recommended_order_qty
    savings_amount: Optional[float] # savings_qty * unit_price
    savings_pct: float              # % reduction vs flat buffer

    # Human-readable action
    action: str                     # "reduce" | "increase" | "maintain"
    recommendation: str             # e.g. "Order 85 m3 instead of 97 m3"
    insight: str                    # e.g. "Crew experience reduces expected waste"

    # Accuracy (if actuals recorded)
    actual_waste_pct: Optional[float]
    prediction_accuracy: Optional[str]  # "within 2%" or "off by 5%"


class ProjectRecommendationReport(BaseModel):
    project_id: str
    project_name: str
    project_type: str
    location: Optional[str]
    total_estimated_cost: Optional[float]

    # Aggregate savings
    total_flat_buffer_cost: Optional[float]
    total_ai_recommended_cost: Optional[float]
    total_savings_amount: Optional[float]
    total_savings_pct: Optional[float]
    co2_reduction_kg: Optional[float]   # estimated carbon saving from reduced waste

    materials: List[MaterialRecommendation]

    # Model accuracy (if actuals exist)
    actuals_recorded: int
    avg_prediction_error_pct: Optional[float]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_recommendation(mat: MaterialLineItem) -> Optional[MaterialRecommendation]:
    pred: WastePrediction = mat.prediction
    if not pred:
        return None

    est = mat.estimated_quantity
    rec = pred.recommended_order_qty
    flat = round(est * (1 + INDUSTRY_BUFFER_PCT), 2)
    flat_waste = round(flat - est, 2)
    ai_waste = round(rec - est, 2)
    savings_qty = round(flat - rec, 2)

    savings_amount = None
    flat_cost = None
    ai_cost = None
    if mat.unit_price:
        savings_amount = round(savings_qty * mat.unit_price, 2)
        flat_cost = round(flat * mat.unit_price, 2)
        ai_cost = round(rec * mat.unit_price, 2)

    savings_pct = round((savings_qty / flat) * 100, 1) if flat > 0 else 0

    # Action label
    diff_pct = ((rec - flat) / flat) * 100
    if diff_pct < -2:
        action = "reduce"
    elif diff_pct > 2:
        action = "increase"
    else:
        action = "maintain"

    # Recommendation text
    mat_name = mat.material_type.value.replace("_", " ").title()
    if action == "reduce":
        recommendation = (
            f"Order {rec} {mat.unit} instead of {flat} {mat.unit} "
            f"— save {savings_qty} {mat.unit}"
        )
    elif action == "increase":
        recommendation = (
            f"Order {rec} {mat.unit} instead of {flat} {mat.unit} "
            f"— project conditions require extra buffer"
        )
    else:
        recommendation = f"Standard order of {rec} {mat.unit} is appropriate"

    # Insight from top SHAP driver
    insight = _generate_insight(mat, pred, action)

    # Accuracy
    actual_waste_pct = None
    prediction_accuracy = None
    actual: WasteActual = mat.actual
    if actual and actual.actual_waste_pct is not None:
        actual_waste_pct = actual.actual_waste_pct
        error = abs(pred.predicted_waste_pct - actual.actual_waste_pct)
        if error <= 2:
            prediction_accuracy = f"Accurate (within {error:.1f}%)"
        elif error <= 5:
            prediction_accuracy = f"Close (off by {error:.1f}%)"
        else:
            prediction_accuracy = f"Off by {error:.1f}% — model will improve"

    return MaterialRecommendation(
        material_id=mat.id,
        material_type=mat.material_type.value,
        unit=mat.unit,
        estimated_quantity=est,
        unit_price=mat.unit_price,
        predicted_waste_pct=pred.predicted_waste_pct,
        recommended_order_qty=rec,
        flat_buffer_qty=flat,
        flat_buffer_waste_qty=flat_waste,
        ai_waste_qty=ai_waste,
        savings_qty=savings_qty,
        savings_amount=savings_amount,
        savings_pct=savings_pct,
        action=action,
        recommendation=recommendation,
        insight=insight,
        actual_waste_pct=actual_waste_pct,
        prediction_accuracy=prediction_accuracy,
    )


def _generate_insight(mat: MaterialLineItem, pred: WastePrediction, action: str) -> str:
    """Generate a human-readable insight from the top SHAP driver."""
    shap = pred.shap_values or []
    top = shap[0]["feature"] if shap else None

    driver_insights = {
        "experience_index": "Crew experience reduces cutting waste significantly",
        "material_workability": f"{mat.material_type.value.replace('_',' ').title()} requires precision cutting — waste is expected",
        "phase_complexity": "This construction phase typically has higher off-cut waste",
        "environmental_risk": "Weather conditions in this location increase material exposure waste",
        "historical_waste": "Based on your company's past projects with similar materials",
        "site_constraint": "Urban site constraints limit material staging, increasing handling waste",
    }

    if action == "reduce":
        return driver_insights.get(top, "AI model predicts lower waste than industry average for this project")
    elif action == "increase":
        return driver_insights.get(top, "Project conditions suggest more buffer than industry standard")
    return "Waste prediction aligns with industry standard for this material"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{project_id}", response_model=ProjectRecommendationReport)
def get_recommendations(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = (
        db.query(Project)
        .options(
            selectinload(Project.materials).selectinload(MaterialLineItem.prediction),
            selectinload(Project.materials).selectinload(MaterialLineItem.actual),
        )
        .filter(Project.id == project_id, Project.company_id == current_user.company_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    recs = [_build_recommendation(m) for m in project.materials if m.prediction]
    recs = [r for r in recs if r]  # filter None

    # Aggregate financials
    total_est_cost = None
    total_flat_cost = None
    total_ai_cost = None
    total_savings = None
    total_savings_pct = None

    if all(r.unit_price for r in recs):
        total_est_cost = round(sum(r.estimated_quantity * (r.unit_price or 0) for r in recs), 2)
        total_flat_cost = round(sum(r.flat_buffer_qty * (r.unit_price or 0) for r in recs), 2)
        total_ai_cost = round(sum(r.recommended_order_qty * (r.unit_price or 0) for r in recs), 2)
        total_savings = round(total_flat_cost - total_ai_cost, 2)
        total_savings_pct = round((total_savings / total_flat_cost) * 100, 1) if total_flat_cost else 0

    # CO2 estimate: construction waste ~0.5 kg CO2 per kg of material saved
    # Use savings_qty as a rough proxy (unit-agnostic, directional only)
    co2_kg = round(sum(r.savings_qty * 12 for r in recs), 1)  # rough: 12 kg CO2 per unit saved

    # Prediction accuracy
    actuals_recorded = sum(1 for r in recs if r.actual_waste_pct is not None)
    avg_error = None
    if actuals_recorded:
        errors = [
            abs(r.predicted_waste_pct - r.actual_waste_pct)
            for r in recs if r.actual_waste_pct is not None
        ]
        avg_error = round(sum(errors) / len(errors), 2)

    return ProjectRecommendationReport(
        project_id=project.id,
        project_name=project.name,
        project_type=project.type.value,
        location=project.location,
        total_estimated_cost=total_est_cost,
        total_flat_buffer_cost=total_flat_cost,
        total_ai_recommended_cost=total_ai_cost,
        total_savings_amount=total_savings,
        total_savings_pct=total_savings_pct,
        co2_reduction_kg=co2_kg,
        materials=recs,
        actuals_recorded=actuals_recorded,
        avg_prediction_error_pct=avg_error,
    )
