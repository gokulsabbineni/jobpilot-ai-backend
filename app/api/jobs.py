from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import Job


r = APIRouter(prefix="/api/user/jobs", tags=["jobs"])


@r.get("")
def jobs(
    search: str | None = Query(None),
    job_type: str | None = Query(None),
    remote: bool | None = Query(None),
    db: Session = Depends(get_db),
    u=Depends(active_user),
):
    query = db.query(Job)

    if search:
        value = f"%{search.strip()}%"
        query = query.filter(
            (Job.title.ilike(value))
            | (Job.company.ilike(value))
            | (Job.location.ilike(value))
        )

    if job_type and job_type != "ALL":
        query = query.filter(Job.job_type == job_type)

    if remote is True:
        query = query.filter(Job.remote.is_(True))

    return query.order_by(Job.created_at.desc()).limit(100).all()


@r.get("/{job_id}")
def job(job_id: int, db: Session = Depends(get_db), u=Depends(active_user)):
    return db.get(Job, job_id)
