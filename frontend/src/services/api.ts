// VITE_API_BASE_URL is the canonical name (see .env.example); VITE_API_URL
// is kept as a fallback for existing local .env files, and localhost is
// the last-resort dev-only default — production deployments must set
// VITE_API_BASE_URL explicitly (never hardcode a deployed URL here).
const API_BASE =
  (import.meta as any).env?.VITE_API_BASE_URL || (import.meta as any).env?.VITE_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("civicfix_staff_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function citizenAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem("civicfix_citizen_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = "Something went wrong. Please try again.";
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // ignore parse errors, use default message
    }
    throw new ApiError(detail, res.status);
  }
  return res.json() as Promise<T>;
}

export async function checkHealth(timeoutMs = 4000): Promise<boolean> {
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const res = await fetch(`${API_BASE}/health`, { signal: controller.signal });
    clearTimeout(timer);
    return res.ok;
  } catch {
    return false;
  }
}

export const api = {
  base: API_BASE,

  async login(username: string, password: string) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    return handle<{ access_token: string; username: string; full_name: string; role: string; department: string | null }>(res);
  },

  async submitReport(form: FormData) {
    const res = await fetch(`${API_BASE}/citizen/reports`, { method: "POST", body: form });
    return handle<import("@/types").ReportSubmitResponse>(res);
  },

  async trackReport(complaintId: string) {
    const res = await fetch(`${API_BASE}/citizen/reports/${encodeURIComponent(complaintId)}`);
    return handle<import("@/types").IssueTrackingResponse>(res);
  },

  async myReports(mobile: string) {
    const res = await fetch(`${API_BASE}/citizen/my-reports?mobile=${encodeURIComponent(mobile)}`);
    return handle<import("@/types").MyReportSummary[]>(res);
  },

  async confirmResolution(complaintId: string, confirmed: boolean, feedback?: string) {
    const res = await fetch(`${API_BASE}/issues/${encodeURIComponent(complaintId)}/confirm-resolution`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmed, feedback }),
    });
    return handle<{ status: string; reopen_count: number }>(res);
  },

  async notifications(mobile: string) {
    const res = await fetch(`${API_BASE}/notifications?mobile=${encodeURIComponent(mobile)}`);
    return handle<import("@/types").NotificationItem[]>(res);
  },

  async departments() {
    const res = await fetch(`${API_BASE}/departments`);
    return handle<import("@/types").Department[]>(res);
  },

  // --- Citizen login (optional — guest reporting never requires this) ---
  async citizenRegister(name: string, mobile: string, password: string) {
    const res = await fetch(`${API_BASE}/auth/citizen/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, mobile, password }),
    });
    return handle<import("@/types").CitizenAuthResponse>(res);
  },

  async citizenLogin(mobile: string, password: string) {
    const res = await fetch(`${API_BASE}/auth/citizen/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mobile, password }),
    });
    return handle<import("@/types").CitizenAuthResponse>(res);
  },

  async citizenProfile() {
    const res = await fetch(`${API_BASE}/auth/citizen/me`, { headers: citizenAuthHeaders() });
    return handle<import("@/types").CitizenProfile>(res);
  },

  async nearbyIssues(latitude: number, longitude: number, radiusKm: number) {
    const res = await fetch(`${API_BASE}/citizen/nearby-issues?latitude=${latitude}&longitude=${longitude}&radius_km=${radiusKm}`);
    return handle<import("@/types").NearbyIssueItem[]>(res);
  },

  async addSupport(complaintId: string, payload: { client_report_id: string; name: string; mobile: string; note?: string; language: string }) {
    const res = await fetch(`${API_BASE}/citizen/reports/${encodeURIComponent(complaintId)}/support`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    return handle<import("@/types").ReportSubmitResponse>(res);
  },

  // --- Staff (authenticated) ---
  async me() {
    const res = await fetch(`${API_BASE}/auth/me`, { headers: authHeaders() });
    return handle<import("@/types").StaffProfile>(res);
  },

  async dashboardSummary(dataScope: import("@/types").DataScope = "live") {
    const res = await fetch(`${API_BASE}/dashboard/summary?data_scope=${dataScope}`, { headers: authHeaders() });
    return handle<import("@/types").KPISummary>(res);
  },

  async dashboardMap(dataScope: import("@/types").DataScope = "live") {
    const res = await fetch(`${API_BASE}/dashboard/map?data_scope=${dataScope}`, { headers: authHeaders() });
    return handle<import("@/types").MapMarker[]>(res);
  },

  async staffIssues(params: Record<string, string | number | boolean | undefined>) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "" && v !== null) query.set(k, String(v));
    });
    const res = await fetch(`${API_BASE}/staff/issues?${query.toString()}`, { headers: authHeaders() });
    return handle<import("@/types").StaffIssueSummary[]>(res);
  },

  async staffIssueDetail(id: number) {
    const res = await fetch(`${API_BASE}/staff/issues/${id}`, { headers: authHeaders() });
    return handle<import("@/types").StaffIssueDetail>(res);
  },

  async acceptIssue(id: number) {
    const res = await fetch(`${API_BASE}/staff/issues/${id}/accept`, { method: "POST", headers: authHeaders() });
    return handle<{ status: string }>(res);
  },

  async startWork(id: number) {
    const res = await fetch(`${API_BASE}/staff/issues/${id}/start-work`, { method: "POST", headers: authHeaders() });
    return handle<{ status: string }>(res);
  },

  async transferIssue(id: number, department_id: number, note?: string) {
    const res = await fetch(`${API_BASE}/staff/issues/${id}/transfer`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ department_id, note }),
    });
    return handle<{ status: string; department: string }>(res);
  },

  async addNote(id: number, note: string) {
    const res = await fetch(`${API_BASE}/staff/issues/${id}/note`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ note }),
    });
    return handle<{ ok: boolean }>(res);
  },

  async resolveIssue(id: number, form: FormData) {
    const res = await fetch(`${API_BASE}/staff/issues/${id}/resolve`, { method: "POST", headers: authHeaders(), body: form });
    return handle<{ status: string }>(res);
  },

  async reviewDecision(id: number, decision: "APPROVED" | "REJECTED", note?: string) {
    const res = await fetch(`${API_BASE}/staff/issues/${id}/review-decision`, {
      method: "POST",
      headers: { ...authHeaders(), "Content-Type": "application/json" },
      body: JSON.stringify({ decision, note }),
    });
    return handle<{ status: string }>(res);
  },

  async departmentAnalytics() {
    const res = await fetch(`${API_BASE}/analytics/departments`, { headers: authHeaders() });
    return handle<import("@/types").DepartmentPerformance[]>(res);
  },

  async categoryAnalytics() {
    const res = await fetch(`${API_BASE}/analytics/categories`, { headers: authHeaders() });
    return handle<import("@/types").CategoryBreakdown[]>(res);
  },

  async hotspots() {
    const res = await fetch(`${API_BASE}/analytics/hotspots`, { headers: authHeaders() });
    return handle<import("@/types").Hotspot[]>(res);
  },

  async responseTimeAnalytics(dataScope: import("@/types").DataScope = "live") {
    const res = await fetch(`${API_BASE}/analytics/response-times?data_scope=${dataScope}`, { headers: authHeaders() });
    return handle<import("@/types").ResponseTimeAnalytics>(res);
  },

  async backlogAnalytics(dataScope: import("@/types").DataScope = "live") {
    const res = await fetch(`${API_BASE}/analytics/backlog?data_scope=${dataScope}`, { headers: authHeaders() });
    return handle<import("@/types").BacklogAnalytics>(res);
  },

  async heatmap(days: number, category: string, dataScope: import("@/types").DataScope = "live") {
    const query = new URLSearchParams({ days: String(days), data_scope: dataScope });
    if (category && category !== "All") query.set("category", category);
    const res = await fetch(`${API_BASE}/analytics/heatmap?${query.toString()}`, { headers: authHeaders() });
    return handle<import("@/types").HeatmapPoint[]>(res);
  },
};

export function imageUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http") || path.startsWith("blob:")) return path;
  return `${API_BASE}${path}`;
}
