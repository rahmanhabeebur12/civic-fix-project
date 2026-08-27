"""
analytics_service.py

Department response-time and backlog analytics. Completely separate from
app.services.core.priority — nothing here feeds priority calculation, and
priority.py's own tested age factor is never touched or replaced.

Uses only existing Issue lifecycle timestamps (created_at, assigned_at,
accepted_at, work_started_at, resolved_at) — no new lifecycle columns
were added. "Citizen verification" reuses Resolution.confirmed_at and
"reopened" reuses Issue.reopen_count / StatusHistory, both of which
already exist.

All arithmetic goes through _as_utc() so it behaves identically whether
the DB driver returns naive-UTC (SQLite) or timezone-aware (PostgreSQL)
datetimes for a DateTime(timezone=True) column.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median
from typing import Iterable

CLOSED_STATUSES = ("RESOLVED", "REJECTED")
BACKLOG_STATUSES = ("SUBMITTED", "AI_VERIFIED", "MANUAL_REVIEW", "ASSIGNED")


def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _hours_between(start: datetime | None, end: datetime | None) -> float | None:
    start_utc, end_utc = _as_utc(start), _as_utc(end)
    if start_utc is None or end_utc is None:
        return None
    return max(0.0, (end_utc - start_utc).total_seconds() / 3600.0)


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 1) if values else 0.0


def _median(values: list[float]) -> float:
    return round(median(values), 1) if values else 0.0


@dataclass
class ResponseTimeAnalytics:
    avg_time_to_assignment_hours: float
    median_time_to_assignment_hours: float
    avg_time_to_accept_hours: float
    median_time_to_accept_hours: float
    avg_time_to_start_work_hours: float
    avg_time_to_resolution_hours: float
    median_time_to_resolution_hours: float
    avg_unresolved_age_hours: float
    oldest_unresolved: list[dict]


def compute_response_time_analytics(issues: Iterable, *, oldest_limit: int = 5, now: datetime | None = None) -> ResponseTimeAnalytics:
    """`now` is injectable for deterministic tests; defaults to the real
    current time (timezone-aware UTC)."""
    issues = list(issues)
    now = _as_utc(now) or datetime.now(timezone.utc)

    to_assignment = [h for i in issues if (h := _hours_between(i.created_at, i.assigned_at)) is not None]
    to_accept = [h for i in issues if (h := _hours_between(i.created_at, i.accepted_at)) is not None]
    to_start = [h for i in issues if (h := _hours_between(i.created_at, i.work_started_at)) is not None]
    to_resolution = [
        h for i in issues
        if i.status == "RESOLVED" and (h := _hours_between(i.created_at, i.resolved_at)) is not None
    ]

    # Unresolved age must stop growing once an issue is closed — only
    # currently-open issues are included here, and their age is measured
    # against `now`, never continuing past resolution.
    unresolved = [i for i in issues if i.status not in CLOSED_STATUSES]
    unresolved_ages = [h for i in unresolved if (h := _hours_between(i.created_at, now)) is not None]

    oldest = sorted(unresolved, key=lambda i: _as_utc(i.created_at) or now)[:oldest_limit]
    oldest_payload = [
        {
            "complaint_id": i.complaint_id,
            "issue_type": i.issue_type,
            "status": i.status,
            "priority_level": i.priority_level,
            "age_hours": round(_hours_between(i.created_at, now) or 0.0, 1),
        }
        for i in oldest
    ]

    return ResponseTimeAnalytics(
        avg_time_to_assignment_hours=_avg(to_assignment),
        median_time_to_assignment_hours=_median(to_assignment),
        avg_time_to_accept_hours=_avg(to_accept),
        median_time_to_accept_hours=_median(to_accept),
        avg_time_to_start_work_hours=_avg(to_start),
        avg_time_to_resolution_hours=_avg(to_resolution),
        median_time_to_resolution_hours=_median(to_resolution),
        avg_unresolved_age_hours=_avg(unresolved_ages),
        oldest_unresolved=oldest_payload,
    )


@dataclass
class BacklogAnalytics:
    per_department: list[dict]
    high_backlog: int
    critical_backlog: int
    total_open_backlog: int
    total_resolved: int
    reopened_count: int


def compute_backlog_analytics(issues: Iterable) -> BacklogAnalytics:
    issues = list(issues)
    backlog = [i for i in issues if i.status in BACKLOG_STATUSES]
    resolved = [i for i in issues if i.status == "RESOLVED"]
    reopened = [i for i in issues if i.reopen_count > 0]

    per_dept: dict[str, dict] = {}
    for i in backlog:
        dept_name = i.primary_department.name if i.primary_department else "Unassigned"
        entry = per_dept.setdefault(dept_name, {"department": dept_name, "backlog": 0, "high_backlog": 0, "critical_backlog": 0})
        entry["backlog"] += 1
        if i.priority_level == "HIGH":
            entry["high_backlog"] += 1
        elif i.priority_level == "CRITICAL":
            entry["critical_backlog"] += 1

    return BacklogAnalytics(
        per_department=sorted(per_dept.values(), key=lambda d: -d["backlog"]),
        high_backlog=sum(1 for i in backlog if i.priority_level == "HIGH"),
        critical_backlog=sum(1 for i in backlog if i.priority_level == "CRITICAL"),
        total_open_backlog=len(backlog),
        total_resolved=len(resolved),
        reopened_count=len(reopened),
    )
