from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import AgentRun, Application, Job
from app.services.application_runner import run_application
from app.services.live_discovery import discover_for_query

r = APIRouter(prefix="/api/user/agent", tags=["agent"])


def out(run):
    return {
        "id": run.id if run else None, "status": run.status if run else "IDLE",
        "jobs_scanned": run.jobs_scanned if run else 0, "applications_made": run.applications_made if run else 0,
        "applications_submitted": run.applications_submitted if run else 0,
        "applications_action_required": run.applications_action_required if run else 0,
        "applications_failed": run.applications_failed if run else 0,
        "started_at": run.started_at if run else None, "completed_at": run.completed_at if run else None,
        "error_message": run.error_message if run else None,
    }


def _norm(value):
    return " ".join(str(value or "").lower().replace("-", " ").replace("_", " ").split())

def matches_preferences(job, preferences):
    if not preferences:
        return True
    job_type = _norm(job.job_type)
    if preferences.job_types:
        wanted = {_norm(x) for x in preferences.job_types}
        if job_type and not any(w == job_type for w in wanted):
            return False
    if preferences.locations:
        hay = _norm(job.location)
        wanted = [_norm(x) for x in preferences.locations]
        if not any(x in hay for x in wanted) and not job.remote:
            return False
    remote_pref = _norm(preferences.remote_preference)
    if remote_pref in {"remote", "remote only"} and not job.remote:
        return False
    if remote_pref in {"onsite", "on site"} and job.remote:
        return False
    if preferences.salary_min and job.salary_max and job.salary_max < preferences.salary_min:
        return False
    if preferences.salary_max and job.salary_min and job.salary_min > preferences.salary_max:
        return False
    if preferences.job_titles:
        title = _norm(job.title)
        requested = [_norm(x) for x in preferences.job_titles if _norm(x)]
        if requested and not any(wanted in title or title in wanted or any(word in title.split() for word in wanted.split() if len(word) > 2) for wanted in requested):
            return False
    return True

@r.get("")
def status(db: Session = Depends(get_db), u=Depends(active_user)):
    return out(db.query(AgentRun).filter_by(user_id=u.id).order_by(AgentRun.id.desc()).first())


@r.post("/start")
async def start(db: Session = Depends(get_db), u=Depends(active_user)):
    if not u.resume:
        raise HTTPException(400, "Upload a resume before starting the agent")

    run = AgentRun(user_id=u.id, status="RUNNING", started_at=datetime.now(timezone.utc))
    db.add(run)
    db.flush()
    try:
        search_terms = (u.preferences.job_titles if u.preferences and u.preferences.job_titles else [])
        search = " ".join(search_terms[:3]) if search_terms else None
        discovery = await discover_for_query(db, search=search, limit=100)
        db.flush()

        jobs = db.query(Job).order_by(Job.posted_at.desc().nullslast(), Job.created_at.desc()).limit(5000).all()
        matching = [job for job in jobs if matches_preferences(job, u.preferences)]
        if not matching and search:
            discovered_ids = set(discovery.get("scores", {}).keys())
            matching = [job for job in jobs if str(job.id) in discovered_ids]
        run.jobs_scanned = len(jobs)

        # Free-tier safe cap: submit a small batch synchronously; leave the rest READY
        # for a future worker/scheduler rather than blocking the web request indefinitely.
        candidates = []
        for job in matching:
            existing = db.query(Application).filter_by(user_id=u.id, job_id=job.id).first()
            if existing:
                continue
            app = Application(
                user_id=u.id, job_id=job.id, status="READY",
                match_score=discovery.get("scores", {}).get(str(job.id), 70),
                external_url=job.url, provider=(job.source or "").upper(),
            )
            db.add(app)
            candidates.append(app)
            run.applications_made += 1
            if len(candidates) >= 10:
                break

        db.flush()
        for app in candidates:
            result = await run_application(db, u, app)
            status_value = getattr(result, "status", None)
            if status_value == "SUBMITTED":
                run.applications_submitted += 1
            elif status_value == "ACTION_REQUIRED":
                run.applications_action_required += 1
            elif status_value in {"FAILED", "RETRY"}:
                run.applications_failed += 1

        run.status = "COMPLETED_WITH_WARNINGS" if discovery.get("errors") else "COMPLETED"
        run.error_message = "; ".join(discovery.get("errors", []))[:4000] if discovery.get("errors") else None
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        return out(run)
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Agent run failed: {str(exc)[:500]}") from exc


@r.post("/pause")
def pause(db: Session = Depends(get_db), u=Depends(active_user)):
    return _change(db, u, "PAUSED")


@r.post("/stop")
def stop(db: Session = Depends(get_db), u=Depends(active_user)):
    return _change(db, u, "STOPPED")


def _change(db, u, status):
    run = db.query(AgentRun).filter_by(user_id=u.id).order_by(AgentRun.id.desc()).first()
    if not run:
        raise HTTPException(404, "No agent run found")
    run.status = status
    db.commit()
    db.refresh(run)
    return out(run)
