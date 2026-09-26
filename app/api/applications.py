from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import Application, Job, ActionRequired

r = APIRouter(prefix="/api/user/applications", tags=["applications"])

TRACKED_STATUSES = {
    "DISCOVERED","MATCHED","READY","IN_PROGRESS","SUBMITTED",
    "ACTION_REQUIRED","BLOCKED","FAILED","RETRY","NOT_A_MATCH","DUPLICATE","EXPIRED"
}

def serialize(application: Application):
    job = application.job
    return {
        "id": application.id, "user_id": application.user_id, "job_id": application.job_id,
        "status": application.status, "match_score": application.match_score,
        "external_url": application.external_url, "provider": application.provider,
        "attempt_count": application.attempt_count, "max_attempts": application.max_attempts,
        "last_error": application.last_error, "next_retry_at": application.next_retry_at,
        "submitted_at": application.submitted_at, "started_at": application.started_at,
        "created_at": application.created_at, "updated_at": application.updated_at,
        "job": {
            "id": job.id, "company": job.company, "title": job.title,
            "description": job.description, "location": job.location,
            "job_type": job.job_type, "remote": job.remote,
            "salary_min": job.salary_min, "salary_max": job.salary_max,
            "url": job.url, "source": job.source, "posted_at": job.posted_at,
        },
    }

@r.get("")
def apps(db: Session = Depends(get_db), u=Depends(active_user)):
    return [serialize(x) for x in db.query(Application).filter_by(user_id=u.id)
            .order_by(Application.id.desc()).all()]

@r.get("/{application_id}")
def get_application(application_id: int, db: Session = Depends(get_db), u=Depends(active_user)):
    application = db.query(Application).filter_by(id=application_id, user_id=u.id).first()
    if not application:
        raise HTTPException(404, "Application not found")
    return serialize(application)

@r.post("/jobs/{job_id}")
def apply(job_id: int, db: Session = Depends(get_db), u=Depends(active_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    existing = db.query(Application).filter_by(user_id=u.id, job_id=job.id).first()
    if existing:
        return serialize(existing)
    application = Application(
        user_id=u.id, job_id=job.id, status="READY", match_score=0,
        external_url=job.url, provider=(job.source or "").upper(),
    )
    db.add(application); db.commit(); db.refresh(application)
    return serialize(application)

@r.post("/{application_id}/retry")
def retry_application(application_id: int, db: Session = Depends(get_db), u=Depends(active_user)):
    application = db.query(Application).filter_by(id=application_id, user_id=u.id).first()
    if not application:
        raise HTTPException(404, "Application not found")
    if application.status not in {"FAILED", "RETRY"}:
        raise HTTPException(400, "Only failed applications can be retried")
    if application.attempt_count >= application.max_attempts:
        application.status = "BLOCKED"
        application.last_error = "Maximum retry attempts reached"
        db.commit()
        raise HTTPException(409, "Maximum retry attempts reached")
    application.status = "READY"
    application.next_retry_at = None
    application.last_error = None
    db.commit()
    db.refresh(application)
    return serialize(application)
