from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.schemas import Preferences
from app.models import User, UserPreferences, Job


r = APIRouter(prefix="/api/user", tags=["user"])


class ProfileUpdate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


@r.get("/profile")
def profile(u=Depends(active_user)):
    return {
        "id": u.id,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "email": u.email,
        "role": u.role,
        "status": u.status,
    }


@r.put("/profile")
def update_profile(
    p: ProfileUpdate,
    db: Session = Depends(get_db),
    u=Depends(active_user),
):
    u.first_name = p.first_name.strip()
    u.last_name = p.last_name.strip()
    db.commit()
    db.refresh(u)
    return {
        "id": u.id,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "email": u.email,
        "role": u.role,
        "status": u.status,
    }


@r.get("/preferences")
def prefs(db: Session = Depends(get_db), u=Depends(active_user)):
    return db.query(UserPreferences).filter_by(user_id=u.id).first()


@r.put("/preferences")
def set_prefs(p: Preferences, db: Session = Depends(get_db), u=Depends(active_user)):
    x = db.query(UserPreferences).filter_by(user_id=u.id).first()
    if x is None:
        x = UserPreferences(user_id=u.id)
        db.add(x)
    for k, v in p.model_dump().items():
        setattr(x, k, v)
    db.commit()
    db.refresh(x)
    return x


@r.get("/dashboard")
def dashboard(db: Session = Depends(get_db), u=Depends(active_user)):
    applications = list(u.applications)
    return {
        "user": {
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
            "status": u.status,
        },
        "resume": {
            "uploaded": bool(u.resume),
            "file_name": u.resume.file_name if u.resume else None,
            "uploaded_at": u.resume.uploaded_at if u.resume else None,
        },
        "preferences": {
            "configured": bool(
                u.preferences
                and (
                    u.preferences.job_types
                    or u.preferences.job_titles
                    or u.preferences.locations
                )
            ),
            "job_types": u.preferences.job_types if u.preferences else [],
            "job_titles": u.preferences.job_titles if u.preferences else [],
            "locations": u.preferences.locations if u.preferences else [],
            "remote_preference": u.preferences.remote_preference if u.preferences else "ANY",
            "salary_min": u.preferences.salary_min if u.preferences else None,
            "salary_max": u.preferences.salary_max if u.preferences else None,
            "sponsorship_required": u.preferences.sponsorship_required if u.preferences else False,
            "auto_apply": u.preferences.auto_apply if u.preferences else False,
        },
        "applications": {
            "total": len(applications),
            "submitted": sum(a.status == "SUBMITTED" for a in applications),
            "in_progress": sum(a.status in {"READY", "IN_PROGRESS"} for a in applications),
            "action_required": sum(not a.completed for a in u.actions if a.completed is False),
            "failed": sum(a.status == "FAILED" for a in applications),
        },
        "agent": {
            "status": u.agent_runs[-1].status if u.agent_runs else "IDLE",
            "jobs_scanned": u.agent_runs[-1].jobs_scanned if u.agent_runs else 0,
            "applications_made": u.agent_runs[-1].applications_made if u.agent_runs else 0,
            "started_at": u.agent_runs[-1].started_at if u.agent_runs else None,
            "completed_at": u.agent_runs[-1].completed_at if u.agent_runs else None,
            "error_message": u.agent_runs[-1].error_message if u.agent_runs else None,
        },
    }
