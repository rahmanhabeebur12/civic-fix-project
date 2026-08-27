from pydantic import BaseModel


class KPISummary(BaseModel):
    open_issues: int
    critical_issues: int
    in_progress: int
    resolved_today: int
    avg_response_time_hours: float
    avg_resolution_time_hours: float
    pending_backlog: int
    reopened_issues: int
    manual_review_queue: int
    overdue_issues: int


class MapMarker(BaseModel):
    id: int
    complaint_id: str
    issue_type: str
    category: str
    latitude: float
    longitude: float
    severity: str
    priority_level: str
    status: str
    reporter_count: int
    department: str | None
    is_demo: bool
