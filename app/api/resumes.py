from pathlib import Path
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import active_user
from app.models import Resume


r = APIRouter(prefix="/api/user/resume", tags=["resume"])

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx"}
MAX_RESUME_BYTES = 10 * 1024 * 1024


def safe_resume_path(path_value: str | None) -> Path | None:
    if not path_value or path_value.startswith("supabase://"):
        return None

    path = Path(path_value).resolve()
    storage_root = Path(settings.storage_dir).resolve()

    try:
        path.relative_to(storage_root)
    except ValueError:
        return None

    return path


def supabase_object_url(object_path: str) -> str:
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured")
    bucket = quote(settings.supabase_storage_bucket, safe="")
    path = quote(object_path, safe="/")
    return f"{settings.supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{path}"


def supabase_headers() -> dict[str, str]:
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not configured")
    return {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }


async def supabase_upload(object_path: str, data: bytes, content_type: str | None) -> str:
    headers = supabase_headers()
    headers["Content-Type"] = content_type or "application/octet-stream"
    headers["x-upsert"] = "true"

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            supabase_object_url(object_path),
            content=data,
            headers=headers,
        )
        response.raise_for_status()

    return f"supabase://{settings.supabase_storage_bucket}/{object_path}"


async def supabase_delete(storage_reference: str) -> None:
    prefix = f"supabase://{settings.supabase_storage_bucket}/"
    if not storage_reference.startswith(prefix):
        return

    object_path = storage_reference[len(prefix):]
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.delete(
            supabase_object_url(object_path),
            headers=supabase_headers(),
        )
        if response.status_code not in {200, 204, 404}:
            response.raise_for_status()


@r.get("")
def get_resume(u=Depends(active_user)):
    return u.resume


@r.post("")
async def upload(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    u=Depends(active_user),
):
    name = Path(file.filename or "").name
    suffix = Path(name).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            "Only PDF, DOC and DOCX files are supported",
        )

    data = await file.read()
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(413, "File too large")

    old_reference = u.resume.file_path if u.resume else None

    if settings.uses_supabase_storage:
        object_path = f"users/{u.id}/{name}"
        try:
            stored_reference = await supabase_upload(
                object_path,
                data,
                file.content_type,
            )
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500] or "Supabase Storage rejected the upload."
            raise HTTPException(
                502,
                f"Resume storage upload failed: {detail}",
            ) from exc
        except (httpx.RequestError, RuntimeError) as exc:
            raise HTTPException(
                503,
                "Resume storage is temporarily unavailable. Please try again.",
            ) from exc
    else:
        folder = Path(settings.storage_dir)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"user_{u.id}_{name}"
        path.write_bytes(data)
        stored_reference = str(path)

    resume = u.resume or Resume(
        user_id=u.id,
        file_name=name,
    )

    resume.file_name = name
    resume.file_path = stored_reference
    resume.content_text = None
    resume.parsed_profile = {
        "skills": [],
        "experience": [],
        "education": [],
    }

    if u.resume is None:
        db.add(resume)

    try:
        db.commit()
        db.refresh(resume)
    except Exception:
        db.rollback()
        raise

    # If the same filename was uploaded, Supabase has already overwritten the
    # object. Do not delete the newly uploaded object in that case.
    if old_reference and old_reference != stored_reference:
        try:
            if old_reference.startswith("supabase://"):
                await supabase_delete(old_reference)
            else:
                old_path = safe_resume_path(old_reference)
                if old_path and old_path.exists():
                    old_path.unlink()
        except (httpx.RequestError, httpx.HTTPStatusError):
            # The database now points at the new resume. Cleanup of the old
            # object can safely be retried later without failing the upload.
            pass

    return resume


@r.delete("")
async def delete_resume(
    db: Session = Depends(get_db),
    u=Depends(active_user),
):
    resume = u.resume

    if resume is None:
        raise HTTPException(404, "No resume is currently uploaded")

    stored_reference = resume.file_path

    db.delete(resume)
    db.commit()

    if stored_reference and stored_reference.startswith("supabase://"):
        try:
            await supabase_delete(stored_reference)
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            raise HTTPException(
                502,
                "Resume was removed from your account, but cloud storage cleanup failed. Please contact support if the file still appears in storage.",
            ) from exc
    else:
        stored_path = safe_resume_path(stored_reference)
        if stored_path and stored_path.exists():
            stored_path.unlink()

    return {"message": "Resume deleted successfully"}
