from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import admin_user
from app.models import (
    ActionRequired,
    AgentRun,
    Application,
    AuditLog,
    User,
    UserPreferences,
)


r = APIRouter(prefix="/api/admin", tags=["admin"])


def audit(db, admin, action, user_id, details=None):
    db.add(
        AuditLog(
            user_id=admin.id,
            action=action,
            resource="user",
            resource_id=str(user_id),
            details=details or {},
        )
    )


def user_summary(user):
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login_at": user.last_login_at,
    }


def application_summary(application):
    job = application.job
    return {
        "id": application.id,
        "user_id": application.user_id,
        "user": user_summary(application.user) if application.user else None,
        "job": (
            {
                "id": job.id,
                "company": job.company,
                "title": job.title,
                "location": job.location,
                "job_type": job.job_type,
                "remote": job.remote,
                "url": job.url,
                "source": job.source,
            }
            if job
            else None
        ),
        "status": application.status,
        "match_score": application.match_score,
        "external_url": application.external_url,
        "submitted_at": application.submitted_at,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
    }


@r.get("/dashboard")
def dashboard(db: Session = Depends(get_db), u=Depends(admin_user)):
    total_users = db.query(User).count()
    active_users = db.query(User).filter_by(status="ACTIVE").count()
    pending = db.query(User).filter_by(status="PENDING_APPROVAL").count()
    total_applications = db.query(Application).count()
    active_agents = db.query(AgentRun).filter(
        AgentRun.status == "RUNNING"
    ).count()

    return {
        "total_users": total_users,
        "pending_approvals": pending,
        "active_users": active_users,
        "total_applications": total_applications,
        "active_agents": active_agents,
    }


@r.get("/users")
def users(db: Session = Depends(get_db), u=Depends(admin_user)):
    return [
        user_summary(user)
        for user in db.query(User).order_by(User.id.desc()).all()
    ]


@r.get("/users/{user_id}")
def user_details(
    user_id: int,
    db: Session = Depends(get_db),
    u=Depends(admin_user),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    applications = user.applications
    actions = [action for action in user.actions if not action.completed]

    return {
        **user_summary(user),
        "application_statistics": {
            "total": len(applications),
            "submitted": sum(x.status == "SUBMITTED" for x in applications),
            "failed": sum(x.status == "FAILED" for x in applications),
            "action_required": len(actions),
        },
        "resume": (
            {
                "id": user.resume.id,
                "file_name": user.resume.file_name,
                "uploaded_at": user.resume.uploaded_at,
            }
            if user.resume
            else None
        ),
        "preferences": (
            {
                "job_types": user.preferences.job_types,
                "job_titles": user.preferences.job_titles,
                "locations": user.preferences.locations,
                "remote_preference": user.preferences.remote_preference,
                "salary_min": user.preferences.salary_min,
                "salary_max": user.preferences.salary_max,
                "sponsorship_required": user.preferences.sponsorship_required,
                "auto_apply": user.preferences.auto_apply,
            }
            if user.preferences
            else None
        ),
    }


@r.get("/approvals")
def approvals(db: Session = Depends(get_db), u=Depends(admin_user)):
    return [
        user_summary(user)
        for user in db.query(User)
        .filter_by(status="PENDING_APPROVAL")
        .order_by(User.created_at.asc())
        .all()
    ]


@r.post("/approvals/{uid}/approve")
def approve(uid: int, db: Session = Depends(get_db), u=Depends(admin_user)):
    user = db.get(User, uid)
    if not user:
        raise HTTPException(404, "User not found")

    user.status = "ACTIVE"
    audit(db, u, "APPROVE_USER", uid)
    db.commit()
    return user_summary(user)


@r.post("/users/{uid}/approve")
def approve_user_again(uid: int, db: Session = Depends(get_db), u=Depends(admin_user)):
    user = db.get(User, uid)
    if not user:
        raise HTTPException(404, "User not found")
    if user.role == "ADMIN":
        raise HTTPException(400, "Admin accounts cannot be changed through user approval.")

    user.status = "ACTIVE"
    audit(db, u, "APPROVE_USER", uid, {"previous_status": "REJECTED"})
    db.commit()
    return user_summary(user)


@r.post("/approvals/{uid}/reject")
def reject(uid: int, db: Session = Depends(get_db), u=Depends(admin_user)):
    user = db.get(User, uid)
    if not user:
        raise HTTPException(404, "User not found")

    user.status = "REJECTED"
    audit(db, u, "REJECT_USER", uid)
    db.commit()
    return user_summary(user)


@r.get("/applications")
def applications(db: Session = Depends(get_db), u=Depends(admin_user)):
    return [
        application_summary(item)
        for item in db.query(Application)
        .order_by(Application.id.desc())
        .all()
    ]


@r.get("/agent-activity")
def activity(db: Session = Depends(get_db), u=Depends(admin_user)):
    return [
        {
            "id": run.id,
            "user_id": run.user_id,
            "status": run.status,
            "jobs_scanned": run.jobs_scanned or 0,
            "applications_made": run.applications_made or 0,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "error_message": run.error_message,
        }
        for run in db.query(AgentRun)
        .order_by(AgentRun.id.desc())
        .all()
    ]


@r.get("/audit-logs")
def logs(db: Session = Depends(get_db), u=Depends(admin_user)):
    return db.query(AuditLog).order_by(AuditLog.id.desc()).limit(500).all()


@r.get("/settings")
def get_settings(db: Session = Depends(get_db), u=Depends(admin_user)):
    defaults = {
        "agent_enabled": True,
        "auto_apply_enabled": False,
        "maintenance_mode": False,
        "max_applications_per_run": 25,
    }

    return defaults


@r.put("/settings")
def update_settings(payload: dict, db: Session = Depends(get_db), u=Depends(admin_user)):
    audit(
        db,
        u,
        "UPDATE_SYSTEM_SETTINGS",
        u.id,
        {"settings": payload},
    )
    db.commit()
    return payload
