from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.api.routes.auth import get_current_user
from app.models.db_models import (
    User, Project, ProjectPhase, MaterialLineItem, CrewProfile
)
from app.models.schemas import ProjectCreate, ProjectOut, CrewProfileCreate, CrewProfileOut

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("/", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return (
        db.query(Project)
        .filter(Project.company_id == current_user.company_id)
        .order_by(Project.created_at.desc())
        .all()
    )


@router.post("/", response_model=ProjectOut)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = Project(
        company_id=current_user.company_id,
        name=payload.name,
        type=payload.type,
        location=payload.location,
        area_sqm=payload.area_sqm,
        start_date=payload.start_date,
    )
    db.add(project)
    db.flush()

    # Create phases
    phase_map = {}
    for p in payload.phases:
        phase = ProjectPhase(
            project_id=project.id,
            phase_name=p.phase_name,
            planned_start=p.planned_start,
            planned_end=p.planned_end,
        )
        db.add(phase)
        db.flush()
        phase_map[p.phase_name] = phase.id

    # Create material line items
    for m in payload.materials:
        phase_id = phase_map.get(m.phase_name) if m.phase_name else None
        mat = MaterialLineItem(
            project_id=project.id,
            phase_id=phase_id,
            crew_profile_id=m.crew_profile_id,
            material_type=m.material_type,
            estimated_quantity=m.estimated_quantity,
            unit=m.unit,
            unit_price=m.unit_price,
        )
        db.add(mat)

    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
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
    return project


# --- Crew Profiles ---

@router.get("/crews/list", response_model=List[CrewProfileOut])
def list_crews(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(CrewProfile).filter(CrewProfile.company_id == current_user.company_id).all()


@router.post("/crews/", response_model=CrewProfileOut)
def create_crew(
    payload: CrewProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.ml.features import compute_experience_index
    crew = CrewProfile(
        company_id=current_user.company_id,
        name=payload.name,
        size=payload.size,
        avg_experience_years=payload.avg_experience_years,
        experience_index=compute_experience_index(payload.avg_experience_years),
    )
    db.add(crew)
    db.commit()
    db.refresh(crew)
    return crew
