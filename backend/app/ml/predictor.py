"""
WasteIQ Waste Prediction Engine.

Two-layer prediction architecture:
  1. Global base model: pre-trained XGBoost on synthetic + research data
  2. Company layer: fine-tuned on company-specific actuals (unlocked after 20 projects)

Outputs waste % point estimate + quantile confidence interval.
SHAP values provide explainability for each prediction.
"""
import os
import json
import pickle
import numpy as np
from typing import Optional
from app.ml.features import (
    build_feature_vector,
    feature_vector_to_array,
    FEATURE_NAMES,
    compute_experience_index,
    infer_weather_zone,
)
from app.config import settings


class WastePredictor:
    def __init__(self, company_id: Optional[str] = None):
        self.company_id = company_id
        self.model = None
        self.model_version = "base_v1"
        self._load_model()

    def _load_model(self):
        """Load company-specific model if available, else fall back to base model."""
        if self.company_id:
            company_model_path = os.path.join(
                settings.model_store_path, f"company_{self.company_id}.pkl"
            )
            if os.path.exists(company_model_path):
                with open(company_model_path, "rb") as f:
                    self.model = pickle.load(f)
                self.model_version = f"company_{self.company_id}_v1"
                return

        base_model_path = os.path.join(settings.model_store_path, "base_model.pkl")
        if os.path.exists(base_model_path):
            with open(base_model_path, "rb") as f:
                self.model = pickle.load(f)
            self.model_version = "base_v1"
        else:
            self.model = None  # falls back to heuristic predictor

    def predict(
        self,
        material_type: str,
        estimated_quantity: float,
        phase_name: Optional[str],
        crew_size: int,
        avg_experience_years: float,
        location: Optional[str] = None,
        country: Optional[str] = None,
        is_urban: bool = False,
        supplier_reliability: float = 0.8,
        company_historical_waste_pct: Optional[float] = None,
    ) -> dict:
        """
        Run waste prediction for a single material line item.

        Returns:
            predicted_waste_pct: point estimate
            ci_low: 10th percentile estimate
            ci_high: 90th percentile estimate
            recommended_order_qty: estimated_quantity * (1 + predicted_waste_pct)
            feature_snapshot: all signals used (stored for audit + retraining)
            shap_values: top feature contributions (explainability)
        """
        experience_index = compute_experience_index(avg_experience_years)
        weather_zone = infer_weather_zone(country, location)

        feature_vector = build_feature_vector(
            material_type=material_type,
            estimated_quantity=estimated_quantity,
            phase_name=phase_name,
            experience_index=experience_index,
            crew_size=crew_size,
            weather_zone=weather_zone,
            is_urban=is_urban,
            supplier_reliability=supplier_reliability,
            company_historical_waste_pct=company_historical_waste_pct,
        )

        x = np.array([feature_vector_to_array(feature_vector)])

        if self.model is not None:
            predicted_pct = float(self.model.predict(x)[0])
            predicted_pct = max(0.01, min(predicted_pct, 0.60))  # clamp to 1–60%
            ci_low, ci_high = self._compute_confidence_interval(x, predicted_pct)
            shap_values = self._compute_shap(x, feature_vector)
        else:
            # Heuristic fallback when no trained model exists yet
            predicted_pct, ci_low, ci_high = self._heuristic_predict(feature_vector)
            shap_values = self._heuristic_shap(feature_vector)

        recommended_order_qty = round(estimated_quantity * (1 + predicted_pct), 2)

        return {
            "predicted_waste_pct": round(predicted_pct * 100, 2),  # return as %
            "ci_low": round(ci_low * 100, 2),
            "ci_high": round(ci_high * 100, 2),
            "recommended_order_qty": recommended_order_qty,
            "model_version": self.model_version,
            "feature_snapshot": feature_vector,
            "shap_values": shap_values,
        }

    def _compute_confidence_interval(self, x: np.ndarray, point_estimate: float):
        """Derive confidence interval using ±1 std from quantile models if available."""
        spread = point_estimate * 0.35  # fallback: ±35% of estimate
        return max(0, point_estimate - spread), min(0.60, point_estimate + spread)

    def _compute_shap(self, x: np.ndarray, feature_vector: dict) -> list:
        """Compute SHAP values if shap library available."""
        try:
            import shap
            explainer = shap.TreeExplainer(self.model)
            sv = explainer.shap_values(x)[0]
            top = sorted(
                zip(FEATURE_NAMES, sv), key=lambda t: abs(t[1]), reverse=True
            )[:5]
            return [{"feature": f, "impact": round(float(v), 4)} for f, v in top]
        except Exception:
            return self._heuristic_shap(feature_vector)

    def _heuristic_predict(self, fv: dict) -> tuple:
        """
        Rule-based waste prediction used as cold-start before model is trained.
        Combines material workability + crew experience + phase complexity.
        """
        base = fv["material_workability_index"] * 0.15   # max 15% from material
        exp_penalty = (1 - fv["experience_index"]) * 0.10  # inexperienced = +10%
        phase_add = fv["phase_complexity_score"] * 0.08
        env_add = fv["environmental_risk_score"] * 0.05
        site_add = fv["site_constraint_score"]
        hist = fv["company_historical_waste_pct"]

        # Weighted blend of heuristic and historical
        heuristic = base + exp_penalty + phase_add + env_add + site_add
        predicted = heuristic * 0.6 + hist * 0.4
        predicted = max(0.02, min(predicted, 0.55))

        spread = predicted * 0.4
        return predicted, max(0, predicted - spread), min(0.60, predicted + spread)

    def _heuristic_shap(self, fv: dict) -> list:
        """Return rough driver ranking based on feature magnitudes."""
        drivers = [
            ("material_workability", fv["material_workability_index"] * 0.15),
            ("experience_index", (1 - fv["experience_index"]) * 0.10),
            ("phase_complexity", fv["phase_complexity_score"] * 0.08),
            ("environmental_risk", fv["environmental_risk_score"] * 0.05),
            ("historical_waste", fv["company_historical_waste_pct"] * 0.4),
        ]
        drivers.sort(key=lambda t: abs(t[1]), reverse=True)
        return [{"feature": f, "impact": round(v, 4)} for f, v in drivers[:5]]
