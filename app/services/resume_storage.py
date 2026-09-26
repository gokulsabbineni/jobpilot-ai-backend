from pathlib import Path
from urllib.parse import quote
import tempfile

import httpx

from app.config import settings


def _object_url(object_path: str) -> str:
    if not settings.supabase_url:
        raise RuntimeError("SUPABASE_URL is not configured")

    bucket = quote(settings.supabase_storage_bucket, safe="")
    path = quote(object_path, safe="/")

    return (
        f"{settings.supabase_url.rstrip('/')}"
        f"/storage/v1/object/{bucket}/{path}"
    )


def _headers() -> dict[str, str]:
    if not settings.supabase_service_role_key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY is not configured"
        )

    return {
        "Authorization": (
            f"Bearer {settings.supabase_service_role_key}"
        ),
        "apikey": settings.supabase_service_role_key,
    }


async def materialize_resume(
    storage_reference: str | None,
) -> str | None:
    """
    Make a resume available as a temporary local file.

    Supports:
    - Local filesystem paths for development
    - supabase://bucket/path references for production
    """

    if not storage_reference:
        return None

    # Local development storage.
    if not storage_reference.startswith("supabase://"):
        path = Path(storage_reference)

        if path.exists() and path.is_file():
            return str(path)

        return None

    prefix = (
        f"supabase://"
        f"{settings.supabase_storage_bucket}/"
    )

    if not storage_reference.startswith(prefix):
        raise ValueError(
            "Resume storage reference does not match "
            "the configured Supabase bucket"
        )

    object_path = storage_reference[len(prefix):]

    if not object_path:
        raise ValueError("Resume storage path is empty")

    suffix = Path(object_path).suffix or ".bin"

    fd, temp_path = tempfile.mkstemp(
        prefix="jobpilot_resume_",
        suffix=suffix,
    )

    # mkstemp creates the file. Remove it so we can write the
    # downloaded bytes normally.
    Path(temp_path).unlink(missing_ok=True)

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                _object_url(object_path),
                headers=_headers(),
            )

            response.raise_for_status()

        Path(temp_path).write_bytes(response.content)

        return temp_path

    except Exception:
        Path(temp_path).unlink(missing_ok=True)
        raise


def cleanup_materialized_resume(
    file_path: str | None,
) -> None:
    """
    Delete a temporary resume downloaded from Supabase.

    Local development resume files are left untouched.
    """

    if not file_path:
        return

    path = Path(file_path)

    if not path.name.startswith("jobpilot_resume_"):
        return

    path.unlink(missing_ok=True)