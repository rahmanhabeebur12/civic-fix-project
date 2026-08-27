import uuid
from datetime import datetime
from sqlalchemy.orm import Session


def new_client_report_id() -> str:
    return str(uuid.uuid4())


def generate_complaint_id(db: Session) -> str:
    """CIV-<year>-<sequential 4-digit padded number>."""
    from app.models.issue import Issue

    year = datetime.utcnow().year
    prefix = f"CIV-{year}-"
    count = db.query(Issue).filter(Issue.complaint_id.like(f"{prefix}%")).count()
    next_num = count + 1
    return f"{prefix}{next_num:04d}"
