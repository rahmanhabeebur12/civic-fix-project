"""
report_pipeline.py

Single orchestrator for the citizen report lifecycle. This is the only
place in the app that chains AI understanding -> validation -> duplicate
detection -> priority assignment -> routing -> persistence. Routers must
not reimplement any part of this decision logic — they only translate
HTTP input into a call here and translate the result back into a response.

Pipeline:

    Receive citizen report
    -> Normalize input / save image
    -> AI / rule-based UNDERSTANDING          (issue_understanding_service)
    -> Load nearby live (non-demo) candidates  (duplicate_detector)
    -> VALIDATION                              (app.services.core.validator)
    -> Handle VALID / REVIEW / SUSPICIOUS
    -> DUPLICATE CHECK (skipped if SUSPICIOUS) (app.services.core.duplicate)
    -> CREATE_NEW / REVIEW / LINK_TO_EXISTING
    -> PRIORITY ASSIGNMENT                     (app.services.core.priority)
    -> Department routing                      (routing_service)
    -> Persist all results
    -> Return (Issue, IssueReport, already_processed)

Ideology: AI/rules understand the report; validator.py, duplicate.py, and
priority.py — unmodified, canonical, deterministic modules under
app/services/core/ — make every final civic decision.
"""
import json
import os
from datetime import datetime

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models.issue import Issue, IssueReport, StatusHistory
from app.models.user import User
from app.services import issue_understanding_service, routing_service
from app.services.core import duplicate as core_duplicate
from app.services.core import priority as core_priority
from app.services.duplicate_detector import load_candidate_issues
from app.services.image_sanitizer import (
    ImageSanitizationError, delete_sanitized_image, read_upload_enforcing_limit, sanitize_image_bytes,
)
from app.services.notification_service import notify
from app.services.rate_limiter import check_rate_limit
from app.services.review_routing import evaluate_manual_review
from app.services.spam_detector import detect_supplemental_flags, hash_image_bytes
from app.services.taxonomy import to_validator_category
from app.services.validation_adapter import calculate_validity_adaptive, determine_submission_mode
from app.utils.id_generator import generate_complaint_id


def _get_or_create_user(db: Session, name: str, mobile: str) -> User:
    user = db.query(User).filter(User.mobile == mobile).first()
    if user:
        if name and user.name != name:
            user.name = name
        return user
    user = User(name=name or "Citizen", mobile=mobile)
    db.add(user)
    db.flush()
    return user


def _log_status(db: Session, issue: Issue, status: str, changed_by: str, note: str) -> None:
    db.add(StatusHistory(issue_id=issue.id, status=status, changed_by=changed_by, note=note))


def _priority_payload_for(issue: Issue) -> dict:
    return {
        "severity": issue.severity_level,
        "number_of_reporters": issue.reporter_count,
        "location_type": issue.location_type,
        "created_at": (issue.created_at or datetime.utcnow()).isoformat(),
        "impact_level": issue.impact_level,
    }


def _apply_priority(db: Session, issue: Issue) -> None:
    """The ONLY place priority is ever calculated — always via the
    canonical, unmodified app.services.core.priority.calculate_priority()."""
    result = core_priority.calculate_priority(_priority_payload_for(issue))
    issue.priority_score = result["priority_score"]
    issue.priority_level = result["priority_level"]
    issue.priority_breakdown = json.dumps(result["breakdown"])
    issue.priority_reasons = json.dumps(result["reasons"])


async def process_citizen_report(
    db: Session,
    *,
    client_report_id: str,
    description: str | None,
    latitude: float,
    longitude: float,
    accuracy: float | None,
    language: str,
    name: str,
    mobile: str,
    was_offline: bool,
    image: UploadFile | None,
    description_source: str = "TYPED",
    client_ip_hash: str | None = None,
) -> tuple[Issue, IssueReport, bool]:
    """Runs one citizen report through the full deterministic pipeline.

    `description_source` ("TYPED" | "VOICE") is analytics-only metadata —
    whether the description text originated from speech-to-text. It never
    affects submission_mode, validation, duplicate detection, or priority.

    `client_ip_hash` is a weak anti-abuse signal only (see
    app.services.rate_limiter) — never a duplicate/validity/priority input.

    Either `image` or a non-empty `description` is required — never both.
    This is an accessibility requirement: a citizen who cannot type and a
    citizen who cannot use a camera must both still be able to report.
    Only a report with *neither* is rejected.

    Returns (issue, report, already_processed). already_processed=True
    means client_report_id was seen before and no new processing occurred
    — the caller should treat this exactly like a fresh success response
    built from the existing records (idempotency).
    """

    # ------------------------------------------------------------------
    # IDEMPOTENCY — the same client_report_id (online or offline-synced)
    # must never be processed twice.
    # ------------------------------------------------------------------
    existing = db.query(IssueReport).filter(IssueReport.client_report_id == client_report_id).first()
    if existing and existing.issue_id:
        issue = db.query(Issue).get(existing.issue_id)
        return issue, existing, True

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(status_code=400, detail="Invalid GPS coordinates.")

    # ------------------------------------------------------------------
    # RATE LIMITING — a citizen's mobile-derived user_id is the primary
    # identity key; offline-originated reports are exempt (see
    # rate_limiter.py). Checked before any expensive work (image
    # sanitization, AI understanding) so an over-limit request fails fast.
    # ------------------------------------------------------------------
    identity_user = db.query(User).filter(User.mobile == mobile).first()
    check_rate_limit(
        db,
        user_id=identity_user.id if identity_user else None,
        client_ip_hash=client_ip_hash,
        was_offline=was_offline,
    )

    has_photo = image is not None
    has_description = bool((description or "").strip())
    if not has_photo and not has_description:
        raise HTTPException(status_code=400, detail="Please provide either a photo or a description.")

    submission_mode = determine_submission_mode(description, has_photo)

    # ------------------------------------------------------------------
    # SECURE IMAGE UPLOAD — only when a photo was actually provided. The
    # untrusted upload is streamed with a size cap enforced during the
    # read itself (not just Content-Length), then passed through the
    # single canonical sanitizer (decode, strip metadata, resize,
    # re-encode under a server-generated name) before anything else in
    # the app — including validator.py — ever sees a file path. The raw
    # bytes are held only in memory. A missing photo is never fabricated
    # — it is passed through as "" (validator's own honest zero-score
    # for that factor), never invented.
    # ------------------------------------------------------------------
    if has_photo:
        raw_bytes = await read_upload_enforcing_limit(image)
        image_hash = hash_image_bytes(raw_bytes)
        try:
            sanitized = sanitize_image_bytes(raw_bytes, subdir="reports")
        except ImageSanitizationError as e:
            raise HTTPException(status_code=400, detail=e.user_message)
        relative_image_path = sanitized.sanitized_path
        absolute_image_path = os.path.join(settings.UPLOAD_DIR, relative_image_path)
    else:
        image_hash = None
        relative_image_path = ""
        absolute_image_path = ""

    try:
        return _run_pipeline(
            db,
            client_report_id=client_report_id,
            description=(description or "").strip(),
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
            language=language,
            name=name,
            mobile=mobile,
            was_offline=was_offline,
            submission_mode=submission_mode,
            description_source=description_source if description_source in ("TYPED", "VOICE") else "TYPED",
            client_ip_hash=client_ip_hash,
            image_hash=image_hash,
            relative_image_path=relative_image_path,
            absolute_image_path=absolute_image_path,
        )
    except Exception:
        # Don't strand a sanitized file on disk if anything downstream
        # (classification, validation, persistence, ...) fails — no Issue
        # or IssueReport row exists in that case either, since nothing
        # was committed yet.
        if relative_image_path:
            delete_sanitized_image(relative_image_path)
        raise


def _run_pipeline(
    db: Session,
    *,
    client_report_id: str,
    description: str,
    latitude: float,
    longitude: float,
    accuracy: float | None,
    language: str,
    name: str,
    mobile: str,
    was_offline: bool,
    submission_mode: str,
    description_source: str,
    client_ip_hash: str | None,
    image_hash: str | None,
    relative_image_path: str,
    absolute_image_path: str,
) -> tuple[Issue, IssueReport, bool]:
    user = _get_or_create_user(db, name, mobile)

    # ------------------------------------------------------------------
    # AI / RULE-BASED UNDERSTANDING — produces category, severity (1-5),
    # impact_level (1-5), location_type, confidence. This step only
    # *understands* the report; it never decides validity/duplicate/
    # priority itself.
    # ------------------------------------------------------------------
    classification = issue_understanding_service.classify_report(db, description, relative_image_path, latitude, longitude)
    validator_category = to_validator_category(classification.issue_type)

    # Candidates are loaded once, up front: their COUNT feeds validator's
    # duplicate-evidence factor, and the same list is reused for the
    # actual duplicate check below (no need to query twice). Only real,
    # live (non-demo) issues are ever candidates.
    candidates = load_candidate_issues(db, category=classification.category, latitude=latitude, longitude=longitude)
    user_previous_reports = db.query(IssueReport).filter(IssueReport.user_id == user.id).count()

    # ------------------------------------------------------------------
    # VALIDATION — app.services.core.validator is the sole authority,
    # via the accessibility-aware adapter (see validation_adapter.py).
    # For PHOTO_AND_TEXT this is a pure passthrough to
    # validator.calculate_validity() — completely unmodified. A missing
    # photo/description is never fabricated: absolute_image_path/
    # description are passed through exactly as empty.
    # ------------------------------------------------------------------
    validator_payload = {
        "user_id": user.id,
        "description": description,
        "category": validator_category,
        "photo_path": absolute_image_path,
        "latitude": latitude,
        "longitude": longitude,
        "timestamp": datetime.utcnow().isoformat(),
        "number_of_previous_reports": len(candidates),
        "user_previous_reports": user_previous_reports,
    }
    validity_result = calculate_validity_adaptive(validator_payload, submission_mode=submission_mode)

    # Supplemental, non-scoring signals (image reuse, abusive language).
    # These never change validity_score/validity_status.
    supplemental_flags = detect_supplemental_flags(
        db, description=description, user_id=user.id, image_hash=image_hash,
    )

    report = IssueReport(
        client_report_id=client_report_id,
        is_demo=False,
        user_id=user.id,
        original_description=description,
        normalized_description=description.strip(),
        image_path=relative_image_path,
        image_hash=image_hash,
        latitude=latitude,
        longitude=longitude,
        gps_accuracy=accuracy,
        language=language,
        submission_mode=submission_mode,
        description_source=description_source,
        client_ip_hash=client_ip_hash,
        accessibility_adjustment=validity_result.accessibility_adjustment,
        validity_score=validity_result.validity_score,
        validity_status=validity_result.status,
        validity_breakdown=json.dumps(validity_result.breakdown),
        validation_errors=json.dumps(validity_result.validation_errors),
        supplemental_flags=json.dumps(supplemental_flags),
        was_offline=was_offline,
        synced_at=datetime.utcnow() if was_offline else None,
    )
    db.add(report)
    db.flush()

    # ------------------------------------------------------------------
    # DUPLICATE CHECK — app.services.core.duplicate is the sole authority.
    # Skipped entirely for SUSPICIOUS reports: an unverified report must
    # not be allowed to merge into (and inflate the reporter_count of) a
    # real civic issue.
    # ------------------------------------------------------------------
    new_report_payload = {
        "id": None,  # not present among `candidates` — nothing to self-exclude
        "category": classification.category,
        "description": description,
        "latitude": latitude,
        "longitude": longitude,
        "photo_path": relative_image_path,
    }

    if validity_result.status in ("VALID", "REVIEW"):
        duplicate_recommendation = core_duplicate.get_duplicate_recommendation(new_report_payload, candidates)
    else:
        duplicate_recommendation = {"action": "CREATE_NEW", "matched_report_id": None, "duplicate_score": 0, "confidence": "NONE"}

    duplicate_breakdown: dict = {}
    duplicate_distance = None
    if duplicate_recommendation["matched_report_id"] is not None:
        matched_candidate = next(
            (c for c in candidates if c["id"] == duplicate_recommendation["matched_report_id"]), None,
        )
        if matched_candidate:
            score_detail = core_duplicate.calculate_duplicate_score(new_report_payload, matched_candidate)
            duplicate_breakdown = score_detail["breakdown"]
            duplicate_distance = score_detail["distance_meters"]

    action = duplicate_recommendation["action"]
    report.is_duplicate = action == "LINK_TO_EXISTING"

    # ------------------------------------------------------------------
    # REVIEW ROUTING — a report reaches the normal active workflow only
    # when the system has enough confidence to proceed. This looks at
    # the canonical engines' own outputs (validity status, duplicate
    # action) plus the AI understanding layer's confidence/category —
    # never re-implementing or re-weighting validator.py/duplicate.py
    # themselves. See app.services.review_routing for the full rule set.
    # ------------------------------------------------------------------
    is_manual_review, review_reasons = evaluate_manual_review(
        validity_status=validity_result.status,
        ai_confidence=classification.confidence,
        category=classification.category,
        duplicate_action=action,
        has_photo=bool(relative_image_path),
        description=description,
        validator_category=validator_category,
    )

    # ------------------------------------------------------------------
    # CREATE_NEW / REVIEW / LINK_TO_EXISTING
    # A POSSIBLE (REVIEW) duplicate is never auto-merged — it still
    # creates its own Issue, with the possible match recorded for staff.
    # ------------------------------------------------------------------
    if action == "LINK_TO_EXISTING":
        issue = db.query(Issue).get(duplicate_recommendation["matched_report_id"])

        # INDEPENDENT REPORTER COUNT — priority's reporter factor must
        # represent independent citizens, not repeated submissions from
        # the same person. Every report in this app carries a resolved
        # user_id (via mobile), so "independent" here means a distinct
        # user_id that hasn't already contributed to this exact issue.
        # report.issue_id is still unset at this point, so this query
        # naturally excludes the report currently being processed.
        already_reported = (
            db.query(IssueReport)
            .filter(IssueReport.issue_id == issue.id, IssueReport.user_id == user.id)
            .first()
            is not None
        )
        if not already_reported:
            issue.reporter_count += 1
        report.issue_id = issue.id

        # PRIORITY — recalculated using the updated reporter count only;
        # severity/location/age/impact stay pinned to the founding report.
        _apply_priority(db, issue)

        note = (
            f"Additional citizen report linked (duplicate score {duplicate_recommendation['duplicate_score']}, "
            f"confidence {duplicate_recommendation['confidence']})."
        )
        note += f" Reporter count now {issue.reporter_count}." if not already_reported else " (Same citizen had already reported this issue — reporter count unchanged.)"
        _log_status(db, issue, issue.status, "system", note)
    else:
        primary_dept, supporting_dept = routing_service.route_department(db, classification.issue_type)

        issue = Issue(
            complaint_id=generate_complaint_id(db),
            issue_type=classification.issue_type,
            category=classification.category,
            is_demo=False,
            latitude=latitude,
            longitude=longitude,
            severity=classification.severity_label,
            severity_level=classification.severity,
            severity_reason=classification.severity_reason,
            impact_level=classification.impact_level,
            location_type=classification.location_type,
            location_context=classification.location_context,
            primary_department_id=primary_dept.id,
            supporting_department_id=supporting_dept.id if supporting_dept else None,
            ai_confidence=classification.confidence,
            ai_reasoning=classification.reasoning_summary,
            status="MANUAL_REVIEW" if is_manual_review else "SUBMITTED",
            validity_status=validity_result.status,
            duplicate_score=float(duplicate_recommendation["duplicate_score"]),
            duplicate_confidence=duplicate_recommendation["confidence"],
            duplicate_action=action,
            duplicate_breakdown=json.dumps(duplicate_breakdown),
            duplicate_distance_meters=duplicate_distance,
            reporter_count=1,
            image_path=relative_image_path,
            assigned_at=datetime.utcnow(),
        )
        db.add(issue)
        db.flush()
        report.issue_id = issue.id

        # PRIORITY — app.services.core.priority is the sole authority.
        _apply_priority(db, issue)

        _log_status(db, issue, "SUBMITTED", "citizen", "Report submitted by citizen.")
        if not is_manual_review:
            _log_status(
                db, issue, "AI_VERIFIED", "system",
                f"AI classified as {classification.issue_type} ({classification.confidence:.0%} confidence).",
            )
            _log_status(db, issue, "ASSIGNED", "system", f"Routed to {primary_dept.name}.")
            issue.status = "ASSIGNED"
        else:
            _log_status(
                db, issue, "MANUAL_REVIEW", "system",
                f"Flagged for manual review: {', '.join(review_reasons)}.",
            )

    # ------------------------------------------------------------------
    # NOTIFY + PERSIST
    # ------------------------------------------------------------------
    if action == "LINK_TO_EXISTING":
        notify(
            db, user_id=user.id, issue_id=issue.id, complaint_id=issue.complaint_id,
            title="Report linked to existing issue",
            message=f"Your report was linked to an existing civic issue. {issue.reporter_count} citizens have reported this issue.",
            notif_type="received",
        )
    else:
        notify(
            db, user_id=user.id, issue_id=issue.id, complaint_id=issue.complaint_id,
            title="Report received", message="We've received your report and it's being processed.",
            notif_type="received",
        )

    db.commit()
    db.refresh(issue)
    db.refresh(report)

    return issue, report, False


async def add_support_report(
    db: Session,
    *,
    complaint_id: str,
    client_report_id: str,
    name: str,
    mobile: str,
    note: str | None,
    language: str,
    client_ip_hash: str | None,
) -> tuple[Issue, IssueReport, bool]:
    """"Report Same Issue" / "Add Support" from the nearby-issues feature.

    A citizen explicitly confirms an EXISTING Issue (by complaint_id) is
    the same problem they're seeing — this deliberately bypasses the
    probabilistic duplicate-scoring uncertainty (which might only reach
    POSSIBLE/REVIEW) in favor of a citizen-confirmed direct link, so a
    second independent Issue is never created for something the citizen
    has explicitly identified as already-reported.

    Reuses the exact same independent-reporter-count and priority-
    recalculation logic as the LINK_TO_EXISTING path in _run_pipeline —
    this is not a new decision engine, just a different entry point into
    the same reporter-linking mechanics.
    """
    existing = db.query(IssueReport).filter(IssueReport.client_report_id == client_report_id).first()
    if existing and existing.issue_id:
        issue = db.query(Issue).get(existing.issue_id)
        return issue, existing, True

    issue = db.query(Issue).filter(Issue.complaint_id == complaint_id, Issue.is_demo.is_(False)).first()
    if not issue:
        raise HTTPException(status_code=404, detail="No matching civic issue found.")
    if issue.status in ("RESOLVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="This issue is already closed and can no longer receive support.")

    user = _get_or_create_user(db, name, mobile)
    check_rate_limit(db, user_id=user.id, client_ip_hash=client_ip_hash, was_offline=False)

    description = (note or "").strip() or "Citizen confirmed this issue is still present nearby."

    report = IssueReport(
        client_report_id=client_report_id,
        is_demo=False,
        issue_id=issue.id,
        user_id=user.id,
        original_description=description,
        normalized_description=description,
        latitude=issue.latitude,
        longitude=issue.longitude,
        language=language,
        submission_mode="TEXT_ONLY",
        description_source="TYPED",
        client_ip_hash=client_ip_hash,
        # This is an explicit citizen confirmation of an already-routed,
        # already-valid issue — not a fresh unverified claim — so it does
        # not need to go through validator.py's evidence-based scoring.
        validity_score=100.0,
        validity_status="VALID",
        validity_breakdown=json.dumps({}),
        validation_errors=json.dumps([]),
        supplemental_flags=json.dumps([]),
        is_duplicate=True,
        was_offline=False,
    )
    db.add(report)
    db.flush()

    already_reported = (
        db.query(IssueReport)
        .filter(IssueReport.issue_id == issue.id, IssueReport.user_id == user.id, IssueReport.id != report.id)
        .first()
        is not None
    )
    if not already_reported:
        issue.reporter_count += 1
    _apply_priority(db, issue)

    note_text = f"Additional citizen confirmed the same issue via nearby-issues support."
    note_text += f" Reporter count now {issue.reporter_count}." if not already_reported else " (Same citizen had already reported this issue — reporter count unchanged.)"
    _log_status(db, issue, issue.status, "citizen", note_text)

    notify(
        db, user_id=user.id, issue_id=issue.id, complaint_id=issue.complaint_id,
        title="Thanks for confirming this issue",
        message=f"Your report was linked to an existing civic issue. {issue.reporter_count} citizens have reported this issue.",
        notif_type="received",
    )

    db.commit()
    db.refresh(issue)
    db.refresh(report)
    return issue, report, False
