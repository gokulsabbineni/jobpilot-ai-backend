import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.config import settings
from sqlalchemy.orm import Session

, get_db
from app.deps import active_user
from app.models import AgentRun, Application, Job, User
from app.services.agent_access import get_or_create_entitlement, get_usage, capabilities
from app.services.application_runner import run_application
from app.services.live_discovery import discover_for_query
from app.db import SessionLocal


r = APIRouter(prefix="/api/user/agent", tags=["agent"])

_agent_tasks = {}

def get_session():
    return SessionLocal()


def out(run):
    return {
        "id": run.id if run else None,
        "status": run.status if run else "IDLE",
        "jobs_scanned": run.jobs_scanned if run else 0,
        "applications_made": run.applications_made if run else 0,
        "applications_submitted": run.applications_submitted if run else 0,
        "applications_action_required": run.applications_action_required if run else 0,
        "applications_failed": run.applications_failed if run else 0,
        "started_at": run.started_at if run else None,
        "completed_at": run.completed_at if run else None,
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
        if requested and not any(
            wanted in title
            or title in wanted
            or any(word in title.split() for word in wanted.split() if len(word) > 2)
            for wanted in requested
        ):
            return False

    return True


def _job_recency_key(job):
    """
    Application priority is explicitly driven by posting recency.

    Jobs with a known posting timestamp always come before jobs without one.
    created_at is only a fallback when the source did not provide posted_at.
    The timestamp is normalized to UTC so mixed source timezone formats cannot
    change the ordering or cause comparison errors.
    """
    posted_at = job.posted_at
    if posted_at is not None:
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)
        else:
            posted_at = posted_at.astimezone(timezone.utc)
        return (1, posted_at)

    created_at = job.created_at
    if created_at is not None:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = created_at.astimezone(timezone.utc)
        return (0, created_at)

    return (0, datetime.min.replace(tzinfo=timezone.utc))


def prioritize_jobs(jobs):
    """
    Newest-first application queue.

    This is intentionally a stable sort: when two jobs have the same
    timestamp, their existing database order is preserved.
    """
    return sorted(jobs, key=_job_recency_key, reverse=True)



async def resume_running_agents():
    """Resume agents that were RUNNING before a backend restart/deploy."""
    db = get_session()
    try:
        runs = (
            db.query(AgentRun)
            .filter(AgentRun.status == "RUNNING")
            .all()
        )
        for run in runs:
            task = _agent_tasks.get(run.user_id)
            if not task or task.done():
                _agent_tasks[run.user_id] = asyncio.create_task(
                    _continuous_loop(run.user_id, run.id)
                )
    finally:
        db.close()

@r.get("")
def status(db: Session = Depends(get_db), u=Depends(active_user)):
    return out(
        db.query(AgentRun)
        .filter_by(user_id=u.id)
        .order_by(AgentRun.id.desc())
        .first()
    )


@r.get("/access")
def access(db: Session = Depends(get_db), u=Depends(active_user)):
    entitlement = get_or_create_entitlement(db, u.id)
    usage = get_usage(db, u.id)
    db.commit()
    return {
        "capabilities": capabilities(entitlement),
        "limits": {
            "daily_application_limit": entitlement.daily_application_limit,
            "daily_discovery_limit": entitlement.daily_discovery_limit,
        },
        "usage": {
            "date": usage.usage_date,
            "discovery_requests": usage.discovery_requests,
            "jobs_discovered": usage.jobs_discovered,
            "pages_crawled": usage.pages_crawled,
            "browser_minutes": usage.browser_minutes,
            "applications_attempted": usage.applications_attempted,
            "applications_submitted": usage.applications_submitted,
            "llm_requests": usage.llm_requests,
        },
    }


async def _run_cycle(user_id: int, run_id: int):
    """Run one discovery/apply cycle for a continuously running agent."""
    db = get_session()
    try:
        u = db.get(User, user_id)
        run = db.get(AgentRun, run_id)
        if not u or not run:
            return False

        entitlement = get_or_create_entitlement(db, u.id)
        usage = get_usage(db, u.id)

        if usage.discovery_requests >= entitlement.daily_discovery_limit:
            # Keep the run active. The continuous loop waits for the next UTC
            # day and then automatically resumes discovery.
            run.status = "RUNNING"
            run.error_message = "Daily discovery limit reached. Waiting for the next daily reset."
            db.commit()
            return True

        search_terms = (
            u.preferences.job_titles
            if u.preferences and u.preferences.job_titles
            else []
        )
        search = " ".join(search_terms[:3]) if search_terms else None

        usage.discovery_requests += 1
        discovery = await discover_for_query(db, search=search, limit=100)
        usage.jobs_discovered += int(discovery.get("discovered", 0) or 0)
        db.flush()

        jobs = db.query(Job).limit(5000).all()
        run.jobs_scanned = len(jobs)

        # Filter first, then rank. Recency is the primary application priority.
        matching = [job for job in jobs if matches_preferences(job, u.preferences)]
        if not matching and search:
            discovered_ids = set(discovery.get("scores", {}).keys())
            matching = [job for job in jobs if str(job.id) in discovered_ids]
        matching = prioritize_jobs(matching)

        remaining = max(
            0,
            entitlement.daily_application_limit - usage.applications_attempted,
        )
        batch_limit = min(10, remaining)

        candidates = []
        for job in matching:
            if len(candidates) >= batch_limit:
                break

            existing = (
                db.query(Application)
                .filter_by(user_id=u.id, job_id=job.id)
                .first()
            )
            if existing:
                continue

            app = Application(
                user_id=u.id,
                job_id=job.id,
                status="READY",
                match_score=discovery.get("scores", {}).get(str(job.id), 70),
                external_url=job.url,
                provider=(job.source or "").upper(),
            )
            db.add(app)
            candidates.append(app)
            run.applications_made += 1

        db.flush()

        if u.preferences and u.preferences.auto_apply:
            for app in candidates:
                # Re-check the run before every application so Stop/Pause takes
                # effect between jobs rather than waiting for the whole batch.
                db.refresh(run)
                if run.status != "RUNNING":
                    db.commit()
                    return run.status == "RUNNING"

                usage.applications_attempted += 1
                result = await run_application(db, u, app)
                status_value = getattr(result, "status", None)

                if status_value == "SUBMITTED":
                    run.applications_submitted += 1
                    usage.applications_submitted += 1
                elif status_value == "ACTION_REQUIRED":
                    run.applications_action_required += 1
                elif status_value in {"FAILED", "RETRY"}:
                    run.applications_failed += 1

        if discovery.get("errors"):
            run.error_message = "; ".join(discovery.get("errors", []))[:4000]
            run.status = "COMPLETED_WITH_WARNINGS"
        else:
            run.error_message = None

        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        run = db.get(AgentRun, run_id)
        if run:
            run.status = "COMPLETED_WITH_WARNINGS"
            run.error_message = f"Cycle failed: {str(exc)[:3500]}"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
        return True
    finally:
        db.close()


async def _continuous_loop(user_id: int, run_id: int):
    """Continuously discover and process newest matching jobs."""
    try:
        while True:
            db = get_session()
            try:
                run = db.get(AgentRun, run_id)
                if not run or run.status != "RUNNING":
                    return
            finally:
                db.close()

            await _run_cycle(user_id, run_id)

            # Wait for the next UTC reset when the daily discovery allowance
            # is exhausted; otherwise use the normal polling interval.
            db = get_session()
            try:
                usage = get_usage(db, user_id)
                entitlement = get_or_create_entitlement(db, user_id)
                wait_seconds = settings.agent_poll_interval_seconds
                if usage.discovery_requests >= entitlement.daily_discovery_limit:
                    now = datetime.now(timezone.utc)
                    next_day = (
                        now.replace(hour=0, minute=0, second=0, microsecond=0)
                        + timedelta(days=1)
                    )
                    wait_seconds = max(1, int((next_day - now).total_seconds()))
            finally:
                db.close()

            db = get_session()
            try:
                run = db.get(AgentRun, run_id)
                if not run or run.status != "RUNNING":
                    return
            finally:
                db.close()

            await asyncio.sleep(wait_seconds)
    except asyncio.CancelledError:
        return


@r.post("/start")
async def start(db: Session = Depends(get_db), u=Depends(active_user)):
    if not u.resume:
        raise HTTPException(400, "Upload a resume before starting the agent")

    entitlement = get_or_create_entitlement(db, u.id)
    usage = get_usage(db, u.id)

    if usage.discovery_requests >= entitlement.daily_discovery_limit:
        raise HTTPException(429, "Daily discovery limit reached. Try again tomorrow.")

    existing = (
        db.query(AgentRun)
        .filter_by(user_id=u.id)
        .order_by(AgentRun.id.desc())
        .first()
    )
    if existing and existing.status == "RUNNING":
        return out(existing)

    run = AgentRun(
        user_id=u.id,
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.flush()
    db.commit()
    db.refresh(run)

    task = _agent_tasks.get(u.id)
    if task and not task.done():
        task.cancel()

    _agent_tasks[u.id] = asyncio.create_task(_continuous_loop(u.id, run.id))

    return out(run)


@r.post("/pause")
def pause(db: Session = Depends(get_db), u=Depends(active_user)):
    result = _change(db, u, "PAUSED")
    task = _agent_tasks.get(u.id)
    if task and not task.done():
        task.cancel()
    return result


@r.post("/stop")
def stop(db: Session = Depends(get_db), u=Depends(active_user)):
    result = _change(db, u, "STOPPED")
    task = _agent_tasks.get(u.id)
    if task and not task.done():
        task.cancel()
    return result


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
