"""
Feature engineering for WasteIQ ML model.
This module is the core of the patent-worthy invention:
combining crew behavioral signals + project phase + environmental factors
into a unified feature vector for per-material waste prediction.
"""
import numpy as np
from typing import Optional


# Material workability index: how difficult each material is to cut/fit precisely.
# Higher = more cutting waste. Based on construction domain knowledge.
MATERIAL_WORKABILITY = {
    "concrete": 0.3,
    "steel_rebar": 0.2,
    "lumber": 0.6,
    "drywall": 0.7,
    "tiles": 0.9,      # highest — cuts are very wasteful
    "pipe": 0.4,
    "insulation": 0.5,
    "brick": 0.5,
    "glass": 0.85,
    "other": 0.5,
}

# Phase complexity: how waste-prone each construction phase is.
PHASE_COMPLEXITY = {
    "foundation": 0.3,
    "framing": 0.6,
    "mep": 0.7,       # plumbing/electrical has high off-cut waste
    "finishing": 0.8,  # finishing phase has most material fitting waste
    "landscaping": 0.4,
}

# Weather risk by material: how much bad weather amplifies waste for each material.
MATERIAL_WEATHER_SENSITIVITY = {
    "concrete": 0.9,   # cold/wet weather causes concrete waste
    "lumber": 0.7,     # warping in humid conditions
    "drywall": 0.8,    # moisture damage
    "steel_rebar": 0.3,
    "tiles": 0.2,
    "pipe": 0.1,
    "insulation": 0.6,
    "brick": 0.4,
    "glass": 0.3,
    "other": 0.4,
}

# Weather zone risk scores (0=low risk, 1=high risk)
WEATHER_ZONE_RISK = {
    "tropical": 0.7,
    "hot_dry": 0.5,
    "cold_wet": 0.8,
    "temperate": 0.3,
    "arid": 0.4,
}


def compute_experience_index(avg_experience_years: float) -> float:
    """
    Normalize crew experience into a 0-1 index.
    0 = least experienced (0 yrs), 1 = most experienced (20+ yrs).
    Uses a logarithmic curve — experience gains plateau after ~15 years.
    """
    clamped = min(max(avg_experience_years, 0), 20)
    return float(np.log1p(clamped) / np.log1p(20))


def infer_weather_zone(country: Optional[str], location: Optional[str]) -> str:
    """
    Simple heuristic to infer weather zone from location metadata.
    In production this would call a weather API.
    """
    if not location and not country:
        return "temperate"
    text = f"{location or ''} {country or ''}".lower()
    if any(w in text for w in ["india", "thailand", "brazil", "singapore", "malaysia"]):
        return "tropical"
    if any(w in text for w in ["canada", "russia", "norway", "finland", "alaska"]):
        return "cold_wet"
    if any(w in text for w in ["dubai", "saudi", "egypt", "arizona", "nevada"]):
        return "hot_dry"
    return "temperate"


def build_feature_vector(
    material_type: str,
    estimated_quantity: float,
    phase_name: Optional[str],
    experience_index: float,
    crew_size: int,
    weather_zone: str,
    is_urban: bool = False,
    supplier_reliability: float = 0.8,
    company_historical_waste_pct: Optional[float] = None,
) -> dict:
    """
    Core patent claim: build the unified feature vector used for waste prediction.

    Returns a dict that is both the model input and the feature_snapshot
    stored on every WastePrediction record (enabling full auditability).
    """
    material_workability = MATERIAL_WORKABILITY.get(material_type, 0.5)
    phase_complexity = PHASE_COMPLEXITY.get(phase_name or "framing", 0.5)
    weather_risk = WEATHER_ZONE_RISK.get(weather_zone, 0.3)
    weather_sensitivity = MATERIAL_WEATHER_SENSITIVITY.get(material_type, 0.4)

    # Derived composite signals
    environmental_risk = weather_risk * weather_sensitivity
    site_constraint_penalty = 0.15 if is_urban else 0.0
    # Crew size factor: larger crews = slightly more coordination waste
    crew_size_factor = min(crew_size / 50, 1.0)

    return {
        # Raw signals
        "material_type_encoded": list(MATERIAL_WORKABILITY.keys()).index(
            material_type if material_type in MATERIAL_WORKABILITY else "other"
        ),
        "estimated_quantity": estimated_quantity,
        "experience_index": experience_index,
        "crew_size": crew_size,
        "supplier_reliability": supplier_reliability,

        # Engineered features (patent-critical)
        "material_workability_index": material_workability,
        "phase_complexity_score": phase_complexity,
        "environmental_risk_score": environmental_risk,
        "site_constraint_score": site_constraint_penalty,
        "crew_size_factor": crew_size_factor,
        "company_historical_waste_pct": company_historical_waste_pct or 0.12,

        # Metadata (not used as model features, stored for audit)
        "_material_type": material_type,
        "_phase_name": phase_name,
        "_weather_zone": weather_zone,
    }


def feature_vector_to_array(fv: dict) -> list:
    """Extract only the numeric model input features from the feature vector."""
    keys = [
        "material_type_encoded",
        "estimated_quantity",
        "experience_index",
        "crew_size",
        "supplier_reliability",
        "material_workability_index",
        "phase_complexity_score",
        "environmental_risk_score",
        "site_constraint_score",
        "crew_size_factor",
        "company_historical_waste_pct",
    ]
    return [fv[k] for k in keys]


FEATURE_NAMES = [
    "material_type",
    "estimated_quantity",
    "experience_index",
    "crew_size",
    "supplier_reliability",
    "material_workability",
    "phase_complexity",
    "environmental_risk",
    "site_constraint",
    "crew_size_factor",
    "historical_waste",
]
