from urllib.parse import urlparse

from app.config import settings
from app.providers.base import ApplicationProvider


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def identify_application_provider(url: str | None, source: str | None = None) -> str:
    """Identify an ATS from source metadata and URL without making assumptions."""
    source_value = (source or "").lower()
    host = _host(url or "")

    if "greenhouse" in source_value or "greenhouse.io" in host:
        return "greenhouse"
    if "lever" in source_value or "lever.co" in host:
        return "lever"
    if "ashby" in source_value or "ashbyhq.com" in host:
        return "ashby"
    if "smartrecruiters" in source_value or "smartrecruiters.com" in host:
        return "smartrecruiters"
    if "workday" in source_value or "myworkdayjobs.com" in host or "workday.com" in host:
        return "workday"
    return "generic"


def provider_capabilities(entitlement) -> dict[str, bool]:
    advanced = bool(entitlement and entitlement.advanced_enabled)
    return {
        "greenhouse": True,
        "lever": True,
        "ashby": True,
        "smartrecruiters": True,
        "workday": advanced and bool(settings.workday_provider_enabled),
        "browser": advanced and bool(entitlement.cloud_browser_enabled),
        "serp": advanced and bool(entitlement.serp_discovery_enabled),
        "premium_crawling": advanced and bool(entitlement.premium_crawling_enabled),
    }


def application_provider_for(application, entitlement=None) -> str:
    return identify_application_provider(
        application.external_url,
        application.provider,
    )
