import httpx
from urllib.parse import quote
from sqlalchemy.orm import Session

from app.services.discovery import upsert_discovery, configured_sources, discover_from_sources
from app.services.agent_access import get_or_create_entitlement
from app.providers.paid import discover_with_apify, discover_with_serp


async def fetch_jobicy(client, search=None, limit=200):
    params = {"count": min(max(limit, 1), 200)}
    if search:
        params["tag"] = search[:50]
    response = await client.get("https://jobicy.com/api/v2/remote-jobs", params=params)
    response.raise_for_status()
    items = response.json().get("jobs", [])
    return [{
        "provider": "JOBICY",
        "external_id": str(x.get("id") or x.get("jobSlug") or ""),
        "company": x.get("companyName"),
        "title": x.get("jobTitle"),
        "description": x.get("jobDescription") or x.get("jobExcerpt"),
        "location": x.get("jobGeo") or "Remote",
        "job_type": "CONTRACT" if "contract" in str(x.get("jobType","")).lower() else "FULL_TIME",
        "remote": True,
        "posted_at": x.get("pubDate") or x.get("date") or x.get("jobDate"),
        "salary_min": x.get("salaryMin"),
        "salary_max": x.get("salaryMax"),
        "url": x.get("url"),
        "source_url": x.get("url"),
        "raw_data": x,
    } for x in items]


async def fetch_remotive(client, search=None, limit=100):
    params = {"limit": min(max(limit, 1), 100)}
    if search:
        params["search"] = search[:100]
    response = await client.get("https://remotive.com/api/remote-jobs", params=params)
    response.raise_for_status()
    items = response.json().get("jobs", [])
    return [{
        "provider": "REMOTIVE",
        "external_id": str(x.get("id") or ""),
        "company": x.get("company_name"),
        "title": x.get("title"),
        "description": x.get("description"),
        "location": x.get("candidate_required_location") or "Remote",
        "job_type": "CONTRACT" if "contract" in str(x.get("job_type","")).lower() else "FULL_TIME",
        "remote": True,
        "posted_at": x.get("publication_date") or x.get("published_at") or x.get("date"),
        "url": x.get("url"),
        "source_url": x.get("url"),
        "raw_data": x,
    } for x in items]



async def fetch_arbeitnow(client, search=None, limit=100):
    response = await client.get(
        "https://www.arbeitnow.com/api/job-board-api",
        params={"search": search[:100]} if search else None,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("data", []) if isinstance(payload, dict) else []
    if search:
        needle = search.lower()
        items = [
            x for x in items
            if needle in str(x.get("title", "")).lower()
            or needle in str(x.get("description", "")).lower()
            or needle in str(x.get("company_name", "")).lower()
        ]
    return [{
        "provider": "ARBEITNOW",
        "external_id": str(x.get("slug") or x.get("id") or ""),
        "company": x.get("company_name"),
        "title": x.get("title"),
        "description": x.get("description"),
        "location": x.get("location") or "Location not specified",
        "job_type": "CONTRACT" if "contract" in str(x.get("job_types", "")).lower() else "FULL_TIME",
        "remote": bool(x.get("remote")),
        "posted_at": x.get("created_at") or x.get("date") or x.get("published_at"),
        "url": x.get("url"),
        "source_url": x.get("url"),
        "raw_data": x,
    } for x in items[:limit]]


async def fetch_himalayas(client, search=None, limit=100):
    params = {"limit": min(max(limit, 1), 100)}
    if search:
        params["q"] = search[:100]
    params["sort"] = "recent"
    response = await client.get(
        "https://himalayas.app/jobs/api/search",
        params=params,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("jobs", []) if isinstance(payload, dict) else []
    return [{
        "provider": "HIMALAYAS",
        "external_id": str(x.get("id") or x.get("slug") or ""),
        "company": x.get("companyName") or x.get("company"),
        "title": x.get("title"),
        "description": x.get("description"),
        "location": x.get("location") or "Remote",
        "job_type": "CONTRACT" if "contract" in str(x.get("employmentType", "")).lower() else "FULL_TIME",
        "remote": bool(x.get("remote", True)),
        "salary_min": x.get("salaryMin"),
        "salary_max": x.get("salaryMax"),
        "url": x.get("applicationLink") or x.get("url"),
        "source_url": x.get("applicationLink") or x.get("url"),
        "raw_data": x,
    } for x in items[:limit]]




async def fetch_job_opportunities(client, search=None, limit=50):
    params = {"limit": min(max(limit, 1), 50), "include_description": "true"}
    if search:
        params["q"] = search[:100]
    response = await client.get(
        "https://api.jobopportunitiesapi.org/public/jobs",
        params=params,
    )
    response.raise_for_status()
    payload = response.json()
    items = payload.get("data", []) if isinstance(payload, dict) else []
    return [{
        "provider": "JOB_OPPORTUNITIES_API",
        "external_id": str(x.get("id") or x.get("slug") or ""),
        "company": x.get("company"),
        "title": x.get("title"),
        "description": x.get("description"),
        "location": x.get("location") or x.get("city") or "Location not specified",
        "job_type": str(x.get("employment_type") or "FULL_TIME").upper().replace(" ", "_"),
        "remote": str(x.get("remote") or "").lower() == "remote",
        "posted_at": x.get("posted_at") or x.get("first_seen_at"),
        "url": x.get("apply_url"),
        "source_url": x.get("apply_url"),
        "raw_data": x,
    } for x in items]


async def discover_for_query(db: Session, search=None, limit=200, user_id=None):
    result = {"discovered": 0, "errors": [], "scores": {}}
    sources = configured_sources()
    entitlement = get_or_create_entitlement(db, user_id) if user_id else None
    # Sources can be supplied through JOB_SOURCES without changing application code.
    # Example: {"provider":"career_page","url":"https://company.com/careers","search":"golang"}
    if sources:
        configured = await discover_from_sources(db, sources)
        result["discovered"] += configured["discovered"]
        result["errors"].extend(configured["errors"])
        result["scores"].update(configured["scores"])

    async with httpx.AsyncClient(timeout=45, follow_redirects=True,
        headers={"User-Agent": "JobPilotAI/1.0"}) as client:
        items = []
        for name, loader in (
            ("JOBICY", lambda: fetch_jobicy(client, search, limit)),
            ("REMOTIVE", lambda: fetch_remotive(client, search, limit)),
            ("ARBEITNOW", lambda: fetch_arbeitnow(client, search, limit)),
            ("HIMALAYAS", lambda: fetch_himalayas(client, search, min(limit, 20))),
            ("JOB_OPPORTUNITIES_API", lambda: fetch_job_opportunities(client, search, min(limit, 50))),
        ):
            try:
                items.extend(await loader())
            except Exception as exc:
                result["errors"].append(f"{name}: {exc}")

        # Optional advanced discovery providers are admin-capability gated.
        if entitlement and entitlement.advanced_enabled and search:
            if entitlement.serp_discovery_enabled:
                serp = await discover_with_serp(search, limit=min(limit, 100))
                result["errors"].extend("SERP: " + error for error in serp.errors)
                items.extend(serp.items)
            if entitlement.premium_crawling_enabled:
                apify = await discover_with_apify(search, limit=min(limit, 100))
                result["errors"].extend("APIFY: " + error for error in apify.errors)
                items.extend(apify.items)

        for item in items:
            try:
                job = upsert_discovery(db, item)
                result["scores"][str(job.id)] = 75
                result["discovered"] += 1
            except Exception as exc:
                result["errors"].append(f"{item.get('provider')}: {exc}")

    return result
