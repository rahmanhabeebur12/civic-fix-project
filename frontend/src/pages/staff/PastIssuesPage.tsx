import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StaffLayout } from "@/components/StaffLayout";
import { DemoBadge } from "@/components/Badges";
import { DataScopeFilter } from "@/components/DataScopeFilter";
import { Spinner } from "@/components/Spinner";
import { api } from "@/services/api";
import type { DataScope, StaffIssueSummary } from "@/types";

function hoursBetween(startIso: string, endIso: string): number {
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  return Math.max(0, ms / 1000 / 3600);
}

function formatDuration(hours: number): string {
  if (hours < 48) return `${Math.round(hours)}h`;
  return `${Math.round(hours / 24)}d`;
}

export default function PastIssuesPage() {
  const [issues, setIssues] = useState<StaffIssueSummary[] | null>(null);
  const [dataScope, setDataScope] = useState<DataScope>("live");

  useEffect(() => {
    setIssues(null);
    // Resolved issues remain in the same database — this view only
    // scopes what's SHOWN, exactly like every other staff filter (status
    // is a real Issue.status value already supported by /staff/issues).
    api.staffIssues({ status: "RESOLVED", data_scope: dataScope }).then(setIssues).catch(() => setIssues([]));
  }, [dataScope]);

  return (
    <StaffLayout>
      <div className="mb-1 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-slate-800">Past Issues</h1>
        <DataScopeFilter value={dataScope} onChange={setDataScope} />
      </div>
      <p className="mb-5 text-sm text-slate-500">
        Resolved issues — kept for the record, no longer on the active dashboard. If a citizen reopens one, it moves back to Issues automatically.
      </p>

      {!issues ? (
        <Spinner label="Loading past issues…" />
      ) : issues.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-400">
          No resolved issues yet.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[820px] text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3">Complaint</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3">Department</th>
                <th className="px-4 py-3">Resolved</th>
                <th className="px-4 py-3">Resolution Time</th>
                <th className="px-4 py-3">Reopen History</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {issues.map((issue) => (
                <tr key={issue.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                  <td className="px-4 py-3 font-semibold text-slate-800">
                    <div className="flex items-center gap-2">
                      {issue.complaint_id}
                      {issue.is_demo && <DemoBadge />}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{issue.category}</td>
                  <td className="px-4 py-3 text-slate-600">{issue.department || "—"}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {issue.resolved_at ? new Date(issue.resolved_at).toLocaleDateString() : "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {issue.resolved_at ? formatDuration(hoursBetween(issue.created_at, issue.resolved_at)) : "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-600">
                    {issue.reopen_count > 0 ? (
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
                        Reopened {issue.reopen_count}×
                      </span>
                    ) : (
                      <span className="text-xs text-slate-400">Never reopened</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Link to={`/staff/issues/${issue.id}`} className="text-xs font-semibold text-brand-700 underline">
                      Evidence &amp; verification →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </StaffLayout>
  );
}
