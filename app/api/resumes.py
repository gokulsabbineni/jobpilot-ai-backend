from pathlib import Path

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import active_user
from app.models import Resume


r = APIRouter(prefix="/api/user/resume", tags=["resume"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_RESUME_BYTES = 10 * 1024 * 1024


def safe_resume_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None

    path = Path(path_value).resolve()
    storage_root = Path(settings.storage_dir).resolve()

    try:
        path.relative_to(storage_root)
    except ValueError:
        return None

    return path


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
            "Only PDF, DOCX and TXT files are supported",
        )

    data = await file.read()
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(413, "File too large")

    folder = Path(settings.storage_dir)
    folder.mkdir(parents=True, exist_ok=True)

    old_path = safe_resume_path(
        u.resume.file_path if u.resume else None
    )

    path = folder / f"user_{u.id}_{name}"
    path.write_bytes(data)

    resume = u.resume or Resume(
        user_id=u.id,
        file_name=name,
    )

    resume.file_name = name
    resume.file_path = str(path)
    resume.content_text = None
    resume.parsed_profile = {
        "skills": [],
        "experience": [],
        "education": [],
    }

    if u.resume is None:
        db.add(resume)

    db.commit()
    db.refresh(resume)

    if old_path and old_path != path.resolve() and old_path.exists():
        old_path.unlink()

    return resume


@r.delete("")
def delete_resume(
    db: Session = Depends(get_db),
    u=Depends(active_user),
):
    resume = u.resume

    if resume is None:
        raise HTTPException(404, "No resume is currently uploaded")

    stored_path = safe_resume_path(resume.file_path)

    db.delete(resume)
    db.commit()

    if stored_path and stored_path.exists():
        stored_path.unlink()

    return {"message": "Resume deleted successfully"}
