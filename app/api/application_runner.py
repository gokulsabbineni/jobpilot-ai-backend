from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import Application
from app.services.application_runner import run_application
from app.api.applications import serialize

r = APIRouter(prefix="/api/user/applications", tags=["application-runner"])

@r.post("/{application_id}/run")
async def run(application_id:int, db:Session=Depends(get_db), u=Depends(active_user)):
    application=db.query(Application).filter_by(id=application_id,user_id=u.id).first()
    if not application:
        raise HTTPException(404,"Application not found")
    if application.status in {"SUBMITTED","IN_PROGRESS"}:
        return serialize(application)
    return serialize(await run_application(db,u,application))
