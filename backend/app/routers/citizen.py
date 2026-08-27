import math

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.issue import Issue, IssueReport
from app.models.user import User
from app.schemas.issue import (
    AddSupportRequest, IssueTrackingResponse, NearbyIssueItem, ReportSubmitResponse, ResolutionInfo, StatusHistoryItem,
)
from app.services.location_service import haversine_meters
from app.services.rate_limiter import hash_client_ip
from app.services.report_pipeline import add_support_report, process_citizen_report
from app.utils.file_storage import resolve_url

router = APIRouter(prefix="/citizen", tags=["citizen"])

# "Unresolved/live" for the nearby-issues feature — mirrors
# app.routers.issues.RESOLVED_TERMINAL_STATUSES.
_UNRESOLVED_STATUSES_EXCLUDE = ("RESOLVED", "REJECTED")

# Client-facing radius choices (kilometers) — default 3km.
_ALLOWED_RADIUS_KM = (1.0, 3.0, 5.0)
_DEFAULT_RADIUS_KM = 3.0


def _client_ip(request: Request) -> str | None:
    # A reverse proxy (Render, etc.) sets X-Forwarded-For; fall back to the
    # direct connection otherwise. This is only ever hashed before storage
    # (see rate_limiter.hash_client_ip) — the raw IP is never persisted.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


@router.post("/reports", response_model=ReportSubmitResponse)
async def submit_report(
    client_report_id: str = Form(...),
    description: str = Form(""),
    latitude: float = Form(...),
    longitude: float = Form(...),
    accuracy: float | None = Form(None),
    language: str = Form("en"),
    name: str = Form("Citizen"),
    mobile: str = Form(...),
    was_offline: bool = Form(False),
    description_source: str = Form("TYPED"),  # TYPED | VOICE — analytics only
    image: UploadFile | None = File(None),
    request: Request = None,  # FastAPI always injects the real Request
    db: Session = Depends(get_db),
):
    """Validates HTTP input and delegates all report-decision logic to the
    central pipeline. No validity/duplicate/priority logic — and no direct
    handling of uploaded image bytes — belongs here; the pipeline routes
    the upload through the canonical image sanitizer.

    Accessibility requirement: a photo and a description are not both
    required — either is enough. The pipeline rejects only when neither
    is provided, with a simple user-facing message."""
    if image is not None and not image.filename:
        # Some browsers submit an empty <input type="file"> as a
        # zero-byte UploadFile rather than omitting the field entirely.
        image = None
    issue, report, already_processed = await process_citizen_report(
        db,
        client_report_id=client_report_id,
        description=description,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy,
        language=language,
        name=name,
        mobile=mobile,
        was_offline=was_offline,
        description_source=description_source,
        image=image,
        client_ip_hash=hash_client_ip(_client_ip(request)),
    )

    return _build_submit_response(issue, report, already_processed)


@router.post("/reports/{complaint_id}/support", response_model=ReportSubmitResponse)
async def support_existing_issue(complaint_id: str, payload: AddSupportRequest, request: Request, db: Session = Depends(get_db)):
    """"Report Same Issue" / "Add Support" from the nearby-issues feature —
    links a new IssueReport to an already-known Issue rather than creating
    a second independent one. See report_pipeline.add_support_report."""
    issue, report, already_processed = await add_support_report(
        db,
        complaint_id=complaint_id,
        client_report_id=payload.client_report_id,
        name=payload.name,
        mobile=payload.mobile,
        note=payload.note,
        language=payload.language,
        client_ip_hash=hash_client_ip(_client_ip(request)),
    )
    return _build_submit_response(issue, report, already_processed)


@router.get("/nearby-issues", response_model=list[NearbyIssueItem])
def nearby_issues(latitude: float, longitude: float, radius_km: float = _DEFAULT_RADIUS_KM, db: Session = Depends(get_db)):
    """Currently unresolved, live (non-demo) issues near the citizen's GPS
    location — used by the "Nearby Issues" feature so a citizen can add
    support to an existing report instead of unknowingly creating a
    duplicate. Never exposes reporter identity."""
    if radius_km not in _ALLOWED_RADIUS_KM:
        radius_km = _DEFAULT_RADIUS_KM
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise HTTPException(status_code=400, detail="Invalid GPS coordinates.")

    radius_meters = radius_km * 1000
    # Coarse bounding-box pre-filter (cheap, index-friendly), same pattern
    # as duplicate_detector.load_candidate_issues, before the precise
    # Haversine distance check.
    lat_delta = radius_meters / 111_320.0
    lon_delta = radius_meters / (111_320.0 * max(0.1, math.cos(math.radians(latitude))))

    candidates = (
        db.query(Issue)
        .filter(Issue.is_demo.is_(False))
        .filter(~Issue.status.in_(_UNRESOLVED_STATUSES_EXCLUDE))
        .filter(Issue.latitude.between(latitude - lat_delta, latitude + lat_delta))
        .filter(Issue.longitude.between(longitude - lon_delta, longitude + lon_delta))
        .all()
    )

    results = []
    for issue in candidates:
        distance = haversine_meters(latitude, longitude, issue.latitude, issue.longitude)
        if distance <= radius_meters:
            results.append(NearbyIssueItem(
                complaint_id=issue.complaint_id,
                issue_type=issue.issue_type,
                category=issue.category,
                status=issue.status,
                priority_level=issue.priority_level,
                distance_meters=round(distance, 1),
                reporter_count=issue.reporter_count,
                created_at=issue.created_at,
            ))

    results.sort(key=lambda r: r.distance_meters)
    return results


def _build_submit_response(issue: Issue, report: IssueReport, already_processed: bool) -> ReportSubmitResponse:
    dept_name = issue.primary_department.name if issue.primary_department else "General Civic Support"
    if already_processed:
        message = "This report was already submitted. Showing existing status."
    elif report.is_duplicate:
        message = f"Your report was linked to an existing civic issue. {issue.reporter_count} citizens have reported this issue."
    else:
        message = "Report submitted successfully."

    return ReportSubmitResponse(
        complaint_id=issue.complaint_id,
        issue_type=issue.issue_type,
        category=issue.category,
        department=dept_name,
        priority_level=issue.priority_level,
        priority_score=issue.priority_score,
        status=issue.status,
        is_duplicate=bool(report.is_duplicate),
        reporter_count=issue.reporter_count,
        validity_status=report.validity_status,
        review_required=report.validity_status != "VALID",
        submission_mode=report.submission_mode,
        message=message,
    )


@router.get("/reports/{complaint_id}", response_model=IssueTrackingResponse)
def track_report(complaint_id: str, db: Session = Depends(get_db)):
    issue = db.query(Issue).filter(Issue.complaint_id == complaint_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="No report found with that complaint ID.")
    return _build_tracking_response(issue)


@router.get("/my-reports")
def my_reports(mobile: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.mobile == mobile).first()
    if not user:
        return []
    reports = db.query(IssueReport).filter(IssueReport.user_id == user.id).order_by(IssueReport.submitted_at.desc()).all()
    results = []
    seen_issue_ids = set()
    for r in reports:
        if not r.issue_id or r.issue_id in seen_issue_ids:
            continue
        seen_issue_ids.add(r.issue_id)
        issue = db.query(Issue).get(r.issue_id)
        if not issue:
            continue
        results.append({
            "complaint_id": issue.complaint_id,
            "issue_type": issue.issue_type,
            "category": issue.category,
            "status": issue.status,
            "priority_level": issue.priority_level,
            "department": issue.primary_department.name if issue.primary_department else None,
            "image_url": resolve_url(issue.image_path),
            "created_at": issue.created_at,
            "reporter_count": issue.reporter_count,
        })
    return results


def _build_tracking_response(issue: Issue) -> IssueTrackingResponse:
    first_report = issue.reports[0] if issue.reports else None
    return IssueTrackingResponse(
        complaint_id=issue.complaint_id,
        issue_type=issue.issue_type,
        category=issue.category,
        description=first_report.original_description if first_report else "",
        image_url=resolve_url(issue.image_path),
        latitude=issue.latitude,
        longitude=issue.longitude,
        address=issue.address or issue.location_context,
        department=issue.primary_department.name if issue.primary_department else "General Civic Support",
        supporting_department=issue.supporting_department.name if issue.supporting_department else None,
        severity=issue.severity,
        priority_level=issue.priority_level,
        priority_score=issue.priority_score,
        status=issue.status,
        reporter_count=issue.reporter_count,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        reopen_count=issue.reopen_count,
        timeline=[StatusHistoryItem.model_validate(s) for s in issue.status_history],
        resolutions=[
            ResolutionInfo(
                image_url=resolve_url(r.image_path),
                note=r.note,
                officer_username=r.officer_username,
                created_at=r.created_at,
                citizen_confirmed=r.citizen_confirmed,
                citizen_feedback=r.citizen_feedback or "",
                confirmed_at=r.confirmed_at,
            )
            for r in issue.resolutions
        ],
    )
