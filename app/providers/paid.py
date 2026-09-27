"""Optional paid provider adapters.

These adapters are deliberately configuration-gated. They do not silently
call a paid service when credentials are absent. The first implementation
provides provider discovery contracts; concrete crawling can be enabled later
without changing the agent orchestration layer.
"""

import httpx

from app.config import settings
from app.providers.base import ProviderResult


async def discover_with_serp(query: str, limit: int = 100) -> ProviderResult:
    if not settings.bright_data_serp_api_key:
        return ProviderResult("brightdata_serp", errors=["Bright Data SERP provider is not configured."])
    # Provider endpoint/auth details are isolated here so changing vendors
    # cannot leak into the agent or discovery orchestration code.
    return ProviderResult("brightdata_serp", metadata={"configured": True, "limit": limit},
                          errors=["SERP adapter is configured but not enabled until endpoint settings are supplied."])


async def discover_with_apify(query: str, limit: int = 100) -> ProviderResult:
    if not settings.apify_api_token:
        return ProviderResult("apify", errors=["Apify provider is not configured."])
    return ProviderResult("apify", metadata={"configured": True, "limit": limit},
                          errors=["Apify adapter is configured but Actor selection is not enabled yet."])
