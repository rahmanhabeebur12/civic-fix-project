"""
reliability_service.py

Explainable REPORTER RELIABILITY signal, for staff-facing trust context
only.

IMPORTANT — account reliability != issue urgency. This score is NEVER
read by app.services.core.priority (see
report_pipeline._priority_payload_for, which only ever builds severity/
number_of_reporters/location_type/created_at/impact_level). A highly
reliable citizen's report is not prioritized above an equally severe
report from a brand-new citizen — priority stays based solely on the
canonical priority.py factors.

Computed on demand from existing data (no new persisted score column, so
there is nothing to keep in sync) but fully explainable via `breakdown`.
Report volume alone is deliberately capped low — reliability is built by
reports that were actually confirmed genuine, not by submitting many
reports.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.issue import Issue, IssueReport
from app.models.user import User

# Component caps — tuned so genuine, citizen-confirmed resolutions
# dominate the score and raw submission volume never can.
MAX_GENUINE_COMPONENT = 50
GENUINE_POINTS_PER_RESOLUTION = 10
MAX_AGE_COMPONENT = 20
AGE_POINTS_PER_WEEK = 1
MAX_VOLUME_COMPONENT = 10
ABUSE_PENALTY_PER_FLAG = 20
MAX_ABUSE_PENALTY = 60

TRUSTED_MIN_SCORE = 60
BUILDING_MIN_SCORE = 20


@dataclass
class ReliabilityResult:
    score: int  # 0-100
    label: str  # NEW | BUILDING | TRUSTED
    breakdown: dict
    total_reports: int
    resolved_as_genuine: int
    rejected_or_suspicious: int
    account_age_days: int


def _empty_result() -> ReliabilityResult:
    return ReliabilityResult(
        score=0, label="NEW", breakdown={}, total_reports=0,
        resolved_as_genuine=0, rejected_or_suspicious=0, account_age_days=0,
    )


def compute_reliability(db: Session, user_id: int | None) -> ReliabilityResult:
    if not user_id:
        return _empty_result()

    user = db.query(User).get(user_id)
    if not user:
        return _empty_result()

    reports = db.query(IssueReport).filter(IssueReport.user_id == user_id).all()
    total_reports = len(reports)

    resolved_as_genuine = 0
    rejected_or_suspicious = 0
    seen_issue_ids: set[int] = set()
    for r in reports:
        if r.validity_status == "SUSPICIOUS":
            rejected_or_suspicious += 1
        if not r.issue_id or r.issue_id in seen_issue_ids:
            continue
        seen_issue_ids.add(r.issue_id)
        issue = db.query(Issue).get(r.issue_id)
        if not issue:
            continue
        if issue.status == "REJECTED":
            rejected_or_suspicious += 1
        elif issue.status == "RESOLVED" and any(res.citizen_confirmed is True for res in issue.resolutions):
            resolved_as_genuine += 1

    account_age_days = 0
    if user.created_at:
        now = datetime.now(timezone.utc)
        created = user.created_at if user.created_at.tzinfo else user.created_at.replace(tzinfo=timezone.utc)
        account_age_days = max(0, (now - created).days)

    genuine_component = min(MAX_GENUINE_COMPONENT, resolved_as_genuine * GENUINE_POINTS_PER_RESOLUTION)
    age_component = min(MAX_AGE_COMPONENT, (account_age_days // 7) * AGE_POINTS_PER_WEEK)
    volume_component = min(MAX_VOLUME_COMPONENT, total_reports)
    abuse_penalty = min(MAX_ABUSE_PENALTY, rejected_or_suspicious * ABUSE_PENALTY_PER_FLAG)

    score = max(0, min(100, genuine_component + age_component + volume_component - abuse_penalty))

    if score >= TRUSTED_MIN_SCORE and rejected_or_suspicious == 0:
        label = "TRUSTED"
    elif score >= BUILDING_MIN_SCORE:
        label = "BUILDING"
    else:
        label = "NEW"

    return ReliabilityResult(
        score=score,
        label=label,
        breakdown={
            "genuine_resolutions_component": genuine_component,
            "account_age_component": age_component,
            "report_volume_component": volume_component,
            "abuse_penalty": -abuse_penalty,
        },
        total_reports=total_reports,
        resolved_as_genuine=resolved_as_genuine,
        rejected_or_suspicious=rejected_or_suspicious,
        account_age_days=account_age_days,
    )
