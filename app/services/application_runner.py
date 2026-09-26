import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import async_playwright

from app.models import ActionRequired, Application

CAPTCHA_TERMS = ("captcha", "recaptcha", "hcaptcha", "verify you are human", "cloudflare")
UNKNOWN_REQUIRED_TERMS = ("ssn", "social security", "date of birth", "bank account", "credit card")

async def run_application(db, user, application):
    application.status = "IN_PROGRESS"
    application.attempt_count += 1
    application.started_at = datetime.now(timezone.utc)
    application.last_error = None
    db.commit()

    try:
        result = await _browser_run(user, application)
        status = result["status"]
        application.status = status
        application.application_data = result.get("data", {})
        if status == "SUBMITTED":
            application.submitted_at = datetime.now(timezone.utc)
        if status in {"ACTION_REQUIRED", "BLOCKED"}:
            action = ActionRequired(
                user_id=user.id,
                application_id=application.id,
                type=result.get("type", "APPLICATION"),
                title=result.get("title", "Application requires your action"),
                description=result.get("description", "The application could not be safely completed automatically."),
            )
            db.add(action)
        db.commit()
        db.refresh(application)
        return application
    except Exception as exc:
        application.last_error = str(exc)[:4000]
        if application.attempt_count < application.max_attempts:
            application.status = "RETRY"
        else:
            application.status = "FAILED"
        db.commit()
        db.refresh(application)
        return application

async def _browser_run(user, application):
    if not application.external_url:
        return {
            "status": "BLOCKED",
            "type": "MISSING_URL",
            "title": "Application URL is missing",
            "description": "This application has no external application URL.",
        }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(application.external_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(1200)
            text = (await page.locator("body").inner_text())[:50000].lower()

            if any(term in text for term in CAPTCHA_TERMS):
                return {
                    "status": "ACTION_REQUIRED",
                    "type": "CAPTCHA",
                    "title": "Complete verification",
                    "description": "The employer site requires a human verification step. JobPilot will not bypass it.",
                }

            if any(term in text for term in UNKNOWN_REQUIRED_TERMS):
                return {
                    "status": "ACTION_REQUIRED",
                    "type": "SENSITIVE_DATA",
                    "title": "Sensitive information requested",
                    "description": "The application requests sensitive information that JobPilot will not guess or fabricate.",
                }

            # Fill only fields with unambiguous, non-sensitive labels.
            values = {
                "first name": user.first_name,
                "last name": user.last_name,
                "email": user.email,
            }
            filled = []
            for label, value in values.items():
                if not value:
                    continue
                locator = page.get_by_label(re.compile(label, re.I))
                if await locator.count():
                    try:
                        await locator.first.fill(value)
                        filled.append(label)
                    except Exception:
                        pass

            file_path = None
            if user.resume and user.resume.file_path and not user.resume.file_path.startswith("supabase://"):
                file_path = user.resume.file_path

            if file_path and Path(file_path).exists():
                for selector in ("input[type=file]", "input[name*=resume i]", "input[accept*=pdf i]"):
                    locator = page.locator(selector)
                    if await locator.count():
                        try:
                            await locator.first.set_input_files(file_path)
                            filled.append("resume")
                            break
                        except Exception:
                            pass

            required = page.locator("input[required], textarea[required], select[required]")
            count = await required.count()
            if count:
                for i in range(min(count, 25)):
                    field = required.nth(i)
                    if await field.is_visible():
                        value = (await field.input_value()).strip()
                        if not value:
                            return {
                                "status": "ACTION_REQUIRED",
                                "type": "FORM_INPUT",
                                "title": "Application needs your input",
                                "description": "The application contains a required field JobPilot cannot safely determine from your profile.",
                                "data": {"filled": filled, "url": page.url},
                            }

            submit = page.get_by_role("button", name=re.compile(r"submit application|submit|apply", re.I))
            if await submit.count() == 0:
                return {
                    "status": "ACTION_REQUIRED",
                    "type": "UNSUPPORTED_FLOW",
                    "title": "Application flow needs review",
                    "description": "JobPilot reached the employer application page but could not identify a safe submission control.",
                    "data": {"filled": filled, "url": page.url},
                }

            # Do not submit automatically when the form contains ambiguous questions.
            return {
                "status": "ACTION_REQUIRED",
                "type": "FINAL_REVIEW",
                "title": "Application ready for final review",
                "description": "The form is reachable and basic fields were prepared. Review the employer questions before submission.",
                "data": {"filled": filled, "url": page.url},
            }
        finally:
            await browser.close()
import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright

from app.models import ActionRequired
from app.services.resume_storage import (
    cleanup_materialized_resume,
    materialize_resume,
)


CAPTCHA_TERMS = (
    "captcha",
    "recaptcha",
    "hcaptcha",
    "verify you are human",
    "cloudflare",
)

UNKNOWN_REQUIRED_TERMS = (
    "ssn",
    "social security",
    "date of birth",
    "bank account",
    "credit card",
)


async def run_application(db, user, application):
    application.status = "IN_PROGRESS"
    application.attempt_count += 1
    application.started_at = datetime.now(timezone.utc)
    application.last_error = None

    db.commit()

    try:
        result = await _browser_run(user, application)

        status = result["status"]

        application.status = status
        application.application_data = result.get(
            "data",
            {},
        )

        if status == "SUBMITTED":
            application.submitted_at = datetime.now(
                timezone.utc
            )

        if status in {
            "ACTION_REQUIRED",
            "BLOCKED",
        }:
            action = ActionRequired(
                user_id=user.id,
                application_id=application.id,
                type=result.get(
                    "type",
                    "APPLICATION",
                ),
                title=result.get(
                    "title",
                    "Application requires your action",
                ),
                description=result.get(
                    "description",
                    "The application could not be safely "
                    "completed automatically.",
                ),
            )

            db.add(action)

        db.commit()
        db.refresh(application)

        return application

    except Exception as exc:
        application.last_error = str(exc)[:4000]

        if application.attempt_count < application.max_attempts:
            application.status = "RETRY"
        else:
            application.status = "FAILED"

        db.commit()
        db.refresh(application)

        return application


async def _browser_run(user, application):
    if not application.external_url:
        return {
            "status": "BLOCKED",
            "type": "MISSING_URL",
            "title": "Application URL is missing",
            "description": (
                "This application has no external "
                "application URL."
            ),
        }

    resume_path = None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True
        )

        page = await browser.new_page()

        try:
            await page.goto(
                application.external_url,
                wait_until="domcontentloaded",
                timeout=45000,
            )

            await page.wait_for_timeout(1200)

            text = (
                await page.locator("body").inner_text()
            )[:50000].lower()

            # Never bypass CAPTCHA or human verification.
            if any(
                term in text
                for term in CAPTCHA_TERMS
            ):
                return {
                    "status": "ACTION_REQUIRED",
                    "type": "CAPTCHA",
                    "title": "Complete verification",
                    "description": (
                        "The employer site requires a "
                        "human verification step. "
                        "JobPilot will not bypass it."
                    ),
                }

            # Never fabricate sensitive information.
            if any(
                term in text
                for term in UNKNOWN_REQUIRED_TERMS
            ):
                return {
                    "status": "ACTION_REQUIRED",
                    "type": "SENSITIVE_DATA",
                    "title": (
                        "Sensitive information requested"
                    ),
                    "description": (
                        "The application requests sensitive "
                        "information that JobPilot will not "
                        "guess or fabricate."
                    ),
                }

            # Fill only unambiguous profile fields.
            values = {
                "first name": user.first_name,
                "last name": user.last_name,
                "email": user.email,
            }

            filled = []

            for label, value in values.items():
                if not value:
                    continue

                locator = page.get_by_label(
                    re.compile(label, re.I)
                )

                if await locator.count():
                    try:
                        await locator.first.fill(value)
                        filled.append(label)
                    except Exception:
                        pass

            # Materialize the resume from Supabase when
            # running in production.
            if user.resume:
                resume_path = await materialize_resume(
                    user.resume.file_path
                )

            if resume_path:
                for selector in (
                    "input[type=file]",
                    "input[name*=resume i]",
                    "input[accept*=pdf i]",
                ):
                    locator = page.locator(selector)

                    if await locator.count():
                        try:
                            await locator.first.set_input_files(
                                resume_path
                            )

                            filled.append("resume")
                            break

                        except Exception:
                            pass

            # Check required fields.
            required = page.locator(
                "input[required], "
                "textarea[required], "
                "select[required]"
            )

            count = await required.count()

            if count:
                for i in range(min(count, 25)):
                    field = required.nth(i)

                    if await field.is_visible():
                        try:
                            value = (
                                await field.input_value()
                            ).strip()
                        except Exception:
                            value = ""

                        if not value:
                            return {
                                "status": "ACTION_REQUIRED",
                                "type": "FORM_INPUT",
                                "title": (
                                    "Application needs "
                                    "your input"
                                ),
                                "description": (
                                    "The application contains "
                                    "a required field JobPilot "
                                    "cannot safely determine "
                                    "from your profile."
                                ),
                                "data": {
                                    "filled": filled,
                                    "url": page.url,
                                },
                            }

            submit = page.get_by_role(
                "button",
                name=re.compile(
                    r"submit application|submit|apply",
                    re.I,
                ),
            )

            if await submit.count() == 0:
                return {
                    "status": "ACTION_REQUIRED",
                    "type": "UNSUPPORTED_FLOW",
                    "title": (
                        "Application flow needs review"
                    ),
                    "description": (
                        "JobPilot reached the employer "
                        "application page but could not "
                        "identify a safe submission control."
                    ),
                    "data": {
                        "filled": filled,
                        "url": page.url,
                    },
                }

            # Do not blindly submit generic forms.
            # Provider-specific adapters will eventually
            # handle supported application flows.
            return {
                "status": "ACTION_REQUIRED",
                "type": "FINAL_REVIEW",
                "title": (
                    "Application ready for final review"
                ),
                "description": (
                    "The form is reachable and basic fields "
                    "were prepared. Review employer questions "
                    "before submission."
                ),
                "data": {
                    "filled": filled,
                    "url": page.url,
                },
            }

        finally:
            cleanup_materialized_resume(resume_path)

            await browser.close()