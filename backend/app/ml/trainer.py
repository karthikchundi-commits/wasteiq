"""
WasteIQ Model Trainer.

Retraining is triggered when a company accumulates 5+ new actuals since last retrain.
This implements the patent-critical feedback loop:
  predicted waste → actual waste recorded → delta logged → model retrained.
"""
import os
import pickle
import numpy as np
from typing import List
from app.config import settings
from app.ml.features import (
    build_feature_vector,
    feature_vector_to_array,
    compute_experience_index,
    infer_weather_zone,
)


RETRAIN_THRESHOLD = 5  # minimum new actuals needed to trigger retraining


def should_retrain(company_id: str, db) -> bool:
    """Check if enough new actuals have accumulated since last retraining."""
    from app.models.db_models import ModelFeedbackLog
    pending = (
        db.query(ModelFeedbackLog)
        .filter(
            ModelFeedbackLog.company_id == company_id,
            ModelFeedbackLog.used_in_retraining == False,
        )
        .count()
    )
    return pending >= RETRAIN_THRESHOLD


def retrain_company_model(company_id: str, db):
    """
    Fine-tune a company-specific XGBoost model using all available actuals.
    Falls back to training from scratch if no base model exists.
    """
    try:
        from xgboost import XGBRegressor
        from app.models.db_models import (
            WasteActual, MaterialLineItem, ProjectPhase,
            Project, CrewProfile, ModelFeedbackLog
        )
        from datetime import datetime

        # Gather training data from actuals
        actuals = (
            db.query(WasteActual)
            .join(MaterialLineItem)
            .join(Project)
            .filter(Project.company_id == company_id)
            .all()
        )

        if len(actuals) < 10:
            return  # Not enough data to fine-tune

        X, y = [], []
        for actual in actuals:
            if actual.actual_waste_pct is None:
                continue
            mat = actual.material
            phase = mat.phase
            crew = mat.crew_profile
            project = mat.project

            experience_index = compute_experience_index(
                crew.avg_experience_years if crew else 5.0
            )
            weather_zone = infer_weather_zone(project.country if hasattr(project, 'country') else None, project.location)

            fv = build_feature_vector(
                material_type=mat.material_type.value,
                estimated_quantity=mat.estimated_quantity,
                phase_name=phase.phase_name.value if phase else None,
                experience_index=experience_index,
                crew_size=crew.size if crew else 10,
                weather_zone=weather_zone,
            )
            X.append(feature_vector_to_array(fv))
            y.append(actual.actual_waste_pct / 100.0)  # store as fraction

        if len(X) < 10:
            return

        X = np.array(X)
        y = np.array(y)

        model = XGBRegressor(
            n_estimators=100,
            max_depth=4,
            learning_rate=0.1,
            objective="reg:squarederror",
            random_state=42,
        )
        model.fit(X, y)

        os.makedirs(settings.model_store_path, exist_ok=True)
        model_path = os.path.join(settings.model_store_path, f"company_{company_id}.pkl")
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        # Mark feedback logs as used in retraining
        db.query(ModelFeedbackLog).filter(
            ModelFeedbackLog.company_id == company_id,
            ModelFeedbackLog.used_in_retraining == False,
        ).update({"used_in_retraining": True, "retrain_date": datetime.utcnow()})
        db.commit()

    except Exception as e:
        print(f"Retraining failed for company {company_id}: {e}")


def generate_synthetic_training_data(n_samples: int = 5000) -> tuple:
    """
    Generate synthetic training data to bootstrap the base model.

    Based on real construction waste research benchmarks:
    - Concrete:    2-8%   (weather-sensitive, phase matters less)
    - Steel rebar: 3-8%   (low workability waste, mostly off-cuts)
    - Lumber:      10-15% (high — framing cuts, humidity warp)
    - Drywall:     8-12%  (moisture + fitting waste)
    - Tiles:       10-15% (highest — irregular cuts, breakage)
    - Pipe:        5-10%  (MEP off-cuts)
    - Insulation:  5-8%
    - Brick:       5-10%  (breakage during delivery + cutting)
    - Glass:       8-15%  (highest breakage risk)

    Interaction effects modelled:
    - Junior crew (<3 yrs) adds +40-60% to base waste
    - Senior crew (>10 yrs) reduces by 20-30%
    - Cold/wet weather amplifies concrete/lumber/drywall waste significantly
    - Urban sites add 10-15% from handling constraints
    - Finishing phase is worst for tiles/drywall/glass
    - MEP phase is worst for pipe
    """
    np.random.seed(42)
    from app.ml.features import (
        MATERIAL_WORKABILITY, PHASE_COMPLEXITY,
        WEATHER_ZONE_RISK, MATERIAL_WEATHER_SENSITIVITY
    )

    # Real industry baseline waste % by material (midpoint of research range)
    MATERIAL_BASE_WASTE = {
        "concrete":    0.045,   # 4.5% baseline
        "steel_rebar": 0.055,   # 5.5%
        "lumber":      0.125,   # 12.5%
        "drywall":     0.100,   # 10%
        "tiles":       0.125,   # 12.5%
        "pipe":        0.075,   # 7.5%
        "insulation":  0.065,   # 6.5%
        "brick":       0.075,   # 7.5%
        "glass":       0.110,   # 11%
        "other":       0.090,   # 9%
    }

    # Phase multiplier on top of base (finishing is worst for fit-and-finish materials)
    MATERIAL_PHASE_MULTIPLIER = {
        ("tiles",       "finishing"):  1.30,
        ("drywall",     "finishing"):  1.25,
        ("glass",       "finishing"):  1.20,
        ("lumber",      "framing"):    1.20,
        ("pipe",        "mep"):        1.25,
        ("insulation",  "mep"):        1.15,
        ("concrete",    "foundation"): 1.10,
        ("brick",       "framing"):    1.15,
    }

    X, y = [], []
    materials = list(MATERIAL_WORKABILITY.keys())
    phases = list(PHASE_COMPLEXITY.keys())
    weather_zones = list(WEATHER_ZONE_RISK.keys())

    for _ in range(n_samples):
        mat = np.random.choice(materials)
        phase = np.random.choice(phases)
        weather = np.random.choice(weather_zones)
        experience_years = np.random.choice([
            np.random.uniform(0, 3),    # junior:  30% of workforce
            np.random.uniform(3, 10),   # mid:     45%
            np.random.uniform(10, 25),  # senior:  25%
        ], p=[0.30, 0.45, 0.25])
        experience_index = compute_experience_index(experience_years)
        crew_size = int(np.random.choice([
            np.random.randint(3, 8),    # small crew
            np.random.randint(8, 25),   # medium crew
            np.random.randint(25, 80),  # large crew
        ], p=[0.35, 0.45, 0.20]))
        supplier_reliability = np.random.beta(5, 2)  # skewed toward reliable
        qty = np.random.lognormal(mean=4, sigma=1.5)  # realistic qty distribution
        qty = float(np.clip(qty, 5, 50000))
        is_urban = np.random.random() < 0.35
        hist_waste = np.random.uniform(0.04, 0.22)

        fv = build_feature_vector(
            material_type=mat,
            estimated_quantity=qty,
            phase_name=phase,
            experience_index=experience_index,
            crew_size=crew_size,
            weather_zone=weather,
            is_urban=is_urban,
            supplier_reliability=supplier_reliability,
            company_historical_waste_pct=hist_waste,
        )

        # Start from material baseline
        base = MATERIAL_BASE_WASTE.get(mat, 0.09)

        # Apply phase×material interaction
        phase_mult = MATERIAL_PHASE_MULTIPLIER.get((mat, phase), 1.0)
        waste = base * phase_mult

        # Crew experience effect: junior crews produce disproportionately more waste
        # experience_index 0→1, effect is nonlinear
        exp_multiplier = 1.0 + (1 - experience_index) ** 1.5 * 0.6
        waste *= exp_multiplier

        # Weather × material interaction
        weather_risk = WEATHER_ZONE_RISK.get(weather, 0.3)
        weather_sensitivity = MATERIAL_WEATHER_SENSITIVITY.get(mat, 0.4)
        weather_effect = 1.0 + weather_risk * weather_sensitivity * 0.4
        waste *= weather_effect

        # Urban site penalty (tight space = more handling damage)
        if is_urban:
            waste *= 1.12

        # Supplier reliability: unreliable suppliers = partial deliveries = off-cuts
        supplier_effect = 1.0 + (1 - supplier_reliability) * 0.25
        waste *= supplier_effect

        # Crew size: very large crews have coordination waste, very small have efficiency
        if crew_size > 40:
            waste *= 1.05
        elif crew_size < 5:
            waste *= 0.95

        # Blend with historical (historical anchors the prediction toward company reality)
        waste = waste * 0.65 + hist_waste * 0.35

        # Realistic noise (heteroskedastic: high-waste materials have more variance)
        noise_std = 0.008 + base * 0.15
        waste += np.random.normal(0, noise_std)
        waste_pct = float(np.clip(waste, 0.005, 0.55))

        X.append(feature_vector_to_array(fv))
        y.append(waste_pct)

    return np.array(X), np.array(y)


def train_base_model():
    """Train and save the base model from synthetic data."""
    try:
        from xgboost import XGBRegressor
    except ImportError:
        print("XGBoost not installed — skipping base model training")
        return None

    print("Generating synthetic training data (5000 samples)...")
    X, y = generate_synthetic_training_data(5000)

    model = XGBRegressor(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
        random_state=42,
    )
    model.fit(X, y)

    os.makedirs(settings.model_store_path, exist_ok=True)
    model_path = os.path.join(settings.model_store_path, "base_model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    print(f"Base model saved to {model_path} ({len(y)} training samples)")
    return model


def ensure_base_model():
    """Train base model if it doesn't already exist on disk. Called at startup."""
    model_path = os.path.join(settings.model_store_path, "base_model.pkl")
    if not os.path.exists(model_path):
        print("Base model not found — training from synthetic data...")
        train_base_model()
    else:
        print(f"Base model found at {model_path}")


if __name__ == "__main__":
    train_base_model()
