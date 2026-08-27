"""
heatmap_service.py

Recurring-issue heatmap aggregation, built from historical RESOLVED
issues only — deliberately NOT the same data as the live/unresolved
dashboard map (app.routers.dashboard.map_markers). Purpose: show
municipalities where problems keep recurring over time, for maintenance
planning ("6 road-damage issues reported within this zone in the last 30
days"), not where problems are open right now.

Every point comes from a real stored Issue row within the requested time
window/category — nothing here fabricates an insight.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Query

from app.models.issue import Issue

ALLOWED_PERIOD_DAYS = (7, 30, 90, 182)  # 182 ~= 6 months
DEFAULT_PERIOD_DAYS = 30


@dataclass
class HeatmapPoint:
    latitude: float
    longitude: float
    weight: int  # occurrence count backing this point (>= reporter_count)
    category: str
    issue_type: str
    complaint_id: str
    resolved_at: datetime | None


def get_heatmap_points(base_query: Query, *, days: int = DEFAULT_PERIOD_DAYS, category: str | None = None) -> list[HeatmapPoint]:
    """`base_query` is a Session.query(Issue) already narrowed by the
    caller's data_scope (live/demo/all) — see app.routers.issues.apply_data_scope
    — so this module doesn't need to know about that distinction itself."""
    if days not in ALLOWED_PERIOD_DAYS:
        days = DEFAULT_PERIOD_DAYS
    since = datetime.utcnow() - timedelta(days=days)

    query = (
        base_query
        .filter(Issue.status == "RESOLVED")
        .filter(Issue.resolved_at.isnot(None))
        .filter(Issue.resolved_at >= since)
    )
    if category and category.strip().lower() != "all":
        query = query.filter(Issue.category == category)

    issues: Iterable[Issue] = query.all()
    return [
        HeatmapPoint(
            latitude=i.latitude,
            longitude=i.longitude,
            weight=max(1, i.reporter_count),
            category=i.category,
            issue_type=i.issue_type,
            complaint_id=i.complaint_id,
            resolved_at=i.resolved_at,
        )
        for i in issues
    ]
