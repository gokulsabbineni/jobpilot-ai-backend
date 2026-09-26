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


@r.get("/discover")
async def discover(
    url: str | None = Query(None),
    company: str | None = Query(None),
    source: str | None = Query(None),
    search: str | None = Query(None),
    job_type: str | None = Query(None),
    remote: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    u=Depends(active_user),
):
    from app.services.discovery import discover_from_sources
    if url:
        result = await discover_from_sources(db, [{"url": url}])
        db.commit()
    query = db.query(Job)
    if company:
        query = query.filter(Job.company.ilike(f"%{company.strip()}%"))
    if source and source != "ALL":
        query = query.filter(Job.source.ilike(source.strip()))
    if search:
        value=f"%{search.strip()}%"
        query=query.filter((Job.title.ilike(value)) | (Job.company.ilike(value)) | (Job.location.ilike(value)) | (Job.description.ilike(value)))
    if job_type and job_type != "ALL":
        query=query.filter(Job.job_type==job_type)
    if remote is True:
        query=query.filter(Job.remote.is_(True))
    rows=query.order_by(Job.posted_at.desc().nullslast(),Job.created_at.desc()).limit(limit).all()
    return [{"id":x.id,"company":x.company,"title":x.title,"description":x.description,"location":x.location,"job_type":x.job_type,"remote":x.remote,"salary_min":x.salary_min,"salary_max":x.salary_max,"url":x.url,"source":x.source,"posted_at":x.posted_at,"created_at":x.created_at} for x in rows]
