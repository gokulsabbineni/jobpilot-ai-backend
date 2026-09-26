import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx
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

    if preferences.job_types and job.job_type and job.job_type not in preferences.job_types:
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

    if preferences.salary_min and job.salary_max and job.salary_max < preferences.salary_min:
        return False
    if preferences.salary_max and job.salary_min and job.salary_min > preferences.salary_max:
        return False

    if preferences.job_titles:
        title = job.title.lower()
        if not any(requested.lower() in title or title in requested.lower()
                   for requested in preferences.job_titles):
            return False

    return True


def configured_sources() -> list[dict[str, Any]]:
    raw = os.getenv("JOB_SOURCES", "[]")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(500, "JOB_SOURCES is invalid JSON") from exc
    if not isinstance(value, list):
        raise HTTPException(500, "JOB_SOURCES must be a JSON array")
    return value


async def discover_jobs() -> tuple[list[dict[str, Any]], list[str]]:
    sources = configured_sources()
    jobs: list[dict[str, Any]] = []
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for source in sources:
            provider = str(source.get("provider", "")).lower()
            try:
                if provider == "greenhouse":
                    jobs.extend(await fetch_greenhouse(client, str(source["board"])))
                elif provider == "lever":
                    jobs.extend(await fetch_lever(client, str(source["site"])))
                else:
                    errors.append(f"Unsupported provider: {provider}")
            except Exception as exc:
                errors.append(
                    f"{provider}:{source.get('board') or source.get('site')}: {exc}"
                )

    return jobs, errors


async def fetch_greenhouse(client: httpx.AsyncClient, board: str) -> list[dict[str, Any]]:
    response = await client.get(
        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
        params={"content": "true"},
    )
    response.raise_for_status()

    result = []
    for item in response.json().get("jobs", []):
        location = ((item.get("location") or {}).get("name") or "").strip()
        text = f"{item.get('title', '')} {location} {item.get('content', '')}"
        result.append({
            "company": board,
            "title": item.get("title") or "Untitled",
            "description": item.get("content") or "",
            "location": location or "United States",
            "job_type": infer_job_type(text),
            "remote": "remote" in text.lower(),
            "url": item.get("absolute_url"),
            "source": "GREENHOUSE",
            "posted_at": parse_datetime(item.get("updated_at")),
        })
    return [job for job in result if job["url"]]


async def fetch_lever(client: httpx.AsyncClient, site: str) -> list[dict[str, Any]]:
    response = await client.get(
        f"https://api.lever.co/v0/postings/{site}",
        params={"mode": "json", "limit": 100},
    )
    response.raise_for_status()

    result = []
    for item in response.json():
        categories = item.get("categories") or {}
        location = categories.get("location") or ""
        description = item.get("descriptionPlain") or item.get("description") or ""
        title = item.get("text") or "Untitled"
        text = f"{title} {location} {description}"
        result.append({
            "company": site,
            "title": title,
            "description": description,
            "location": location or "United States",
            "job_type": infer_job_type(text),
            "remote": "remote" in text.lower(),
            "url": item.get("hostedUrl") or item.get("applyUrl"),
            "source": "LEVER",
            "posted_at": parse_datetime(item.get("createdAt")),
        })
    return [job for job in result if job["url"]]


def infer_job_type(text: str) -> str:
    value = text.lower()
    if "contract" in value or "contractor" in value:
        return "CONTRACT"
    if "intern" in value or "internship" in value:
        return "INTERNSHIP"
    if "part-time" in value or "part time" in value:
        return "PART_TIME"
    return "FULL_TIME"


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def upsert_job(db: Session, payload: dict[str, Any]) -> Job:
    existing = db.query(Job).filter(Job.url == payload["url"]).first()
    if existing:
        existing.company = payload["company"]
        existing.title = payload["title"]
        existing.description = payload["description"]
        existing.location = payload["location"]
        existing.job_type = payload["job_type"]
        existing.remote = payload["remote"]
        existing.source = payload["source"]
        existing.posted_at = payload["posted_at"]
        return existing

    job = Job(**payload)
    db.add(job)
    db.flush()
    return job


@r.get("")
def status(db: Session = Depends(get_db), u=Depends(active_user)):
    return out(
        db.query(AgentRun)
        .filter_by(user_id=u.id)
        .order_by(AgentRun.id.desc())
        .first()
    )


@r.post("/start")
async def start(db: Session = Depends(get_db), u=Depends(active_user)):
    if not u.resume:
        raise HTTPException(400, "Upload a resume before starting the agent")

    discovered, source_errors = await discover_jobs()

    for payload in discovered:
        upsert_job(db, payload)

    db.flush()

    jobs = (
        db.query(Job)
        .order_by(Job.posted_at.desc(), Job.created_at.desc())
        .limit(1000)
        .all()
    )
    matching_jobs = [job for job in jobs if matches_preferences(job, u.preferences)]

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

        db.add(Application(
            user_id=u.id,
            job_id=job.id,
            status="READY",
            match_score=70,
            external_url=job.url,
        ))
        run.applications_made += 1

    run.status = "COMPLETED" if not source_errors else "COMPLETED_WITH_WARNINGS"
    run.completed_at = datetime.now(timezone.utc)
    run.error_message = "; ".join(source_errors) if source_errors else None
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
