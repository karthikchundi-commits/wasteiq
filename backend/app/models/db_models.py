import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Float, Integer, DateTime, ForeignKey,
    Enum, Boolean, JSON, Text
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


def gen_uuid():
    return str(uuid.uuid4())


class ProjectType(str, enum.Enum):
    residential = "residential"
    commercial = "commercial"
    industrial = "industrial"
    infrastructure = "infrastructure"


class ProjectPhaseEnum(str, enum.Enum):
    foundation = "foundation"
    framing = "framing"
    mep = "mep"
    finishing = "finishing"
    landscaping = "landscaping"


class MaterialTypeEnum(str, enum.Enum):
    concrete = "concrete"
    steel_rebar = "steel_rebar"
    lumber = "lumber"
    drywall = "drywall"
    tiles = "tiles"
    pipe = "pipe"
    insulation = "insulation"
    brick = "brick"
    glass = "glass"
    other = "other"


class ExperienceLevel(str, enum.Enum):
    junior = "junior"
    mid = "mid"
    senior = "senior"


class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, nullable=False)
    industry_segment = Column(String)
    country = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="company")
    projects = relationship("Project", back_populates="company")
    crew_profiles = relationship("CrewProfile", back_populates="company")


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="users")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True, default=gen_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    name = Column(String, nullable=False)
    type = Column(Enum(ProjectType), nullable=False)
    location = Column(String)
    area_sqm = Column(Float)
    start_date = Column(DateTime)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="projects")
    phases = relationship("ProjectPhase", back_populates="project", cascade="all, delete-orphan")
    materials = relationship("MaterialLineItem", back_populates="project", cascade="all, delete-orphan")


class ProjectPhase(Base):
    __tablename__ = "project_phases"

    id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    phase_name = Column(Enum(ProjectPhaseEnum), nullable=False)
    planned_start = Column(DateTime)
    planned_end = Column(DateTime)

    project = relationship("Project", back_populates="phases")
    materials = relationship("MaterialLineItem", back_populates="phase")


class CrewProfile(Base):
    __tablename__ = "crew_profiles"

    id = Column(String, primary_key=True, default=gen_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    name = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    avg_experience_years = Column(Float, nullable=False)
    experience_index = Column(Float)  # computed: 0-1 normalized score

    company = relationship("Company", back_populates="crew_profiles")
    materials = relationship("MaterialLineItem", back_populates="crew_profile")


class MaterialLineItem(Base):
    __tablename__ = "material_line_items"

    id = Column(String, primary_key=True, default=gen_uuid)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    phase_id = Column(String, ForeignKey("project_phases.id"))
    crew_profile_id = Column(String, ForeignKey("crew_profiles.id"))
    material_type = Column(Enum(MaterialTypeEnum), nullable=False)
    estimated_quantity = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    unit_price = Column(Float)

    project = relationship("Project", back_populates="materials")
    phase = relationship("ProjectPhase", back_populates="materials")
    crew_profile = relationship("CrewProfile", back_populates="materials")
    prediction = relationship("WastePrediction", back_populates="material", uselist=False)
    actual = relationship("WasteActual", back_populates="material", uselist=False)


class WastePrediction(Base):
    __tablename__ = "waste_predictions"

    id = Column(String, primary_key=True, default=gen_uuid)
    material_line_item_id = Column(String, ForeignKey("material_line_items.id"), nullable=False)
    predicted_waste_pct = Column(Float, nullable=False)
    ci_low = Column(Float, nullable=False)
    ci_high = Column(Float, nullable=False)
    recommended_order_qty = Column(Float, nullable=False)
    model_version = Column(String)
    prediction_date = Column(DateTime, default=datetime.utcnow)
    feature_snapshot = Column(JSON)  # stores all signal values used
    shap_values = Column(JSON)       # top feature contributions

    material = relationship("MaterialLineItem", back_populates="prediction")


class WasteActual(Base):
    __tablename__ = "waste_actuals"

    id = Column(String, primary_key=True, default=gen_uuid)
    material_line_item_id = Column(String, ForeignKey("material_line_items.id"), nullable=False)
    actual_waste_qty = Column(Float, nullable=False)
    actual_waste_pct = Column(Float)  # computed on save
    recorded_by = Column(String)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)

    material = relationship("MaterialLineItem", back_populates="actual")
    feedback_log = relationship("ModelFeedbackLog", back_populates="actual", uselist=False)


class ModelFeedbackLog(Base):
    __tablename__ = "model_feedback_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    company_id = Column(String, ForeignKey("companies.id"), nullable=False)
    prediction_id = Column(String, ForeignKey("waste_predictions.id"))
    actual_id = Column(String, ForeignKey("waste_actuals.id"))
    delta_pct = Column(Float)
    used_in_retraining = Column(Boolean, default=False)
    retrain_date = Column(DateTime)

    actual = relationship("WasteActual", back_populates="feedback_log")
