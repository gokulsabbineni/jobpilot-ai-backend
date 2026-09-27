from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class ATSProfile:
    name: str
    domains: tuple[str, ...]
    form_hints: tuple[str, ...]


PROFILES = (
    ATSProfile("greenhouse", ("greenhouse.io",), ("first_name", "last_name", "email", "resume")),
    ATSProfile("lever", ("lever.co",), ("name", "email", "resume")),
    ATSProfile("ashby", ("ashbyhq.com",), ("name", "email", "resume")),
    ATSProfile("smartrecruiters", ("smartrecruiters.com",), ("first_name", "last_name", "email", "resume")),
)


def profile_for_url(url: str | None) -> ATSProfile | None:
    if not url:
        return None
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return None
    for profile in PROFILES:
        if any(host == domain or host.endswith("." + domain) for domain in profile.domains):
            return profile
    return None


def application_hints(url: str | None) -> dict[str, Any]:
    profile = profile_for_url(url)
    if not profile:
        return {"provider": "generic", "hints": []}
    return {"provider": profile.name, "hints": list(profile.form_hints)}
