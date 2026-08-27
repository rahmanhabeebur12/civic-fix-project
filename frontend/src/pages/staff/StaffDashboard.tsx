import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StaffLayout } from "@/components/StaffLayout";
import { KPICards } from "@/features/dashboard/KPICards";
import { IssueMap } from "@/features/map/IssueMap";
import { PriorityBadge, DemoBadge } from "@/components/Badges";
import { DataScopeFilter } from "@/components/DataScopeFilter";
import { Spinner } from "@/components/Spinner";
import { api } from "@/services/api";
import type { DataScope, KPISummary, MapMarker, StaffIssueSummary } from "@/types";

export default function StaffDashboard() {
  const [dataScope, setDataScope] = useState<DataScope>("live");
  const [summary, setSummary] = useState<KPISummary | null>(null);
  const [markers, setMarkers] = useState<MapMarker[]>([]);
  const [priorityIssues, setPriorityIssues] = useState<StaffIssueSummary[]>([]);

  useEffect(() => {
    setSummary(null);
    api.dashboardSummary(dataScope).then(setSummary).catch(() => {});
    api.dashboardMap(dataScope).then(setMarkers).catch(() => {});
    api.staffIssues({ data_scope: dataScope, active_only: true }).then((issues) => setPriorityIssues(issues.slice(0, 8))).catch(() => {});
  }, [dataScope]);

  const center: [number, number] = markers.length
    ? [markers[0].latitude, markers[0].longitude]
    : [13.0827, 80.2707];

  return (
    <StaffLayout>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold text-slate-800">Command Center</h1>
        <DataScopeFilter value={dataScope} onChange={setDataScope} />
      </div>

      {!summary ? <Spinner label="Loading dashboard…" /> : <KPICards summary={summary} />}

      <div className="mt-6 grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="h-[420px] rounded-2xl border border-slate-200 bg-white p-2 shadow-sm lg:col-span-2">
          <IssueMap markers={markers} center={center} />
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <h2 className="mb-3 text-sm font-bold text-slate-600">Priority Issue List</h2>
          <div className="flex flex-col gap-2">
            {priorityIssues.map((issue) => (
              <Link
                key={issue.id}
                to={`/staff/issues/${issue.id}`}
                className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2 hover:bg-slate-50"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-slate-800">{issue.complaint_id}</p>
                    {issue.is_demo && <DemoBadge />}
                  </div>
                  <p className="text-xs text-slate-500">{issue.issue_type}</p>
                </div>
                <div className="flex flex-col items-end gap-1">
                  <PriorityBadge level={issue.priority_level} />
                  {issue.is_overdue && <span className="text-[10px] font-bold text-red-600">OVERDUE</span>}
                </div>
              </Link>
            ))}
            {priorityIssues.length === 0 && (
              <p className="text-sm text-slate-400">
                {dataScope === "live" ? "No live citizen complaints yet." : "No complaints yet."}
              </p>
            )}
          </div>
          <Link to="/staff/issues" className="mt-3 block text-center text-xs font-semibold text-brand-700 underline">
            View all issues →
          </Link>
        </div>
      </div>
    </StaffLayout>
  );
}
