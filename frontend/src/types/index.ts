export type Language = "en" | "ta";

export type DataScope = "live" | "demo" | "all";

export type SyncStatus = "PENDING_SYNC" | "SYNCING" | "SYNCED" | "SYNC_FAILED";

export type DescriptionSource = "TYPED" | "VOICE";

export interface OfflineReport {
  client_report_id: string;
  description: string;
  original_description: string;
  latitude: number;
  longitude: number;
  accuracy: number | null;
  imageBlob: Blob | null;
  imageType: string | null;
  language: Language;
  name: string;
  mobile: string;
  created_at: string;
  sync_status: SyncStatus;
  sync_attempts: number;
  last_sync_attempt: string | null;
  complaint_id?: string;
  error_message?: string;
  /** Analytics only — was the description originally produced by speech-
   * to-text? Never affects validation/duplicate/priority. */
  description_source?: DescriptionSource;
}

export interface ReportSubmitResponse {
  complaint_id: string;
  issue_type: string;
  category: string;
  department: string;
  priority_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  priority_score: number;
  status: string;
  is_duplicate: boolean;
  reporter_count: number;
  validity_status: string;
  review_required: boolean;
  submission_mode: string;
  message: string;
}

export interface StatusHistoryItem {
  status: string;
  note: string;
  changed_by: string;
  timestamp: string;
}

export interface ResolutionInfo {
  image_url: string;
  note: string;
  officer_username: string;
  created_at: string;
  citizen_confirmed: boolean | null;
  citizen_feedback: string;
  confirmed_at: string | null;
}

export interface IssueTrackingResponse {
  complaint_id: string;
  issue_type: string;
  category: string;
  description: string;
  image_url: string;
  latitude: number;
  longitude: number;
  address: string;
  department: string;
  supporting_department: string | null;
  severity: string;
  priority_level: string;
  priority_score: number;
  status: string;
  reporter_count: number;
  created_at: string;
  updated_at: string;
  reopen_count: number;
  timeline: StatusHistoryItem[];
  resolutions: ResolutionInfo[];
}

export interface MyReportSummary {
  complaint_id: string;
  issue_type: string;
  category: string;
  status: string;
  priority_level: string;
  department: string | null;
  image_url: string;
  created_at: string;
  reporter_count: number;
}

export interface StaffIssueSummary {
  id: number;
  complaint_id: string;
  issue_type: string;
  category: string;
  latitude: number;
  longitude: number;
  severity: string;
  priority_level: string;
  priority_score: number;
  status: string;
  validity_status: string;
  department: string | null;
  reporter_count: number;
  reopen_count: number;
  image_url: string;
  is_overdue: boolean;
  is_demo: boolean;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
  review_reasons: string[];
}

export interface ReporterReliability {
  score: number;
  label: "NEW" | "BUILDING" | "TRUSTED";
  breakdown: Record<string, number>;
  total_reports: number;
  resolved_as_genuine: number;
  account_age_days: number;
}

export interface PriorityBreakdown {
  severity?: number;
  reporters?: number;
  location?: number;
  age?: number;
  impact?: number;
}

export interface ValidityBreakdown {
  photo_validity?: { score: number; weight: number; weighted_contribution: number };
  description_category_consistency?: { score: number; weight: number; weighted_contribution: number };
  location_validity?: { score: number; weight: number; weighted_contribution: number };
  user_reliability?: { score: number; weight: number; weighted_contribution: number };
  duplicate_evidence?: { score: number; weight: number; weighted_contribution: number };
  spam_frequency?: { score: number; weight: number; weighted_contribution: number };
}

export interface DuplicateBreakdown {
  location?: number;
  category?: number;
  description?: number;
  photo?: number;
}

export interface StaffIssueDetail extends Omit<StaffIssueSummary, "department"> {
  description: string;
  original_description: string;
  address: string;

  // Priority (app.services.core.priority)
  severity_level: number;
  severity_reason: string;
  impact_level: number;
  location_type: string;
  location_context: string;
  priority_breakdown: PriorityBreakdown;
  priority_reasons: string[];

  department: string | null;
  department_id: number | null;
  supporting_department: string | null;
  ai_confidence: number;
  ai_reasoning: string;

  // Validity (app.services.core.validator)
  validity_score: number;
  validity_breakdown: ValidityBreakdown;
  validation_errors: string[];

  // Duplicate analysis (app.services.core.duplicate)
  duplicate_score: number;
  duplicate_confidence: string;
  duplicate_action: string;
  duplicate_breakdown: DuplicateBreakdown;
  duplicate_distance_meters: number | null;

  accepted_at: string | null;
  accepted_by: string | null;
  work_started_at: string | null;
  resolved_at: string | null;
  sla_hours: number;
  review_reasons: string[];
  timeline: StatusHistoryItem[];
  resolutions: ResolutionInfo[];
  reports: {
    id: number;
    original_description: string;
    image_url: string;
    validity_score: number;
    validity_status: string;
    validation_errors: string[];
    supplemental_flags: string[];
    submitted_at: string;
    was_offline: boolean;
    reporter_reliability: ReporterReliability;
  }[];
}

export interface KPISummary {
  open_issues: number;
  critical_issues: number;
  in_progress: number;
  resolved_today: number;
  avg_response_time_hours: number;
  avg_resolution_time_hours: number;
  pending_backlog: number;
  reopened_issues: number;
  manual_review_queue: number;
  overdue_issues: number;
}

export interface MapMarker {
  id: number;
  complaint_id: string;
  issue_type: string;
  category: string;
  latitude: number;
  longitude: number;
  severity: string;
  priority_level: string;
  status: string;
  reporter_count: number;
  department: string | null;
  is_demo: boolean;
}

export interface Department {
  id: number;
  name: string;
  code: string;
}

export interface DepartmentPerformance {
  department: string;
  open_issues: number;
  critical_issues: number;
  resolved_count: number;
  pending_backlog: number;
  overdue_issues: number;
  reopened_issues: number;
  avg_response_time_hours: number;
  avg_resolution_time_hours: number;
}

export interface CategoryBreakdown {
  category: string;
  count: number;
}

export interface Hotspot {
  label: string;
  category: string;
  primary_issue_type: string;
  latitude: number;
  longitude: number;
  report_count: number;
  issue_count: number;
  period_days: number;
  avg_recurrence_days: number;
  recommendation: string;
}

export interface NotificationItem {
  id: number;
  title: string;
  message: string;
  notif_type: string;
  complaint_id: string | null;
  is_read: boolean;
  created_at: string;
}

export interface StaffProfile {
  username: string;
  full_name: string;
  role: string;
  department: string | null;
}

export interface CitizenIdentity {
  name: string;
  mobile: string;
}

export interface CitizenAuthResponse {
  access_token: string;
  name: string;
  mobile: string;
}

export interface CitizenProfile {
  name: string;
  mobile: string;
  total_reports: number;
  resolved_reports: number;
  supported_issues: number;
  reliability_label: "NEW" | "BUILDING" | "TRUSTED";
}

export interface NearbyIssueItem {
  complaint_id: string;
  issue_type: string;
  category: string;
  status: string;
  priority_level: string;
  distance_meters: number;
  reporter_count: number;
  created_at: string;
}

export interface OldestUnresolvedItem {
  complaint_id: string;
  issue_type: string;
  status: string;
  priority_level: string;
  age_hours: number;
}

export interface ResponseTimeAnalytics {
  avg_time_to_assignment_hours: number;
  median_time_to_assignment_hours: number;
  avg_time_to_accept_hours: number;
  median_time_to_accept_hours: number;
  avg_time_to_start_work_hours: number;
  avg_time_to_resolution_hours: number;
  median_time_to_resolution_hours: number;
  avg_unresolved_age_hours: number;
  oldest_unresolved: OldestUnresolvedItem[];
}

export interface DepartmentBacklogItem {
  department: string;
  backlog: number;
  high_backlog: number;
  critical_backlog: number;
}

export interface BacklogAnalytics {
  per_department: DepartmentBacklogItem[];
  high_backlog: number;
  critical_backlog: number;
  total_open_backlog: number;
  total_resolved: number;
  reopened_count: number;
}

export interface HeatmapPoint {
  latitude: number;
  longitude: number;
  weight: number;
  category: string;
  issue_type: string;
  complaint_id: string;
}
