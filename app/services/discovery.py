import hashlib
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from sqlalchemy.orm import Session

from app.models import Job, JobDiscovery


TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gh_src", "lever-source", "source", "ref", "referrer",
}


def configured_sources():
    raw = os.getenv("JOB_SOURCES", "[]")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("JOB_SOURCES must be valid JSON") from exc
    if not isinstance(value, list):
        raise ValueError("JOB_SOURCES must be a JSON array")
    return value


def canonicalize_url(url: str) -> str:
    parts = urlsplit((url or "").strip())
    if not parts.scheme or not parts.netloc:
        return url.strip()
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if k.lower() not in TRACKING_PARAMS]
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((
        parts.scheme.lower(),
        parts.netloc.lower(),
        path,
        urlencode(sorted(query)),
        "",
    ))


def fingerprint(payload: dict) -> str:
    provider = str(payload.get("provider") or payload.get("source") or "").upper()
    external_id = str(payload.get("external_id") or "").strip().lower()
    canonical = canonicalize_url(payload.get("url") or "")
    stable = external_id if external_id else canonical
    if not stable:
        stable = "|".join([
            str(payload.get("company") or "").strip().lower(),
            str(payload.get("title") or "").strip().lower(),
            str(payload.get("location") or "").strip().lower(),
        ])
    return hashlib.sha256(f"{provider}|{stable}".encode()).hexdigest()


def parse_datetime(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def utc_datetime(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def infer_job_type(text: str) -> str:
    value = text.lower()
    if "contract" in value or "contractor" in value:
        return "CONTRACT"
    if "intern" in value or "internship" in value:
        return "INTERNSHIP"
    if "part-time" in value or "part time" in value:
        return "PART_TIME"
    return "FULL_TIME"


def normalize(payload: dict) -> dict:
    description = payload.get("description") or ""
    location = (payload.get("location") or "United States").strip()
    title = (payload.get("title") or "Untitled").strip()
    text = f"{title} {location} {description}"
    url = canonicalize_url(payload.get("url") or "")
    explicit_remote = payload.get("remote")
    if explicit_remote is None:
        explicit_remote = "remote" in location.lower()
    return {
        "company": (payload.get("company") or "Unknown Company").strip(),
        "title": title,
        "description": description,
        "location": location,
        "job_type": payload.get("job_type") or infer_job_type(text),
        "remote": bool(explicit_remote),
        "salary_min": payload.get("salary_min"),
        "salary_max": payload.get("salary_max"),
        "url": url,
        "source": str(payload.get("provider") or payload.get("source") or "UNKNOWN").upper(),
        "posted_at": parse_datetime(payload.get("posted_at")) or parse_datetime(payload.get("first_seen_at")),
        "external_id": payload.get("external_id"),
        "source_url": payload.get("source_url") or url,
        "raw_data": payload.get("raw_data") or {},
    }


def upsert_discovery(db: Session, payload: dict) -> Job:
    item = normalize(payload)
    if not item["url"]:
        raise ValueError("Job has no application URL")

    fp = fingerprint(item)
    discovery = db.query(JobDiscovery).filter_by(fingerprint=fp).first()
    if discovery:
        job = db.get(Job, discovery.job_id)
        if job:
            for key in ("company", "title", "description", "location", "job_type",
                        "remote", "salary_min", "salary_max", "url", "source"):
                setattr(job, key, item[key])
            existing_posted_at = utc_datetime(job.posted_at)
            incoming_posted_at = utc_datetime(item["posted_at"])
            if incoming_posted_at is not None and (
                existing_posted_at is None or incoming_posted_at > existing_posted_at
            ):
                job.posted_at = incoming_posted_at
            discovery.last_seen_at = datetime.now(timezone.utc)
            discovery.last_checked_at = datetime.now(timezone.utc)
            discovery.discovery_count += 1
            discovery.active = True
            discovery.crawl_error = None
            discovery.raw_data = item["raw_data"]
            return job

    # Cross-provider duplicate detection. Keep one Job record but preserve
    # provider-specific discovery provenance in JobDiscovery.
    existing = db.query(Job).filter(Job.url == item["url"]).first()
    if not existing:
        existing = db.query(Job).filter(
            Job.company.ilike(item["company"]),
            Job.title.ilike(item["title"]),
            Job.location.ilike(item["location"]),
        ).first()

    if existing:
        discovery = JobDiscovery(
            job_id=existing.id,
            canonical_url=item["url"],
            fingerprint=fp,
            external_id=item["external_id"],
            provider=item["source"],
            source_url=item["source_url"],
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            last_checked_at=datetime.now(timezone.utc),
            raw_data=item["raw_data"],
        )
        db.add(discovery)
        db.flush()
        return existing

    job = Job(
        company=item["company"], title=item["title"], description=item["description"],
        location=item["location"], job_type=item["job_type"], remote=item["remote"],
        salary_min=item["salary_min"], salary_max=item["salary_max"], url=item["url"],
        source=item["source"], posted_at=item["posted_at"],
    )
    db.add(job)
    db.flush()
    db.add(JobDiscovery(
        job_id=job.id, canonical_url=item["url"], fingerprint=fp,
        external_id=item["external_id"], provider=item["source"],
        source_url=item["source_url"], first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc), last_checked_at=datetime.now(timezone.utc),
        raw_data=item["raw_data"],
    ))
    return job


async def fetch_greenhouse(client, board):
    response = await client.get(
        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
        params={"content": "true"},
    )
    response.raise_for_status()
    result = []
    for item in response.json().get("jobs", []):
        location = ((item.get("location") or {}).get("name") or "").strip()
        result.append({
            "provider": "GREENHOUSE", "external_id": str(item.get("id") or ""),
            "company": board, "title": item.get("title"), "description": item.get("content"),
            "location": location, "url": item.get("absolute_url"),
            "posted_at": parse_datetime(item.get("updated_at")),
            "source_url": f"https://boards.greenhouse.io/{board}",
            "raw_data": item,
        })
    return result


async def fetch_lever(client, site):
    result = []
    skip = 0
    while True:
        response = await client.get(
            f"https://api.lever.co/v0/postings/{site}",
            params={"mode": "json", "limit": 100, "skip": skip},
        )
        response.raise_for_status()
        items = response.json()
        if not items:
            break
        result.extend({
            "provider": "LEVER", "external_id": str(item.get("id") or ""),
            "company": site, "title": item.get("text"), 
            "description": item.get("descriptionPlain") or item.get("description"),
            "location": (item.get("categories") or {}).get("location"),
            "job_type": infer_job_type(json.dumps(item)),
            "remote": "remote" in json.dumps(item).lower(),
            "url": item.get("hostedUrl") or item.get("applyUrl"),
            "posted_at": parse_datetime(item.get("createdAt")),
            "source_url": f"https://jobs.lever.co/{site}",
            "raw_data": item,
        } for item in items)
        if len(items) < 100:
            break
        skip += len(items)
        if skip > 10000:
            break
    return result


async def fetch_ashby(client, board):
    response = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
    response.raise_for_status()
    data = response.json()
    result = []
    for item in data.get("jobs", []):
        result.append({
            "provider": "ASHBY", "external_id": str(item.get("jobUrl") or ""),
            "company": data.get("companyName") or board, "title": item.get("title"),
            "description": item.get("descriptionPlain") or item.get("descriptionHtml"),
            "location": item.get("location"), "remote": str(item.get("workplaceType", "")).lower() == "remote",
            "url": item.get("jobUrl") or item.get("applyUrl"),
            "posted_at": parse_datetime(item.get("publishedAt")),
            "source_url": f"https://jobs.ashbyhq.com/{board}",
            "raw_data": item,
        })
    return result


async def fetch_smartrecruiters(client, company, search=None, limit=100):
    items = []
    offset = 0
    while True:
        params = {"limit": min(limit, 100), "offset": offset}
        if search:
            params["q"] = search[:100]
        response = await client.get(
            f"https://api.smartrecruiters.com/v1/companies/{company}/postings",
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        page = data.get("content", [])
        if not page:
            break
        for item in page:
            loc = item.get("location") or {}
            location = ", ".join(str(x) for x in [loc.get("city"), loc.get("region"), loc.get("country")] if x)
            items.append({
                "provider": "SMARTRECRUITERS",
                "external_id": str(item.get("id") or item.get("uuid") or ""),
                "company": (item.get("company") or {}).get("name") or company,
                "title": item.get("name"),
                "description": (item.get("jobAd") or {}).get("jobDescription") or "",
                "location": location or "United States",
                "job_type": infer_job_type(str((item.get("typeOfEmployment") or {}).get("label") or "")),
                "remote": bool(loc.get("remote")) or bool(loc.get("hybrid")),
                "url": item.get("applyUrl") or item.get("ref"),
                "posted_at": parse_datetime(item.get("releasedDate")),
                "source_url": f"https://careers.smartrecruiters.com/{company}",
                "raw_data": item,
            })
        offset += len(page)
        if len(page) < params["limit"] or offset >= int(data.get("totalFound", 0) or 0) or offset >= 1000:
            break
    return items


async def fetch_json_api(client, url):
    response = await client.get(url)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else data.get("jobs", [])


async def discover_from_sources(db: Session, sources: list[dict]):
    discovered = 0
    errors = []
    by_job = {}
    async with httpx.AsyncClient(timeout=45, follow_redirects=True,
                                 headers={"User-Agent": "JobPilotAI/1.0 (+job discovery)"}) as client:
        for source in sources:
            provider = str(source.get("provider") or "").lower()
            try:
                if provider == "greenhouse":
                    items = await fetch_greenhouse(client, str(source["board"]))
                elif provider == "lever":
                    items = await fetch_lever(client, str(source["site"]))
                elif provider == "ashby":
                    items = await fetch_ashby(client, str(source["board"]))
                elif provider == "smartrecruiters":
                    items = await fetch_smartrecruiters(client, str(source["company"]), source.get("search"))
                elif provider == "career_page":
                    from app.services.career_crawler import crawl
                    items = await crawl(client, str(source["url"]), source.get("search"))
                elif provider == "json":
                    items = await fetch_json_api(client, str(source["url"]))
                else:
                    errors.append(f"Unsupported provider: {provider}")
                    continue
                for item in items:
                    try:
                        job = upsert_discovery(db, item)
                        by_job[str(job.id)] = 75
                        discovered += 1
                    except Exception as exc:
                        errors.append(f"{provider}:job:{exc}")
            except Exception as exc:
                errors.append(f"{provider}:{source.get('board') or source.get('site') or source.get('url')}: {exc}")
    return {"discovered": discovered, "errors": errors, "scores": by_job}
