from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import Application, Job


r = APIRouter(prefix="/api/user/applications", tags=["applications"])


def serialize(application: Application):
    job = application.job
    return {
        "id": application.id,
        "user_id": application.user_id,
        "job_id": application.job_id,
        "status": application.status,
        "match_score": application.match_score,
        "external_url": application.external_url,
        "submitted_at": application.submitted_at,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
        "job": {
            "id": job.id,
            "company": job.company,
            "title": job.title,
            "description": job.description,
            "location": job.location,
            "job_type": job.job_type,
            "remote": job.remote,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "url": job.url,
            "source": job.source,
            "posted_at": job.posted_at,
        },
    }


@r.get("")
def apps(db: Session = Depends(get_db), u=Depends(active_user)):
    return [
        serialize(x)
        for x in db.query(Application)
        .filter_by(user_id=u.id)
        .order_by(Application.id.desc())
        .all()
    ]


@r.post("/jobs/{job_id}")
def apply(job_id: int, db: Session = Depends(get_db), u=Depends(active_user)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    existing = (
        db.query(Application)
        .filter_by(user_id=u.id, job_id=job.id)
        .first()
    )
    if existing:
        return serialize(existing)

    application = Application(
        user_id=u.id,
        job_id=job.id,
        status="READY",
        match_score=0,
        external_url=job.url,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return serialize(application)
