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


def generate_synthetic_training_data(n_samples: int = 2000) -> tuple:
    """
    Generate synthetic training data to bootstrap the base model.
    Based on construction waste research benchmarks.
    """
    np.random.seed(42)
    from app.ml.features import (
        MATERIAL_WORKABILITY, PHASE_COMPLEXITY,
        WEATHER_ZONE_RISK, MATERIAL_WEATHER_SENSITIVITY
    )

    X, y = [], []
    materials = list(MATERIAL_WORKABILITY.keys())
    phases = list(PHASE_COMPLEXITY.keys())
    weather_zones = list(WEATHER_ZONE_RISK.keys())

    for _ in range(n_samples):
        mat = np.random.choice(materials)
        phase = np.random.choice(phases)
        weather = np.random.choice(weather_zones)
        experience_index = np.random.beta(2, 2)  # most crews are mid-level
        crew_size = int(np.random.randint(3, 60))
        supplier_reliability = np.random.uniform(0.6, 1.0)
        qty = np.random.uniform(10, 5000)
        hist_waste = np.random.uniform(0.05, 0.20)

        fv = build_feature_vector(
            material_type=mat,
            estimated_quantity=qty,
            phase_name=phase,
            experience_index=experience_index,
            crew_size=crew_size,
            weather_zone=weather,
            supplier_reliability=supplier_reliability,
            company_historical_waste_pct=hist_waste,
        )

        # Simulate realistic waste % based on domain rules + noise
        base_waste = (
            fv["material_workability_index"] * 0.12
            + (1 - experience_index) * 0.08
            + fv["phase_complexity_score"] * 0.06
            + fv["environmental_risk_score"] * 0.04
            + np.random.normal(0, 0.02)
        )
        waste_pct = float(np.clip(base_waste, 0.01, 0.55))

        X.append(feature_vector_to_array(fv))
        y.append(waste_pct)

    return np.array(X), np.array(y)


def train_base_model():
    """Train and save the base model from synthetic data."""
    from xgboost import XGBRegressor

    print("Generating synthetic training data...")
    X, y = generate_synthetic_training_data(2000)

    model = XGBRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.05,
        objective="reg:squarederror",
        random_state=42,
    )
    model.fit(X, y)

    os.makedirs(settings.model_store_path, exist_ok=True)
    model_path = os.path.join(settings.model_store_path, "base_model.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    print(f"Base model saved to {model_path}")
    return model


if __name__ == "__main__":
    train_base_model()
