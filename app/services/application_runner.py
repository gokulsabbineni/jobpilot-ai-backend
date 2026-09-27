import re
from datetime import datetime, timezone

from playwright.async_api import async_playwright

from app.models import ActionRequired
from app.services.resume_storage import cleanup_materialized_resume, materialize_resume
from app.providers.registry import application_provider_for
from app.providers.ats import application_hints

CAPTCHA_TERMS = ("captcha", "recaptcha", "hcaptcha", "verify you are human", "cloudflare")
UNKNOWN_REQUIRED_TERMS = ("ssn", "social security", "date of birth", "bank account", "credit card")
SUCCESS_TERMS = ("thank you for applying", "application submitted", "application received", "thanks for applying")


async def run_application(db, user, application):
    application.status = "IN_PROGRESS"
    application.attempt_count += 1
    application.started_at = datetime.now(timezone.utc)
    application.last_error = None
    db.commit()
    try:
        result = await _browser_run(user, application)
        application.status = result["status"]
        data = result.get("data", {})
        data["provider"] = application_provider_for(application)
        data["provider_hints"] = application_hints(application.external_url)
        application.application_data = data
        if application.status == "SUBMITTED":
            application.submitted_at = datetime.now(timezone.utc)
        if application.status in {"ACTION_REQUIRED", "BLOCKED"}:
            db.add(ActionRequired(
                user_id=user.id, application_id=application.id,
                type=result.get("type", "APPLICATION"),
                title=result.get("title", "Application requires your action"),
                description=result.get("description", "The application could not be safely completed automatically."),
            ))
        db.commit()
        db.refresh(application)
        return application
    except Exception as exc:
        application.last_error = str(exc)[:4000]
        application.status = "RETRY" if application.attempt_count < application.max_attempts else "FAILED"
        db.commit()
        db.refresh(application)
        return application


async def _browser_run(user, application):
    if not application.external_url:
        return {"status": "BLOCKED", "type": "MISSING_URL", "title": "Application URL is missing",
                "description": "This application has no external application URL."}

    resume_path = None
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(application.external_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(1200)
            text = (await page.locator("body").inner_text())[:50000].lower()

            if any(term in text for term in CAPTCHA_TERMS):
                return {"status": "ACTION_REQUIRED", "type": "CAPTCHA", "title": "Complete verification",
                        "description": "The employer site requires human verification. JobPilot will not bypass it."}

            if any(term in text for term in UNKNOWN_REQUIRED_TERMS):
                return {"status": "ACTION_REQUIRED", "type": "SENSITIVE_DATA", "title": "Sensitive information requested",
                        "description": "The application requests sensitive information that JobPilot will not guess or fabricate."}

            values = {"first name": user.first_name, "last name": user.last_name, "email": user.email}
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

            if user.resume:
                resume_path = await materialize_resume(user.resume.file_path)
            if resume_path:
                for selector in ("input[type=file]", "input[name*=resume i]", "input[accept*=pdf i]"):
                    locator = page.locator(selector)
                    if await locator.count():
                        try:
                            await locator.first.set_input_files(resume_path)
                            filled.append("resume")
                            break
                        except Exception:
                            pass

            required = page.locator("input[required], textarea[required], select[required]")
            for i in range(min(await required.count(), 25)):
                field = required.nth(i)
                if await field.is_visible():
                    try:
                        value = (await field.input_value()).strip()
                    except Exception:
                        value = ""
                    if not value:
                        return {"status": "ACTION_REQUIRED", "type": "FORM_INPUT", "title": "Application needs your input",
                                "description": "A required field could not be safely determined from your profile.",
                                "data": {"filled": filled, "url": page.url}}

            submit = page.get_by_role("button", name=re.compile(r"submit application|submit|apply", re.I))
            if await submit.count() == 0:
                submit = page.locator("input[type=submit], button[type=submit]")
            if await submit.count() == 0:
                return {"status": "ACTION_REQUIRED", "type": "UNSUPPORTED_FLOW", "title": "Application flow needs review",
                        "description": "JobPilot reached the application page but could not identify a safe submission control.",
                        "data": {"filled": filled, "url": page.url}}

            # Submit only after every visible required form control has a value and
            # no CAPTCHA/MFA/sensitive-data blocker was detected.
            await submit.first.click(timeout=10000)
            await page.wait_for_timeout(1500)
            confirmation = (await page.locator("body").inner_text())[:50000].lower()
            if any(term in confirmation for term in SUCCESS_TERMS):
                return {"status": "SUBMITTED", "data": {"filled": filled, "url": page.url, "confirmation_detected": True}}

            # Some ATSs navigate to a confirmation URL without the same text.
            url = page.url.lower()
            if any(x in url for x in ("/thank", "/confirmation", "/success")):
                return {"status": "SUBMITTED", "data": {"filled": filled, "url": page.url, "confirmation_detected": True}}

            return {"status": "ACTION_REQUIRED", "type": "SUBMISSION_UNCONFIRMED",
                    "title": "Submission could not be confirmed",
                    "description": "JobPilot clicked the submission control, but the employer site did not provide a clear confirmation.",
                    "data": {"filled": filled, "url": page.url}}
        finally:
            cleanup_materialized_resume(resume_path)
            await browser.close()
