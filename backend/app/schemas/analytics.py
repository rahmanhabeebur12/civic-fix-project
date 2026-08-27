from pydantic import BaseModel


class DepartmentPerformance(BaseModel):
    department: str
    open_issues: int
    critical_issues: int
    resolved_count: int
    pending_backlog: int
    overdue_issues: int
    reopened_issues: int
    avg_response_time_hours: float
    avg_resolution_time_hours: float


class CategoryBreakdown(BaseModel):
    category: str
    count: int


class HotspotResponse(BaseModel):
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


class OldestUnresolvedItem(BaseModel):
    complaint_id: str
    issue_type: str
    status: str
    priority_level: str
    age_hours: float


class ResponseTimeAnalyticsResponse(BaseModel):
    avg_time_to_assignment_hours: float
    median_time_to_assignment_hours: float
    avg_time_to_accept_hours: float
    median_time_to_accept_hours: float
    avg_time_to_start_work_hours: float
    avg_time_to_resolution_hours: float
    median_time_to_resolution_hours: float
    avg_unresolved_age_hours: float
    oldest_unresolved: list[OldestUnresolvedItem]


class DepartmentBacklogItem(BaseModel):
    department: str
    backlog: int
    high_backlog: int
    critical_backlog: int


class BacklogAnalyticsResponse(BaseModel):
    per_department: list[DepartmentBacklogItem]
    high_backlog: int
    critical_backlog: int
    total_open_backlog: int
    total_resolved: int
    reopened_count: int


class HeatmapPointResponse(BaseModel):
    latitude: float
    longitude: float
    weight: int
    category: str
    issue_type: str
    complaint_id: str
