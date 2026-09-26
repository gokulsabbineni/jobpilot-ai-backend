from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.deps import active_user
from app.models import ActionRequired
from app.schemas import ActionResponse


r = APIRouter(prefix="/api/user/action-required", tags=["action-required"])


@r.get("")
def items(db: Session = Depends(get_db), u=Depends(active_user)):
    return (
        db.query(ActionRequired)
        .filter_by(user_id=u.id)
        .order_by(ActionRequired.id.desc())
        .all()
    )


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

    if item.completed:
        return item

    item.completed = True
    item.response = p.response
    item.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item
