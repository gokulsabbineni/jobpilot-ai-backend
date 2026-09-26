from fastapi import APIRouter, Depends, Query
from html import unescape
import re
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import Job

r = APIRouter(prefix="/api/user/jobs", tags=["jobs"])


def _query_jobs(db, search=None, company=None, source=None, job_type=None, remote=None, limit=100):
    query = db.query(Job)
    if company:
        query = query.filter(Job.company.ilike(f"%{company.strip()}%"))
    if source and source != "ALL":
        query = query.filter(Job.source.ilike(source.strip()))
    if search:
        value = f"%{search.strip()}%"
        query = query.filter(
            (Job.title.ilike(value)) | (Job.company.ilike(value))
            | (Job.location.ilike(value)) | (Job.description.ilike(value))
        )
    if job_type and job_type != "ALL":
        query = query.filter(Job.job_type == job_type)
    if remote is True:
        query = query.filter(Job.remote.is_(True))
    return query.order_by(Job.posted_at.desc().nullslast(), Job.created_at.desc()).limit(limit).all()


def _plain_description(value):
    if not value:
        return value
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\\s+", " ", unescape(text)).strip()


def _serialize(rows):
    return [{
        "id": x.id, "company": x.company, "title": x.title, "description": _plain_description(x.description),
        "location": x.location, "job_type": x.job_type, "remote": x.remote,
        "salary_min": x.salary_min, "salary_max": x.salary_max, "url": x.url,
        "source": x.source, "posted_at": x.posted_at, "created_at": x.created_at,
    } for x in rows]


@r.get("")
async def jobs(
    search: str | None = Query(None),
    job_type: str | None = Query(None),
    remote: bool | None = Query(None),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    u=Depends(active_user),
):
    # A search is a live discovery request, then the DB is queried for deduped results.
    if search and search.strip():
        from app.services.live_discovery import discover_for_query
        await discover_for_query(db, search=search.strip(), limit=limit)
        db.commit()
    return _serialize(_query_jobs(db, search, job_type=job_type, remote=remote, limit=limit))


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
    from app.services.live_discovery import discover_for_query
    if search:
        await discover_for_query(db, search=search.strip(), limit=limit)
    elif url:
        # URL ingestion remains available for future source adapters.
        from app.services.discovery import discover_from_sources
        await discover_from_sources(db, [{"provider": source or "json", "url": url}])
    db.commit()
    return _serialize(_query_jobs(db, search, company, source, job_type, remote, limit))


@r.get("/{job_id}")
def job(job_id: int, db: Session = Depends(get_db), u=Depends(active_user)):
    return db.get(Job, job_id)
