from pathlib import Path
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import Resume
from app.config import settings


r = APIRouter(prefix="/api/user/resume", tags=["resume"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_RESUME_BYTES = 10 * 1024 * 1024


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
        raise HTTPException(400, "Only PDF, DOCX and TXT files are supported")

    data = await file.read()
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(413, "File too large")

    folder = Path(settings.storage_dir)
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / f"user_{u.id}_{name}"
    path.write_bytes(data)

    resume = u.resume or Resume(user_id=u.id, file_name=name)
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
    return resume
