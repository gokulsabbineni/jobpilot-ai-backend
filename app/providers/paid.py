import json
from typing import Any

import httpx

from app.config import settings
from app.providers.base import ProviderResult


async def discover_with_serp(query: str, limit: int = 100) -> ProviderResult:
    if not settings.bright_data_serp_api_key:
        return ProviderResult("brightdata_serp", errors=["Bright Data SERP provider is not configured."])

    params = {
        "q": query,
        "num": min(max(limit, 1), 100),
    }
    headers = {"Authorization": f"Bearer {settings.bright_data_serp_api_key}"}
    if settings.bright_data_zone:
        params["zone"] = settings.bright_data_zone
    if settings.bright_data_customer_id:
        params["customer": settings.bright_data_customer_id]

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.get(
                "https://api.brightdata.com/request",
                params=params,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        return ProviderResult("brightdata_serp", metadata={"configured": True}, items=payload.get("organic", []) if isinstance(payload, dict) else [])
    except Exception as exc:
        return ProviderResult("brightdata_serp", errors=[str(exc)[:1000]])


async def discover_with_apify(query: str, limit: int = 100) -> ProviderResult:
    if not settings.apify_api_token or not settings.apify_job_actor_id:
        return ProviderResult("apify", errors=["Apify provider or Actor is not configured."])

    try:
        actor_input: dict[str, Any] = {"query": query, "limit": min(max(limit, 1), 100)}
        if settings.apify_job_actor_input_json:
            actor_input.update(json.loads(settings.apify_job_actor_input_json))

        async with httpx.AsyncClient(timeout=120) as client:
            run = await client.post(
                f"https://api.apify.com/v2/acts/{settings.apify_job_actor_id}/runs",
                params={"token": settings.apify_api_token, "waitForFinish": 120},
                json=actor_input,
            )
            run.raise_for_status()
            run_data = run.json().get("data", {})
            dataset_id = run_data.get("defaultDatasetId")
            if not dataset_id:
                return ProviderResult("apify", errors=["Apify Actor run returned no dataset."])

            dataset = await client.get(
                f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                params={"token": settings.apify_api_token, "clean": "true", "limit": limit},
            )
            dataset.raise_for_status()
            items = dataset.json()
        return ProviderResult("apify", items=items if isinstance(items, list) else [], metadata={"configured": True})
    except Exception as exc:
        return ProviderResult("apify", errors=[str(exc)[:1000]])
