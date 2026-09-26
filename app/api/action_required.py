from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import ActionRequired
from app.schemas import ActionResponse


r = APIRouter(prefix="/api/user/action-required", tags=["action-required"])


def serialize(item: ActionRequired):
    application = item.application
    job = application.job if application else None

    return {
        "id": item.id,
        "user_id": item.user_id,
        "application_id": item.application_id,
        "type": item.type,
        "title": item.title,
        "description": item.description,
        "required": item.required,
        "completed": item.completed,
        "response": item.response,
        "created_at": item.created_at,
        "completed_at": item.completed_at,
        "application": (
            {
                "id": application.id,
                "status": application.status,
                "job": (
                    {
                        "id": job.id,
                        "company": job.company,
                        "title": job.title,
                        "location": job.location,
                        "url": job.url,
                    }
                    if job
                    else None
                ),
            }
            if application
            else None
        ),
    }


@r.get("")
def items(db: Session = Depends(get_db), u=Depends(active_user)):
    return [
        serialize(item)
        for item in (
            db.query(ActionRequired)
            .filter_by(user_id=u.id)
            .order_by(ActionRequired.id.desc())
            .all()
        )
    ]


@r.post("/{item_id}")
def complete(
    item_id: int,
    p: ActionResponse,
    db: Session = Depends(get_db),
    u=Depends(active_user),
):
    item = (
        db.query(ActionRequired)
        .filter_by(id=item_id, user_id=u.id)
        .first()
    )
    if not item:
        raise HTTPException(404, "Action item not found")

    if not item.completed:
        item.completed = True
        item.response = p.response
        item.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)

    return serialize(item)
