"""
DB adapter for the canonical duplicate engine (app/services/core/duplicate.py).

This module does NOT score duplicates itself — it only loads candidate
Issues from the database and converts them into the plain-dict payload
shape that duplicate.get_duplicate_recommendation() expects. All actual
scoring (location/category/description/photo weighting, Haversine
distance, HIGH/POSSIBLE/NONE thresholds) lives exclusively in that
canonical module, completely unmodified.

Candidate selection itself is filtered at the DB level BEFORE the
canonical engine ever sees a candidate — same/similar category, live
(non-demo), active status, a recent time window, and a coarse geographic
bounding box. This only narrows the candidate SET (cheaper queries, no
comparing a new report against a 2-year-old closed issue on the other
side of the city); it never changes duplicate.py's scoring formula or
HIGH/POSSIBLE/NONE thresholds.
"""
import math
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.issue import Issue

ACTIVE_STATUSES = (
    "SUBMITTED", "AI_VERIFIED", "MANUAL_REVIEW", "ASSIGNED", "ACCEPTED", "IN_PROGRESS",
    "AWAITING_CITIZEN_VERIFICATION", "REOPENED",
)

# Degrees-per-meter is latitude-dependent for longitude, but a generous
# fixed approximation is fine here — this is only a coarse pre-filter to
# shrink the candidate set; the canonical duplicate.py still does the
# real Haversine distance scoring on whatever survives it.
_METERS_PER_DEGREE_LAT = 111_320.0


def load_candidate_issues(
    db: Session,
    *,
    category: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> list[dict[str, Any]]:
    """Loads active, real (non-demo), recent, geographically-nearby issues
    in the same category as duplicate-check candidates.

    Restricting to is_demo=False is deliberate and mandatory: a live
    citizen report must never be compared against — and therefore never
    silently merged into — seeded demo data.
    """
    query = (
        db.query(Issue)
        .filter(Issue.status.in_(ACTIVE_STATUSES))
        .filter(Issue.category == category)
        .filter(Issue.is_demo.is_(False))
    )

    lookback_days = settings.DUPLICATE_CANDIDATE_LOOKBACK_DAYS
    if lookback_days > 0:
        since = datetime.utcnow() - timedelta(days=lookback_days)
        query = query.filter(Issue.created_at >= since)

    if latitude is not None and longitude is not None:
        max_meters = settings.DUPLICATE_CANDIDATE_MAX_DISTANCE_METERS
        lat_delta = max_meters / _METERS_PER_DEGREE_LAT
        # Longitude degrees shrink toward the poles; this is only a coarse
        # box — the canonical engine's Haversine distance is still the
        # real filter downstream.
        lon_delta = max_meters / (_METERS_PER_DEGREE_LAT * max(0.1, math.cos(math.radians(latitude))))
        query = query.filter(Issue.latitude.between(latitude - lat_delta, latitude + lat_delta))
        query = query.filter(Issue.longitude.between(longitude - lon_delta, longitude + lon_delta))

    issues = query.all()

    candidates: list[dict[str, Any]] = []
    for issue in issues:
        first_report = issue.reports[0] if issue.reports else None
        candidates.append({
            "id": issue.id,
            "category": issue.category,
            "description": first_report.original_description if first_report else "",
            "latitude": issue.latitude,
            "longitude": issue.longitude,
            "photo_path": issue.image_path,
        })
    return candidates
