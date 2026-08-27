from datetime import datetime
from pydantic import BaseModel


class ReportSubmitResponse(BaseModel):
    complaint_id: str
    issue_type: str
    category: str
    department: str
    priority_level: str
    priority_score: int
    status: str
    is_duplicate: bool
    reporter_count: int
    validity_status: str
    review_required: bool
    submission_mode: str
    message: str


class StatusHistoryItem(BaseModel):
    status: str
    note: str
    changed_by: str
    timestamp: datetime

    class Config:
        from_attributes = True


class ResolutionInfo(BaseModel):
    image_url: str
    note: str
    officer_username: str
    created_at: datetime
    citizen_confirmed: bool | None
    citizen_feedback: str
    confirmed_at: datetime | None

    class Config:
        from_attributes = True


class IssueTrackingResponse(BaseModel):
    complaint_id: str
    issue_type: str
    category: str
    description: str
    image_url: str
    latitude: float
    longitude: float
    address: str
    department: str
    supporting_department: str | None
    severity: str
    priority_level: str
    priority_score: int
    status: str
    reporter_count: int
    created_at: datetime
    updated_at: datetime
    reopen_count: int
    timeline: list[StatusHistoryItem]
    resolutions: list[ResolutionInfo]


class StaffIssueSummary(BaseModel):
    id: int
    complaint_id: str
    issue_type: str
    category: str
    latitude: float
    longitude: float
    severity: str
    priority_level: str
    priority_score: int
    status: str
    validity_status: str
    department: str | None
    reporter_count: int
    reopen_count: int
    image_url: str
    is_overdue: bool
    is_demo: bool
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    review_reasons: list[str] = []


class StaffIssueDetail(BaseModel):
    id: int
    complaint_id: str
    issue_type: str
    category: str
    is_demo: bool
    description: str
    original_description: str
    image_url: str
    latitude: float
    longitude: float
    address: str

    # --- Priority (app.services.core.priority) ---
    severity: str
    severity_level: int
    severity_reason: str
    impact_level: int
    location_type: str
    location_context: str
    priority_score: int
    priority_level: str
    priority_breakdown: dict
    priority_reasons: list[str]

    department: str | None
    department_id: int | None
    supporting_department: str | None
    ai_confidence: float
    ai_reasoning: str
    status: str

    # --- Validity (app.services.core.validator, from the founding report) ---
    validity_status: str
    validity_score: float
    validity_breakdown: dict
    validation_errors: list[str]

    # --- Duplicate analysis (app.services.core.duplicate, founding report) ---
    duplicate_score: float
    duplicate_confidence: str
    duplicate_action: str
    duplicate_breakdown: dict
    duplicate_distance_meters: float | None

    reporter_count: int
    reopen_count: int
    created_at: datetime
    updated_at: datetime
    accepted_at: datetime | None
    accepted_by: str | None
    work_started_at: datetime | None
    resolved_at: datetime | None
    is_overdue: bool
    sla_hours: int
    review_reasons: list[str] = []
    timeline: list[StatusHistoryItem]
    resolutions: list[ResolutionInfo]
    reports: list[dict]


class ConfirmResolutionRequest(BaseModel):
    confirmed: bool
    feedback: str | None = None


class TransferRequest(BaseModel):
    department_id: int
    note: str | None = None


class NoteRequest(BaseModel):
    note: str


class ReviewDecisionRequest(BaseModel):
    decision: str  # APPROVED | REJECTED
    note: str | None = None


class NearbyIssueItem(BaseModel):
    """Deliberately excludes reporter name/mobile — those are never
    exposed to other citizens, only to authenticated staff."""
    complaint_id: str
    issue_type: str
    category: str
    status: str
    priority_level: str
    distance_meters: float
    reporter_count: int
    created_at: datetime


class AddSupportRequest(BaseModel):
    client_report_id: str
    name: str
    mobile: str
    note: str | None = None
    language: str = "en"
