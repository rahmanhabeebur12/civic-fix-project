"""Recurring civic hotspot detection.

Groups nearby issues (same category) into geographic clusters using simple
greedy radius clustering — good enough for city-scale demo data without
needing a full geospatial stack.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.models.issue import Issue
from app.services.location_service import haversine_meters

CLUSTER_RADIUS_METERS = 400
MIN_REPORTS_FOR_HOTSPOT = 3
LOOKBACK_DAYS = 90


@dataclass
class Hotspot:
    label: str
    category: str
    primary_issue_type: str
    latitude: float
    longitude: float
    report_count: int
    issue_count: int
    period_days: int
    avg_recurrence_days: float
    recommendation: str


def detect_hotspots(db: Session) -> List[Hotspot]:
    since = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)
    issues = db.query(Issue).filter(Issue.created_at >= since).all()

    clusters: List[List[Issue]] = []

    for issue in issues:
        placed = False
        for cluster in clusters:
            rep = cluster[0]
            if rep.category == issue.category and haversine_meters(rep.latitude, rep.longitude, issue.latitude, issue.longitude) <= CLUSTER_RADIUS_METERS:
                cluster.append(issue)
                placed = True
                break
        if not placed:
            clusters.append([issue])

    hotspots: List[Hotspot] = []
    for cluster in clusters:
        total_reports = sum(i.reporter_count for i in cluster)
        if total_reports < MIN_REPORTS_FOR_HOTSPOT or len(cluster) < 2:
            continue

        avg_lat = sum(i.latitude for i in cluster) / len(cluster)
        avg_lng = sum(i.longitude for i in cluster) / len(cluster)

        type_counts: dict = {}
        for i in cluster:
            type_counts[i.issue_type] = type_counts.get(i.issue_type, 0) + i.reporter_count
        primary_type = max(type_counts, key=type_counts.get)

        dates = sorted(i.created_at for i in cluster if i.created_at)
        if len(dates) >= 2:
            gaps = [(dates[k + 1] - dates[k]).total_seconds() / 86400 for k in range(len(dates) - 1)]
            avg_recurrence = round(sum(gaps) / len(gaps), 1)
        else:
            avg_recurrence = 0.0

        hotspots.append(Hotspot(
            label=f"{cluster[0].category} Hotspot near ({avg_lat:.4f}, {avg_lng:.4f})",
            category=cluster[0].category,
            primary_issue_type=primary_type,
            latitude=avg_lat,
            longitude=avg_lng,
            report_count=total_reports,
            issue_count=len(cluster),
            period_days=LOOKBACK_DAYS,
            avg_recurrence_days=avg_recurrence,
            recommendation=(
                f"Repeated {primary_type.lower()} reports detected in this area. "
                "This is a planning insight, not a guaranteed diagnosis — "
                "recommend an infrastructure-level inspection."
            ),
        ))

    hotspots.sort(key=lambda h: h.report_count, reverse=True)
    return hotspots
