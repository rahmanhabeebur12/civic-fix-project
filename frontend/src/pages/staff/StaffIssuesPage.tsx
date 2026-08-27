import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StaffLayout } from "@/components/StaffLayout";
import { PriorityBadge, StatusBadge, ValidityBadge, DemoBadge } from "@/components/Badges";
import { DataScopeFilter } from "@/components/DataScopeFilter";
import { Spinner } from "@/components/Spinner";
import { api } from "@/services/api";
import type { DataScope, Department, StaffIssueSummary } from "@/types";

const STATUSES = ["SUBMITTED", "AI_VERIFIED", "MANUAL_REVIEW", "ASSIGNED", "ACCEPTED", "IN_PROGRESS", "AWAITING_CITIZEN_VERIFICATION", "RESOLVED", "REOPENED", "REJECTED", "TRANSFERRED"];
const PRIORITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
const SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

export default function StaffIssuesPage() {
  const [issues, setIssues] = useState<StaffIssueSummary[] | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [search, setSearch] = useState("");
  const [dataScope, setDataScope] = useState<DataScope>("live");

  useEffect(() => {
    api.departments().then(setDepartments).catch(() => {});
  }, []);

  useEffect(() => {
    const params = { ...filters, search: search || undefined, data_scope: dataScope };
    api.staffIssues(params).then(setIssues).catch(() => setIssues([]));
  }, [filters, search, dataScope]);

  function setFilter(key: string, value: string) {
    setFilters((prev) => {
      const next = { ...prev };
      if (value) next[key] = value;
      else delete next[key];
      return next;
    });
  }

  return (
    <StaffLayout>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-slate-800">Issues</h1>
        <DataScopeFilter value={dataScope} onChange={setDataScope} />
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        <input
          className="input-field max-w-xs"
          placeholder="Search complaint ID, location…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select className="input-field w-auto" onChange={(e) => setFilter("department_id", e.target.value)}>
          <option value="">All Departments</option>
          {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </select>
        <select className="input-field w-auto" onChange={(e) => setFilter("status", e.target.value)}>
          <option value="">All Statuses</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
        </select>
        <select className="input-field w-auto" onChange={(e) => setFilter("priority_level", e.target.value)}>
          <option value="">All Priorities</option>
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select className="input-field w-auto" onChange={(e) => setFilter("severity", e.target.value)}>
          <option value="">All Severities</option>
          {SEVERITIES.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <label className="flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-600">
          <input type="checkbox" onChange={(e) => setFilter("overdue_only", e.target.checked ? "true" : "")} />
          Overdue only
        </label>
        <label className="flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 text-sm text-slate-600">
          <input type="checkbox" onChange={(e) => setFilter("reopened_only", e.target.checked ? "true" : "")} />
          Reopened only
        </label>
      </div>

      {!issues ? (
        <Spinner label="Loading issues…" />
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Complaint</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Department</th>
                <th className="px-4 py-3">Severity</th>
                <th className="px-4 py-3">Priority</th>
                <th className="px-4 py-3">Validity</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Reporters</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {issues.map((issue) => (
                <tr key={issue.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-4 py-3 font-semibold text-slate-800">
                    <div className="flex items-center gap-2">
                      {issue.complaint_id}
                      {issue.is_overdue && <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-bold text-red-700">OVERDUE</span>}
                      {issue.is_demo && <DemoBadge />}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{issue.issue_type}</td>
                  <td className="px-4 py-3 text-slate-600">{issue.department || "—"}</td>
                  <td className="px-4 py-3"><PriorityBadge level={issue.severity} /></td>
                  <td className="px-4 py-3"><PriorityBadge level={issue.priority_level} /></td>
                  <td className="px-4 py-3"><ValidityBadge status={issue.validity_status} /></td>
                  <td className="px-4 py-3"><StatusBadge status={issue.status} /></td>
                  <td className="px-4 py-3 text-slate-600">{issue.reporter_count}</td>
                  <td className="px-4 py-3">
                    <Link to={`/staff/issues/${issue.id}`} className="text-xs font-semibold text-brand-700 underline">
                      View
                    </Link>
                  </td>
                </tr>
              ))}
              {issues.length === 0 && (
                <tr>
                  <td colSpan={9} className="px-4 py-8 text-center text-slate-400">No complaints match these filters.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </StaffLayout>
  );
}
