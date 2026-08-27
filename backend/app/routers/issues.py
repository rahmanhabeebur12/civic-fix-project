import json
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.config import settings
from app.database import get_db
from app.models.department import Department
from app.models.issue import Issue, StatusHistory
from app.models.resolution import Resolution
from app.models.staff import StaffUser
from app.schemas.issue import (
    ConfirmResolutionRequest, NoteRequest, ReviewDecisionRequest, StaffIssueDetail,
    StaffIssueSummary, StatusHistoryItem, TransferRequest, ResolutionInfo,
)
from app.services import priority_engine
from app.services.core import priority as core_priority
from app.services.image_sanitizer import ImageSanitizationError, read_upload_enforcing_limit, sanitize_image_bytes
from app.services.notification_service import notify
from app.services.reliability_service import compute_reliability
from app.utils.deps import get_current_staff
from app.utils.file_storage import resolve_url

public_router = APIRouter(prefix="/issues", tags=["issues"])
staff_router = APIRouter(prefix="/staff/issues", tags=["staff-issues"])

# The single source of truth for "operationally done" vs. "active" issue
# statuses — reused by the dashboard, analytics, and the staff Issues /
# Past Issues pages so they can never drift out of sync with each other.
PAST_ISSUE_STATUSES = ("RESOLVED", "REJECTED")
# ACTIVE_ISSUE_STATUSES is simply everything else (SUBMITTED, MANUAL_REVIEW,
# ASSIGNED, ACCEPTED, IN_PROGRESS, AWAITING_CITIZEN_VERIFICATION, REOPENED) —
# expressed as Issue.status.notin_(PAST_ISSUE_STATUSES) rather than a
# second literal list, so the two sets can't fall out of sync.


def _log_status(db: Session, issue: Issue, status: str, changed_by: str, note: str):
    db.add(StatusHistory(issue_id=issue.id, status=status, changed_by=changed_by, note=note))


def is_overdue(issue: Issue) -> bool:
    if issue.status in PAST_ISSUE_STATUSES:
        return False
    sla_hours = settings.SLA_HOURS.get(issue.severity, 72)
    # Issue.created_at is DateTime(timezone=True). SQLite ignores that
    # flag and always hands back a naive datetime, but PostgreSQL returns
    # a real timezone-aware one -- subtracting it from naive
    # datetime.utcnow() then raises "can't subtract offset-naive and
    # offset-aware datetimes" on Postgres only. created_at is always a
    # UTC instant in this app either way, so normalizing to naive UTC
    # here is correct on both backends.
    created_at = issue.created_at
    if created_at.tzinfo is not None:
        created_at = created_at.replace(tzinfo=None)
    age_hours = (datetime.utcnow() - created_at).total_seconds() / 3600
    return age_hours > sla_hours


LOW_AI_CONFIDENCE_THRESHOLD = 0.5
FALLBACK_CONFIDENCE = 0.3  # see issue_understanding_service._build_result_fallback


def compute_review_reasons(issue: Issue, first_report) -> list[str]:
    """Explains WHY an issue is (or was) in the manual review queue, using
    only signals that actually occurred — derived from fields already
    stored on Issue/IssueReport. Never guesses; a reason is included only
    when the underlying condition genuinely holds for this issue."""
    reasons: list[str] = []

    if first_report:
        if first_report.submission_mode == "PHOTO_ONLY":
            reasons.append("PHOTO_ONLY")
        elif first_report.submission_mode == "TEXT_ONLY":
            reasons.append("TEXT_ONLY")
        if first_report.accessibility_adjustment:
            reasons.append("ACCESSIBILITY_ADJUSTMENT")
        try:
            flags = json.loads(first_report.supplemental_flags or "[]")
        except json.JSONDecodeError:
            flags = []
        if any("frequency" in f.lower() for f in flags):
            reasons.append("SUSPICIOUS_FREQUENCY")

    if issue.duplicate_action == "REVIEW":
        reasons.append("POSSIBLE_DUPLICATE")

    if issue.category == "Other":
        reasons.append("UNKNOWN_CATEGORY")

    has_photo = bool(issue.image_path)
    if issue.ai_confidence <= FALLBACK_CONFIDENCE and has_photo:
        # A photo was provided but classification still landed in the
        # lowest-confidence fallback — the image-understanding step did
        # not produce a usable result for it.
        reasons.append("IMAGE_CLASSIFICATION_UNAVAILABLE")
    elif issue.ai_confidence < LOW_AI_CONFIDENCE_THRESHOLD:
        reasons.append("LOW_AI_CONFIDENCE")

    return reasons


def _reapply_priority(db: Session, issue: Issue) -> None:
    """Recompute priority via the canonical, unmodified
    app.services.core.priority.calculate_priority() — the only place
    priority is ever calculated for an already-existing issue."""
    payload = {
        "severity": issue.severity_level,
        "number_of_reporters": issue.reporter_count,
        "location_type": issue.location_type,
        "created_at": (issue.created_at or datetime.utcnow()).isoformat(),
        "impact_level": issue.impact_level,
    }
    result = core_priority.calculate_priority(payload)
    issue.priority_score = result["priority_score"]
    issue.priority_level = result["priority_level"]
    issue.priority_breakdown = json.dumps(result["breakdown"])
    issue.priority_reasons = json.dumps(result["reasons"])


# ---------------------------------------------------------------------------
# Public / citizen-facing issue actions
# ---------------------------------------------------------------------------

@public_router.post("/{complaint_id}/confirm-resolution")
def confirm_resolution(complaint_id: str, payload: ConfirmResolutionRequest, db: Session = Depends(get_db)):
    issue = db.query(Issue).filter(Issue.complaint_id == complaint_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    if issue.status != "AWAITING_CITIZEN_VERIFICATION":
        raise HTTPException(status_code=400, detail="This issue is not currently awaiting citizen verification.")

    resolution = (
        db.query(Resolution)
        .filter(Resolution.issue_id == issue.id, Resolution.citizen_confirmed.is_(None))
        .order_by(Resolution.created_at.desc())
        .first()
    )
    if not resolution:
        raise HTTPException(status_code=400, detail="No pending resolution to confirm.")

    resolution.citizen_confirmed = payload.confirmed
    resolution.citizen_feedback = payload.feedback or ""
    resolution.confirmed_at = datetime.utcnow()

    if payload.confirmed:
        issue.status = "RESOLVED"
        issue.resolved_at = datetime.utcnow()
        _log_status(db, issue, "RESOLVED", "citizen", "Citizen confirmed the issue was fixed.")
    else:
        issue.status = "REOPENED"
        issue.reopen_count += 1
        # Deterministic post-processing on top of the canonical priority
        # score — reopening isn't part of priority.py's mandate, so the
        # boost is applied here and then re-leveled via the canonical
        # priority.get_priority_level() (never a locally invented ladder).
        boosted_score = priority_engine.apply_reopen_boost(issue.priority_score, settings.REOPEN_PRIORITY_BOOST)
        issue.priority_score = boosted_score
        issue.priority_level = core_priority.get_priority_level(boosted_score)
        note = f"Citizen reported the issue is still unresolved. Reason: {payload.feedback or 'not specified'}"
        _log_status(db, issue, "REOPENED", "citizen", note)

    db.commit()
    return {"status": issue.status, "reopen_count": issue.reopen_count}


# ---------------------------------------------------------------------------
# Staff issue management
# ---------------------------------------------------------------------------

def _to_summary(issue: Issue) -> StaffIssueSummary:
    first_report = issue.reports[0] if issue.reports else None
    return StaffIssueSummary(
        id=issue.id,
        complaint_id=issue.complaint_id,
        issue_type=issue.issue_type,
        category=issue.category,
        latitude=issue.latitude,
        longitude=issue.longitude,
        severity=issue.severity,
        priority_level=issue.priority_level,
        priority_score=issue.priority_score,
        status=issue.status,
        validity_status=issue.validity_status,
        department=issue.primary_department.name if issue.primary_department else None,
        reporter_count=issue.reporter_count,
        reopen_count=issue.reopen_count,
        image_url=resolve_url(issue.image_path),
        is_overdue=is_overdue(issue),
        is_demo=issue.is_demo,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        resolved_at=issue.resolved_at,
        review_reasons=compute_review_reasons(issue, first_report),
    )


def apply_data_scope(query, data_scope: str | None):
    """Filters a query of Issue by data_scope: 'live' (real citizen reports
    only), 'demo' (seeded data only), or anything else / None -> unfiltered.
    Seeded demo data is never deleted (it powers analytics/hotspot/duplicate
    demos) — this only controls what a given view shows."""
    if data_scope == "live":
        return query.filter(Issue.is_demo.is_(False))
    if data_scope == "demo":
        return query.filter(Issue.is_demo.is_(True))
    return query


@staff_router.get("", response_model=list[StaffIssueSummary])
def list_issues(
    department_id: int | None = None,
    category: str | None = None,
    issue_type: str | None = None,
    severity: str | None = None,
    priority_level: str | None = None,
    status: str | None = None,
    validity_status: str | None = None,
    reopened_only: bool = False,
    overdue_only: bool = False,
    min_reporters: int | None = None,
    search: str | None = None,
    data_scope: str | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
):
    query = db.query(Issue)
    query = apply_data_scope(query, data_scope)
    if active_only:
        # RESOLVED/REJECTED issues are operationally done — the main
        # dashboard/active views should never show them. They remain in
        # the same database and are still reachable via status=RESOLVED
        # (Past Issues) or status=REJECTED filters; nothing is deleted.
        query = query.filter(Issue.status.notin_(PAST_ISSUE_STATUSES))
    if department_id:
        query = query.filter(Issue.primary_department_id == department_id)
    if category:
        query = query.filter(Issue.category == category)
    if issue_type:
        query = query.filter(Issue.issue_type == issue_type)
    if severity:
        query = query.filter(Issue.severity == severity)
    if priority_level:
        query = query.filter(Issue.priority_level == priority_level)
    if status:
        query = query.filter(Issue.status == status)
    if validity_status:
        query = query.filter(Issue.validity_status == validity_status)
    if reopened_only:
        query = query.filter(Issue.reopen_count > 0)
    if min_reporters:
        query = query.filter(Issue.reporter_count >= min_reporters)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Issue.complaint_id.ilike(like), Issue.location_context.ilike(like), Issue.address.ilike(like)))

    issues = query.order_by(Issue.priority_score.desc(), Issue.created_at.desc()).all()

    if overdue_only:
        issues = [i for i in issues if is_overdue(i)]

    return [_to_summary(i) for i in issues]


@staff_router.get("/{issue_id}", response_model=StaffIssueDetail)
def get_issue(issue_id: int, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    issue = db.query(Issue).get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")

    first_report = issue.reports[0] if issue.reports else None

    def _safe_json(raw, default):
        try:
            return json.loads(raw) if raw else default
        except json.JSONDecodeError:
            return default

    priority_breakdown = _safe_json(issue.priority_breakdown, {})
    priority_reasons = _safe_json(issue.priority_reasons, [])
    duplicate_breakdown = _safe_json(issue.duplicate_breakdown, {})

    # Validation transparency comes from the founding report (the one that
    # determined whether this Issue was created / sent to manual review).
    validity_score = first_report.validity_score if first_report else 0.0
    validity_breakdown = _safe_json(first_report.validity_breakdown if first_report else None, {})
    validation_errors = _safe_json(first_report.validation_errors if first_report else None, [])

    return StaffIssueDetail(
        id=issue.id,
        complaint_id=issue.complaint_id,
        issue_type=issue.issue_type,
        category=issue.category,
        is_demo=issue.is_demo,
        description=first_report.normalized_description if first_report else "",
        original_description=first_report.original_description if first_report else "",
        image_url=resolve_url(issue.image_path),
        latitude=issue.latitude,
        longitude=issue.longitude,
        address=issue.address or "",
        severity=issue.severity,
        severity_level=issue.severity_level,
        severity_reason=issue.severity_reason,
        impact_level=issue.impact_level,
        location_type=issue.location_type,
        location_context=issue.location_context,
        priority_score=issue.priority_score,
        priority_level=issue.priority_level,
        priority_breakdown=priority_breakdown,
        priority_reasons=priority_reasons,
        department=issue.primary_department.name if issue.primary_department else None,
        department_id=issue.primary_department_id,
        supporting_department=issue.supporting_department.name if issue.supporting_department else None,
        ai_confidence=issue.ai_confidence,
        ai_reasoning=issue.ai_reasoning,
        status=issue.status,
        validity_status=issue.validity_status,
        validity_score=validity_score,
        validity_breakdown=validity_breakdown,
        validation_errors=validation_errors,
        duplicate_score=issue.duplicate_score,
        duplicate_confidence=issue.duplicate_confidence,
        duplicate_action=issue.duplicate_action,
        duplicate_breakdown=duplicate_breakdown,
        duplicate_distance_meters=issue.duplicate_distance_meters,
        reporter_count=issue.reporter_count,
        reopen_count=issue.reopen_count,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        accepted_at=issue.accepted_at,
        accepted_by=issue.accepted_by,
        work_started_at=issue.work_started_at,
        resolved_at=issue.resolved_at,
        is_overdue=is_overdue(issue),
        sla_hours=settings.SLA_HOURS.get(issue.severity, 72),
        review_reasons=compute_review_reasons(issue, first_report),
        timeline=[StatusHistoryItem.model_validate(s) for s in issue.status_history],
        resolutions=[
            ResolutionInfo(
                image_url=resolve_url(r.image_path), note=r.note, officer_username=r.officer_username,
                created_at=r.created_at, citizen_confirmed=r.citizen_confirmed,
                citizen_feedback=r.citizen_feedback or "", confirmed_at=r.confirmed_at,
            ) for r in issue.resolutions
        ],
        reports=[
            {
                "id": r.id,
                "original_description": r.original_description,
                "image_url": resolve_url(r.image_path),
                "submission_mode": r.submission_mode,
                "accessibility_adjustment": r.accessibility_adjustment,
                "validity_score": r.validity_score,
                "validity_status": r.validity_status,
                "validation_errors": _safe_json(r.validation_errors, []),
                "supplemental_flags": _safe_json(r.supplemental_flags, []),
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                "was_offline": r.was_offline,
                # Staff-facing trust context ONLY — never read by
                # app.services.core.priority. See reliability_service.py.
                "reporter_reliability": _reliability_payload(db, r.user_id),
            }
            for r in issue.reports
        ],
    )


def _reliability_payload(db: Session, user_id: int | None) -> dict:
    result = compute_reliability(db, user_id)
    return {
        "score": result.score,
        "label": result.label,
        "breakdown": result.breakdown,
        "total_reports": result.total_reports,
        "resolved_as_genuine": result.resolved_as_genuine,
        "account_age_days": result.account_age_days,
    }


@staff_router.post("/{issue_id}/accept")
def accept_issue(issue_id: int, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    issue = db.query(Issue).get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    if issue.status not in ("SUBMITTED", "AI_VERIFIED", "ASSIGNED"):
        raise HTTPException(status_code=400, detail=f"Cannot accept an issue in status {issue.status}.")

    issue.status = "ACCEPTED"
    issue.accepted_at = datetime.utcnow()
    issue.accepted_by = staff.full_name
    _log_status(db, issue, "ACCEPTED", staff.full_name, "Officer accepted the issue.")

    for r in issue.reports:
        if r.user_id:
            notify(db, user_id=r.user_id, issue_id=issue.id, complaint_id=issue.complaint_id,
                   title=f"Officer accepted your report — {issue.complaint_id}",
                   message="A municipal officer has accepted your report and will begin work soon.",
                   notif_type="accepted")
    db.commit()
    return {"status": issue.status}


@staff_router.post("/{issue_id}/start-work")
def start_work(issue_id: int, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    issue = db.query(Issue).get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    if issue.status not in ("ACCEPTED", "REOPENED"):
        raise HTTPException(status_code=400, detail="Issue must be accepted (or reopened) before starting work.")

    issue.status = "IN_PROGRESS"
    issue.work_started_at = datetime.utcnow()
    _log_status(db, issue, "IN_PROGRESS", staff.full_name, "Work started on the issue.")

    for r in issue.reports:
        if r.user_id:
            notify(db, user_id=r.user_id, issue_id=issue.id, complaint_id=issue.complaint_id,
                   title=f"Work started — {issue.complaint_id}",
                   message="Work has started on your reported issue.", notif_type="work_started")
    db.commit()
    return {"status": issue.status}


@staff_router.post("/{issue_id}/transfer")
def transfer_issue(issue_id: int, payload: TransferRequest, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    issue = db.query(Issue).get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    dept = db.query(Department).get(payload.department_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found.")

    old_dept_name = issue.primary_department.name if issue.primary_department else "Unassigned"
    issue.primary_department_id = dept.id
    issue.status = "TRANSFERRED"
    _log_status(db, issue, "TRANSFERRED", staff.full_name, f"Transferred from {old_dept_name} to {dept.name}. {payload.note or ''}".strip())
    issue.status = "ASSIGNED"
    db.commit()
    return {"status": issue.status, "department": dept.name}


@staff_router.post("/{issue_id}/note")
def add_note(issue_id: int, payload: NoteRequest, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    issue = db.query(Issue).get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    _log_status(db, issue, issue.status, staff.full_name, f"Note: {payload.note}")
    db.commit()
    return {"ok": True}


@staff_router.post("/{issue_id}/resolve")
async def resolve_issue(
    issue_id: int,
    note: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    staff: StaffUser = Depends(get_current_staff),
):
    issue = db.query(Issue).get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    if issue.status != "IN_PROGRESS":
        raise HTTPException(status_code=400, detail="Work must be in progress before submitting a resolution.")

    # Officer-uploaded resolution evidence is just as untrusted as a
    # citizen upload — it goes through the exact same canonical sanitizer,
    # not a second/looser validator.
    raw_bytes = await read_upload_enforcing_limit(image)
    try:
        sanitized = sanitize_image_bytes(raw_bytes, subdir="resolutions")
    except ImageSanitizationError as e:
        raise HTTPException(status_code=400, detail=e.user_message)
    image_path = sanitized.sanitized_path

    resolution = Resolution(issue_id=issue.id, officer_username=staff.username, image_path=image_path, note=note)
    db.add(resolution)

    issue.status = "AWAITING_CITIZEN_VERIFICATION"
    _log_status(db, issue, "AWAITING_CITIZEN_VERIFICATION", staff.full_name, "Resolution evidence submitted; awaiting citizen verification.")

    for r in issue.reports:
        if r.user_id:
            notify(db, user_id=r.user_id, issue_id=issue.id, complaint_id=issue.complaint_id,
                   title=f"Resolution submitted — {issue.complaint_id}",
                   message="The department has submitted proof of resolution. Please verify.",
                   notif_type="resolution_submitted")
    db.commit()
    return {"status": issue.status}


@staff_router.post("/{issue_id}/review-decision")
def review_decision(issue_id: int, payload: ReviewDecisionRequest, db: Session = Depends(get_db), staff: StaffUser = Depends(get_current_staff)):
    issue = db.query(Issue).get(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")
    if issue.status != "MANUAL_REVIEW":
        raise HTTPException(status_code=400, detail="This issue is not in the manual review queue.")

    if payload.decision == "APPROVED":
        issue.status = "ASSIGNED"
        issue.validity_status = "VALID"
        _log_status(db, issue, "ASSIGNED", staff.full_name, f"Manual review approved. {payload.note or ''}".strip())
    elif payload.decision == "REJECTED":
        issue.status = "REJECTED"
        _log_status(db, issue, "REJECTED", staff.full_name, f"Manual review rejected. {payload.note or ''}".strip())
    else:
        raise HTTPException(status_code=400, detail="Decision must be APPROVED or REJECTED.")

    db.commit()
    return {"status": issue.status}
