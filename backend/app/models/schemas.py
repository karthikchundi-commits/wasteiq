from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
from app.models.db_models import ProjectType, ProjectPhaseEnum, MaterialTypeEnum


# --- Auth ---

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    company_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str


# --- Crew Profile ---

class CrewProfileCreate(BaseModel):
    name: str
    size: int
    avg_experience_years: float

class CrewProfileOut(BaseModel):
    id: str
    name: str
    size: int
    avg_experience_years: float
    experience_index: Optional[float]

    class Config:
        from_attributes = True


# --- Project ---

class PhaseCreate(BaseModel):
    phase_name: ProjectPhaseEnum
    planned_start: Optional[datetime]
    planned_end: Optional[datetime]

class MaterialCreate(BaseModel):
    material_type: MaterialTypeEnum
    estimated_quantity: float
    unit: str
    unit_price: Optional[float]
    phase_name: Optional[ProjectPhaseEnum]
    crew_profile_id: Optional[str]

class ProjectCreate(BaseModel):
    name: str
    type: ProjectType
    location: Optional[str]
    area_sqm: Optional[float]
    start_date: Optional[datetime]
    phases: List[PhaseCreate] = []
    materials: List[MaterialCreate] = []

class WastePredictionOut(BaseModel):
    id: str
    predicted_waste_pct: float
    ci_low: float
    ci_high: float
    recommended_order_qty: float
    model_version: Optional[str]
    shap_values: Optional[List[dict]]

    class Config:
        from_attributes = True

class WasteActualOut(BaseModel):
    id: str
    actual_waste_qty: float
    actual_waste_pct: Optional[float]
    recorded_at: datetime

    class Config:
        from_attributes = True

class MaterialLineItemOut(BaseModel):
    id: str
    material_type: str
    estimated_quantity: float
    unit: str
    unit_price: Optional[float]
    prediction: Optional[WastePredictionOut]
    actual: Optional[WasteActualOut]

    class Config:
        from_attributes = True

class ProjectOut(BaseModel):
    id: str
    name: str
    type: str
    location: Optional[str]
    area_sqm: Optional[float]
    start_date: Optional[datetime]
    status: str
    created_at: datetime
    materials: List[MaterialLineItemOut] = []

    class Config:
        from_attributes = True


# --- Predictions ---

class PredictRequest(BaseModel):
    project_id: str

class PredictionSummary(BaseModel):
    material_id: str
    material_type: str
    estimated_quantity: float
    unit: str
    predicted_waste_pct: float
    ci_low: float
    ci_high: float
    recommended_order_qty: float
    predicted_waste_cost: Optional[float]
    top_drivers: List[dict] = []


# --- Actuals ---

class ActualCreate(BaseModel):
    material_line_item_id: str
    actual_waste_qty: float
    notes: Optional[str]
