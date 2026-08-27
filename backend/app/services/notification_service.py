"""In-app notification service.

Structured so SMS/WhatsApp/email/push channels can be added later without
changing callers — they would just add a `channel` dispatch branch here.
"""
from sqlalchemy.orm import Session

from app.models.notification import Notification


def notify(
    db: Session,
    *,
    user_id: int | None,
    issue_id: int | None,
    complaint_id: str | None,
    title: str,
    message: str,
    notif_type: str = "status_update",
) -> Notification:
    notification = Notification(
        user_id=user_id,
        issue_id=issue_id,
        complaint_id=complaint_id,
        title=title,
        message=message,
        notif_type=notif_type,
        channel="in_app",
    )
    db.add(notification)
    db.flush()
    # Future channels (SMS/WhatsApp/email/push) would be dispatched here,
    # keyed off notif_type/channel, without touching any caller code.
    return notification


NOTIFICATION_TEMPLATES = {
    "received": lambda cid: (f"Report received — {cid}", "We've received your report and it's being processed."),
    "ai_verified": lambda cid: (f"Report verified — {cid}", "Your report has been analysed and verified by our system."),
    "assigned": lambda cid, dept: (f"Department assigned — {cid}", f"Your report was assigned to {dept}."),
    "accepted": lambda cid: (f"Officer accepted your report — {cid}", "A municipal officer has accepted your report and will begin work soon."),
    "work_started": lambda cid: (f"Work started — {cid}", "Work has started on your reported issue."),
    "resolution_submitted": lambda cid: (f"Resolution submitted — {cid}", "The department has submitted proof of resolution. Please verify."),
    "resolved": lambda cid: (f"Issue resolved — {cid}", "Your issue has been marked resolved. Thank you for helping improve your city!"),
    "reopened": lambda cid: (f"Issue reopened — {cid}", "Your issue was reopened and sent back to the department."),
    "duplicate_linked": lambda cid, count: (f"Report linked — {cid}", f"Your report was linked to an existing civic issue. {count} citizens have reported this issue."),
}
