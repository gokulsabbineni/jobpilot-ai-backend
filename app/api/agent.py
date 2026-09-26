from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import active_user
from app.models import AgentRun, Application, Job


r = APIRouter(prefix="/api/user/agent", tags=["agent"])


def out(run):
    return {
        "id": run.id if run else None,
        "status": run.status if run else "IDLE",
        "jobs_scanned": run.jobs_scanned if run else 0,
        "applications_made": run.applications_made if run else 0,
        "started_at": run.started_at if run else None,
        "completed_at": run.completed_at if run else None,
        "error_message": run.error_message if run else None,
    }


def matches_preferences(job: Job, preferences) -> bool:
    if not preferences:
        return True

    if preferences.job_types and job.job_type:
        if job.job_type not in preferences.job_types:
            return False

    if preferences.locations:
        haystack = (job.location or "").lower()
        if not any(location.lower() in haystack for location in preferences.locations):
            if not job.remote:
                return False

    if preferences.remote_preference == "REMOTE" and not job.remote:
        return False

    if preferences.remote_preference == "ONSITE" and job.remote:
        return False

    if preferences.salary_min and job.salary_max:
        if job.salary_max < preferences.salary_min:
            return False

    if preferences.salary_max and job.salary_min:
        if job.salary_min > preferences.salary_max:
            return False

    if preferences.job_titles:
        title = job.title.lower()
        if not any(
            requested.lower() in title or title in requested.lower()
            for requested in preferences.job_titles
        ):
            return False

    return True


@r.get("")
def status(db: Session = Depends(get_db), u=Depends(active_user)):
    return out(
        db.query(AgentRun)
        .filter_by(user_id=u.id)
        .order_by(AgentRun.id.desc())
        .first()
    )


@r.post("/start")
def start(db: Session = Depends(get_db), u=Depends(active_user)):
    if not u.resume:
        raise HTTPException(400, "Upload a resume before starting the agent")

    preferences = u.preferences
    jobs = db.query(Job).order_by(Job.created_at.desc()).limit(100).all()
    matching_jobs = [job for job in jobs if matches_preferences(job, preferences)]

    run = AgentRun(
        user_id=u.id,
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.flush()

    run.jobs_scanned = len(jobs)

    for job in matching_jobs:
        existing = (
            db.query(Application)
            .filter_by(user_id=u.id, job_id=job.id)
            .first()
        )
        if existing:
            continue

        db.add(
            Application(
                user_id=u.id,
                job_id=job.id,
                status="READY",
                match_score=70,
                external_url=job.url,
            )
        )
        run.applications_made += 1

    run.status = "COMPLETED"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return out(run)


@r.post("/pause")
def pause(db: Session = Depends(get_db), u=Depends(active_user)):
    return _change(db, u, "PAUSED")


@r.post("/stop")
def stop(db: Session = Depends(get_db), u=Depends(active_user)):
    return _change(db, u, "STOPPED")


def _change(db, u, status):
    run = (
        db.query(AgentRun)
        .filter_by(user_id=u.id)
        .order_by(AgentRun.id.desc())
        .first()
    )
    if not run:
        raise HTTPException(404, "No agent run found")

    run.status = status
    db.commit()
    db.refresh(run)
    return out(run)
