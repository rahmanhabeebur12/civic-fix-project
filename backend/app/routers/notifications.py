from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.notification import Notification
from app.models.user import User

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(mobile: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.mobile == mobile).first()
    if not user:
        return []
    notifs = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": n.id, "title": n.title, "message": n.message, "notif_type": n.notif_type,
            "complaint_id": n.complaint_id, "is_read": n.is_read, "created_at": n.created_at,
        }
        for n in notifs
    ]


@router.post("/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db)):
    n = db.query(Notification).get(notification_id)
    if n:
        n.is_read = True
        db.commit()
    return {"ok": True}
