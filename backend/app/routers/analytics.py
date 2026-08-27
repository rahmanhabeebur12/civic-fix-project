from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.department import Department
from app.models.issue import Issue
from app.models.staff import StaffUser
from app.schemas.analytics import (
    BacklogAnalyticsResponse, CategoryBreakdown, DepartmentBacklogItem, DepartmentPerformance,
    HeatmapPointResponse, HotspotResponse, OldestUnresolvedItem, ResponseTimeAnalyticsResponse,
)
from app.services.analytics_service import compute_backlog_analytics, compute_response_time_analytics
from app.services.heatmap_service import get_heatmap_points
from app.services.hotspot_service import detect_hotspots
from app.utils.deps import get_current_staff
from app.routers.issues import apply_data_scope, is_overdue, RESOLVED_TERMINAL_STATUSES

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/departments", response_model=list[DepartmentPerformance])
def department_performance(db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    depts = db.query(Department).order_by(Department.name).all()
    results = []
    for dept in depts:
        issues = db.query(Issue).filter(Issue.primary_department_id == dept.id).all()
        if not issues:
            continue
        open_issues = [i for i in issues if i.status not in RESOLVED_TERMINAL_STATUSES]
        critical = [i for i in open_issues if i.priority_level == "CRITICAL"]
        resolved = [i for i in issues if i.status == "RESOLVED"]
        backlog = [i for i in issues if i.status in ("SUBMITTED", "AI_VERIFIED", "MANUAL_REVIEW", "ASSIGNED")]
        overdue = [i for i in open_issues if is_overdue(i)]
        reopened = [i for i in issues if i.reopen_count > 0]

        response_times = [(i.accepted_at - i.created_at).total_seconds() / 3600 for i in issues if i.accepted_at]
        resolution_times = [(i.resolved_at - i.created_at).total_seconds() / 3600 for i in resolved if i.resolved_at]

        results.append(DepartmentPerformance(
            department=dept.name,
            open_issues=len(open_issues),
            critical_issues=len(critical),
            resolved_count=len(resolved),
            pending_backlog=len(backlog),
            overdue_issues=len(overdue),
            reopened_issues=len(reopened),
            avg_response_time_hours=round(sum(response_times) / len(response_times), 1) if response_times else 0.0,
            avg_resolution_time_hours=round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else 0.0,
        ))
    return results


@router.get("/categories", response_model=list[CategoryBreakdown])
def category_breakdown(db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    issues = db.query(Issue).all()
    counts: dict = {}
    for i in issues:
        counts[i.category] = counts.get(i.category, 0) + 1
    return [CategoryBreakdown(category=c, count=n) for c, n in sorted(counts.items(), key=lambda x: -x[1])]


@router.get("/hotspots", response_model=list[HotspotResponse])
def hotspots(db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    results = detect_hotspots(db)
    return [
        HotspotResponse(
            label=h.label, category=h.category, primary_issue_type=h.primary_issue_type,
            latitude=h.latitude, longitude=h.longitude, report_count=h.report_count,
            issue_count=h.issue_count, period_days=h.period_days,
            avg_recurrence_days=h.avg_recurrence_days, recommendation=h.recommendation,
        )
        for h in results
    ]


@router.get("/response-times", response_model=ResponseTimeAnalyticsResponse)
def response_times(data_scope: str = "live", db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    """Average/median time-to-assignment/accept/start-work/resolution,
    oldest unresolved issues, and average unresolved age. Entirely
    separate from app.services.core.priority — nothing here feeds
    priority calculation, and priority.py's own age factor is untouched."""
    issues = apply_data_scope(db.query(Issue), data_scope).all()
    result = compute_response_time_analytics(issues)
    return ResponseTimeAnalyticsResponse(
        avg_time_to_assignment_hours=result.avg_time_to_assignment_hours,
        median_time_to_assignment_hours=result.median_time_to_assignment_hours,
        avg_time_to_accept_hours=result.avg_time_to_accept_hours,
        median_time_to_accept_hours=result.median_time_to_accept_hours,
        avg_time_to_start_work_hours=result.avg_time_to_start_work_hours,
        avg_time_to_resolution_hours=result.avg_time_to_resolution_hours,
        median_time_to_resolution_hours=result.median_time_to_resolution_hours,
        avg_unresolved_age_hours=result.avg_unresolved_age_hours,
        oldest_unresolved=[OldestUnresolvedItem(**o) for o in result.oldest_unresolved],
    )


@router.get("/backlog", response_model=BacklogAnalyticsResponse)
def backlog(data_scope: str = "live", db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    """Open backlog per department, HIGH/CRITICAL backlog split, total
    resolved issues, and reopened-issue count."""
    issues = apply_data_scope(db.query(Issue), data_scope).all()
    result = compute_backlog_analytics(issues)
    return BacklogAnalyticsResponse(
        per_department=[DepartmentBacklogItem(**d) for d in result.per_department],
        high_backlog=result.high_backlog,
        critical_backlog=result.critical_backlog,
        total_open_backlog=result.total_open_backlog,
        total_resolved=result.total_resolved,
        reopened_count=result.reopened_count,
    )


@router.get("/heatmap", response_model=list[HeatmapPointResponse])
def heatmap(
    days: int = 30,
    category: str | None = None,
    data_scope: str = "live",
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
):
    """Recurring-issue heatmap: historical RESOLVED issues only (never
    the live/unresolved dashboard map data) — for municipal maintenance
    planning. See app.services.heatmap_service."""
    base_query = apply_data_scope(db.query(Issue), data_scope)
    points = get_heatmap_points(base_query, days=days, category=category)
    return [
        HeatmapPointResponse(
            latitude=p.latitude, longitude=p.longitude, weight=p.weight,
            category=p.category, issue_type=p.issue_type, complaint_id=p.complaint_id,
        )
        for p in points
    ]
