import re
from dataclasses import dataclass
from urllib.parse import urlparse

from playwright.async_api import Page


@dataclass(frozen=True)
class ATSProfile:
    name: str
    domains: tuple[str, ...]
    form_hints: tuple[str, ...]
    apply_path_hints: tuple[str, ...] = ()


PROFILES = (
    ATSProfile("greenhouse", ("greenhouse.io",), ("first_name", "last_name", "email", "resume"), ("application",)),
    ATSProfile("lever", ("lever.co",), ("name", "email", "resume"), ("apply",)),
    ATSProfile("ashby", ("ashbyhq.com",), ("name", "email", "resume"), ("application",)),
    ATSProfile("smartrecruiters", ("smartrecruiters.com",), ("first_name", "last_name", "email", "resume"), ("apply",)),
    ATSProfile("workday", ("myworkdayjobs.com", "workday.com"), ("name", "email", "resume"), ("apply",)),
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


def application_hints(url: str | None) -> dict:
    profile = profile_for_url(url)
    if not profile:
        return {"provider": "generic", "hints": [], "apply_path_hints": []}
    return {
        "provider": profile.name,
        "hints": list(profile.form_hints),
        "apply_path_hints": list(profile.apply_path_hints),
    }


def _label_variants(provider: str, field: str) -> tuple[str, ...]:
    common = {
        "first_name": ("first name", "first_name", "given name"),
        "last_name": ("last name", "last_name", "family name", "surname"),
        "email": ("email", "email address"),
        "name": ("full name", "name"),
        "resume": ("resume", "cv", "curriculum vitae"),
    }
    provider_fields = {
        "greenhouse": {
            "first_name": ("first name", "first_name"),
            "last_name": ("last name", "last_name"),
            "email": ("email", "email address"),
            "resume": ("resume", "resume/cv", "cv"),
        },
        "lever": {
            "name": ("full name", "name"),
            "email": ("email", "email address"),
            "resume": ("resume", "resume/cv", "cv"),
        },
        "ashby": {
            "name": ("name", "full name"),
            "email": ("email", "email address"),
            "resume": ("resume", "cv"),
        },
        "smartrecruiters": {
            "first_name": ("first name", "first_name"),
            "last_name": ("last name", "last_name"),
            "email": ("email", "email address"),
            "resume": ("resume", "cv"),
        },
        "workday": {
            "name": ("name", "full name"),
            "email": ("email", "email address"),
            "resume": ("resume", "cv"),
        },
    }
    return provider_fields.get(provider, {}).get(field, common.get(field, (field,)))


async def fill_profile_fields(page: Page, provider: str, user) -> list[str]:
    filled = []
    values = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
    }
    if provider in {"lever", "ashby", "workday"} and user.first_name and user.last_name:
        values["name"] = f"{user.first_name} {user.last_name}"

    for field, value in values.items():
        if not value:
            continue
        for label in _label_variants(provider, field):
            locator = page.get_by_label(re.compile(re.escape(label), re.I))
            if await locator.count():
                try:
                    await locator.first.fill(value)
                    filled.append(field)
                    break
                except Exception:
                    continue

    return filled


async def find_resume_input(page: Page, provider: str):
    for label in _label_variants(provider, "resume"):
        locator = page.get_by_label(re.compile(re.escape(label), re.I))
        if await locator.count():
            return locator.first
    for selector in (
        "input[type=file]",
        "input[name*=resume i]",
        "input[name*=cv i]",
        "input[accept*=pdf i]",
        "input[accept*=document i]",
    ):
        locator = page.locator(selector)
        if await locator.count():
            return locator.first
    return None


async def find_submit_control(page: Page, provider: str):
    names = {
        "greenhouse": r"submit application|submit",
        "lever": r"submit application|submit|apply",
        "ashby": r"submit application|submit|apply",
        "smartrecruiters": r"submit application|submit|apply",
        "workday": r"submit application|submit|apply",
        "generic": r"submit application|submit|apply",
    }
    locator = page.get_by_role("button", name=re.compile(names.get(provider, names["generic"]), re.I))
    if await locator.count():
        return locator.first
    locator = page.locator("input[type=submit], button[type=submit]")
    return locator.first if await locator.count() else None
