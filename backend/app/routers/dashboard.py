from datetime import datetime, date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.issue import Issue
from app.models.staff import StaffUser
from app.schemas.dashboard import KPISummary, MapMarker
from app.utils.deps import get_current_staff
from app.routers.issues import is_overdue, apply_data_scope, PAST_ISSUE_STATUSES

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

BACKLOG_STATUSES = ("SUBMITTED", "AI_VERIFIED", "MANUAL_REVIEW", "ASSIGNED")


@router.get("/summary", response_model=KPISummary)
def summary(data_scope: str = "live", db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    issues = apply_data_scope(db.query(Issue), data_scope).all()

    open_issues = [i for i in issues if i.status not in PAST_ISSUE_STATUSES]
    critical = [i for i in open_issues if i.priority_level == "CRITICAL"]
    in_progress = [i for i in issues if i.status == "IN_PROGRESS"]
    resolved_today = [i for i in issues if i.status == "RESOLVED" and i.resolved_at and i.resolved_at.date() == date.today()]
    backlog = [i for i in issues if i.status in BACKLOG_STATUSES]
    reopened = [i for i in issues if i.reopen_count > 0]
    manual_review = [i for i in issues if i.status == "MANUAL_REVIEW"]
    overdue = [i for i in open_issues if is_overdue(i)]

    response_times = [(i.accepted_at - i.created_at).total_seconds() / 3600 for i in issues if i.accepted_at]
    resolution_times = [(i.resolved_at - i.created_at).total_seconds() / 3600 for i in issues if i.resolved_at]

    return KPISummary(
        open_issues=len(open_issues),
        critical_issues=len(critical),
        in_progress=len(in_progress),
        resolved_today=len(resolved_today),
        avg_response_time_hours=round(sum(response_times) / len(response_times), 1) if response_times else 0.0,
        avg_resolution_time_hours=round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else 0.0,
        pending_backlog=len(backlog),
        reopened_issues=len(reopened),
        manual_review_queue=len(manual_review),
        overdue_issues=len(overdue),
    )


@router.get("/map", response_model=list[MapMarker])
def map_markers(data_scope: str = "live", db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    # The main dashboard map is an ACTIVE view — RESOLVED issues must
    # disappear from it immediately (they remain fully in the database;
    # see /staff/issues?status=RESOLVED / the Past Issues page for them).
    # A REOPENED issue has a different status again, so it naturally
    # reappears here with no special-case code needed.
    query = apply_data_scope(db.query(Issue).filter(Issue.status.notin_(PAST_ISSUE_STATUSES)), data_scope)
    issues = query.all()
    return [
        MapMarker(
            id=i.id, complaint_id=i.complaint_id, issue_type=i.issue_type, category=i.category,
            latitude=i.latitude, longitude=i.longitude, severity=i.severity, priority_level=i.priority_level,
            status=i.status, reporter_count=i.reporter_count,
            department=i.primary_department.name if i.primary_department else None,
            is_demo=i.is_demo,
        )
        for i in issues
    ]
