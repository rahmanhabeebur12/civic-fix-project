import { useEffect, useState } from "react";
import { MapContainer, TileLayer } from "react-leaflet";
import { StaffLayout } from "@/components/StaffLayout";
import { Spinner } from "@/components/Spinner";
import { HeatmapLayer } from "@/features/map/HeatmapLayer";
import { api } from "@/services/api";
import type { BacklogAnalytics, CategoryBreakdown, DepartmentPerformance, HeatmapPoint, Hotspot, ResponseTimeAnalytics } from "@/types";

const HEATMAP_PERIODS = [
  { label: "7 days", days: 7 },
  { label: "30 days", days: 30 },
  { label: "90 days", days: 90 },
  { label: "6 months", days: 182 },
];

export default function AnalyticsPage() {
  const [departments, setDepartments] = useState<DepartmentPerformance[] | null>(null);
  const [categories, setCategories] = useState<CategoryBreakdown[] | null>(null);
  const [hotspots, setHotspots] = useState<Hotspot[] | null>(null);
  const [responseTimes, setResponseTimes] = useState<ResponseTimeAnalytics | null>(null);
  const [backlog, setBacklog] = useState<BacklogAnalytics | null>(null);

  const [heatmapDays, setHeatmapDays] = useState(30);
  const [heatmapCategory, setHeatmapCategory] = useState("All");
  const [heatmapPoints, setHeatmapPoints] = useState<HeatmapPoint[] | null>(null);

  useEffect(() => {
    api.departmentAnalytics().then(setDepartments).catch(() => setDepartments([]));
    api.categoryAnalytics().then(setCategories).catch(() => setCategories([]));
    api.hotspots().then(setHotspots).catch(() => setHotspots([]));
    api.responseTimeAnalytics().then(setResponseTimes).catch(() => {});
    api.backlogAnalytics().then(setBacklog).catch(() => {});
  }, []);

  useEffect(() => {
    setHeatmapPoints(null);
    api.heatmap(heatmapDays, heatmapCategory).then(setHeatmapPoints).catch(() => setHeatmapPoints([]));
  }, [heatmapDays, heatmapCategory]);

  const maxCategoryCount = Math.max(1, ...(categories || []).map((c) => c.count));
  // Initial view only — HeatmapLayer pans to the actual data once loaded,
  // since the map now stays mounted across filter changes (see below).
  const heatmapCenter: [number, number] = [13.0827, 80.2707];

  return (
    <StaffLayout>
      <h1 className="mb-5 text-xl font-bold text-slate-800">Analytics</h1>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-3 text-sm font-bold text-slate-600">Issues by Category</h2>
          {!categories ? (
            <Spinner label="Loading…" />
          ) : (
            <div className="flex flex-col gap-2">
              {categories.map((c) => (
                <div key={c.category}>
                  <div className="mb-1 flex justify-between text-xs text-slate-500">
                    <span>{c.category}</span>
                    <span>{c.count}</span>
                  </div>
                  <div className="h-2.5 w-full rounded-full bg-slate-100">
                    <div className="h-2.5 rounded-full bg-brand-500" style={{ width: `${(c.count / maxCategoryCount) * 100}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="mb-3 text-sm font-bold text-slate-600">Department Performance</h2>
          {!departments ? (
            <Spinner label="Loading…" />
          ) : departments.length === 0 ? (
            <p className="text-sm text-slate-400">No department activity yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead className="text-left text-slate-400">
                  <tr>
                    <th className="py-1 pr-2">Dept</th>
                    <th className="py-1 pr-2">Open</th>
                    <th className="py-1 pr-2">Critical</th>
                    <th className="py-1 pr-2">Resolved</th>
                    <th className="py-1 pr-2">Overdue</th>
                    <th className="py-1 pr-2">Reopened</th>
                    <th className="py-1 pr-2">Avg Resp.</th>
                    <th className="py-1 pr-2">Avg Res.</th>
                  </tr>
                </thead>
                <tbody>
                  {departments.map((d) => (
                    <tr key={d.department} className="border-t border-slate-100">
                      <td className="py-1.5 pr-2 font-medium text-slate-700">{d.department}</td>
                      <td className="py-1.5 pr-2">{d.open_issues}</td>
                      <td className="py-1.5 pr-2 text-red-600">{d.critical_issues}</td>
                      <td className="py-1.5 pr-2 text-green-600">{d.resolved_count}</td>
                      <td className="py-1.5 pr-2 text-red-600">{d.overdue_issues}</td>
                      <td className="py-1.5 pr-2">{d.reopened_issues}</td>
                      <td className="py-1.5 pr-2">{d.avg_response_time_hours}h</td>
                      <td className="py-1.5 pr-2">{d.avg_resolution_time_hours}h</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
        <div className="card">
          <h2 className="mb-3 text-sm font-bold text-slate-600">Response Times</h2>
          {!responseTimes ? (
            <Spinner label="Loading…" />
          ) : (
            <div className="grid grid-cols-2 gap-3 text-xs">
              <Stat label="Avg. time to assign" value={`${responseTimes.avg_time_to_assignment_hours}h`} />
              <Stat label="Median time to assign" value={`${responseTimes.median_time_to_assignment_hours}h`} />
              <Stat label="Avg. time to accept" value={`${responseTimes.avg_time_to_accept_hours}h`} />
              <Stat label="Median time to accept" value={`${responseTimes.median_time_to_accept_hours}h`} />
              <Stat label="Avg. time to start work" value={`${responseTimes.avg_time_to_start_work_hours}h`} />
              <Stat label="Avg. resolution time" value={`${responseTimes.avg_time_to_resolution_hours}h`} />
              <Stat label="Median resolution time" value={`${responseTimes.median_time_to_resolution_hours}h`} />
              <Stat label="Avg. unresolved age" value={`${responseTimes.avg_unresolved_age_hours}h`} />
            </div>
          )}
          {responseTimes && responseTimes.oldest_unresolved.length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-xs font-semibold uppercase text-slate-400">Oldest Unresolved</p>
              <div className="flex flex-col gap-1.5">
                {responseTimes.oldest_unresolved.map((o) => (
                  <div key={o.complaint_id} className="flex items-center justify-between rounded-lg border border-slate-100 px-2 py-1.5 text-xs">
                    <span className="font-medium text-slate-700">{o.complaint_id}</span>
                    <span className="text-slate-500">{o.issue_type}</span>
                    <span className="font-semibold text-red-600">{Math.round(o.age_hours / 24)}d old</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="card">
          <h2 className="mb-3 text-sm font-bold text-slate-600">Backlog</h2>
          {!backlog ? (
            <Spinner label="Loading…" />
          ) : (
            <>
              <div className="mb-4 grid grid-cols-2 gap-3 text-xs">
                <Stat label="Open backlog" value={String(backlog.total_open_backlog)} />
                <Stat label="Total resolved" value={String(backlog.total_resolved)} />
                <Stat label="HIGH backlog" value={String(backlog.high_backlog)} accent="text-orange-600" />
                <Stat label="CRITICAL backlog" value={String(backlog.critical_backlog)} accent="text-red-600" />
              </div>
              {backlog.per_department.length > 0 && (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead className="text-left text-slate-400">
                      <tr><th className="py-1 pr-2">Dept</th><th className="py-1 pr-2">Backlog</th><th className="py-1 pr-2">High</th><th className="py-1 pr-2">Critical</th></tr>
                    </thead>
                    <tbody>
                      {backlog.per_department.map((d) => (
                        <tr key={d.department} className="border-t border-slate-100">
                          <td className="py-1.5 pr-2 font-medium text-slate-700">{d.department}</td>
                          <td className="py-1.5 pr-2">{d.backlog}</td>
                          <td className="py-1.5 pr-2 text-orange-600">{d.high_backlog}</td>
                          <td className="py-1.5 pr-2 text-red-600">{d.critical_backlog}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      <div className="card mt-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-sm font-bold text-slate-600">Recurring Issue Heatmap</h2>
            <p className="text-xs text-slate-400">Historical resolved issues — for maintenance planning, not current open problems.</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {HEATMAP_PERIODS.map((p) => (
              <button
                key={p.days}
                onClick={() => setHeatmapDays(p.days)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${heatmapDays === p.days ? "bg-brand-600 text-white" : "border border-slate-300 bg-white text-slate-600"}`}
              >
                {p.label}
              </button>
            ))}
            <select
              className="rounded-lg border border-slate-300 px-2 py-1.5 text-xs"
              value={heatmapCategory}
              onChange={(e) => setHeatmapCategory(e.target.value)}
            >
              <option value="All">All categories</option>
              {(categories || []).map((c) => (
                <option key={c.category} value={c.category}>{c.category}</option>
              ))}
            </select>
          </div>
        </div>
        <div className="relative h-[380px] overflow-hidden rounded-xl border border-slate-200">
          {/* The map itself stays mounted across filter changes — only the
              heat layer's data updates — so switching days/category
              refreshes the layer instead of tearing down and rebuilding
              the whole Leaflet map each time. */}
          <MapContainer center={heatmapCenter} zoom={12} className="h-full w-full">
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <HeatmapLayer points={heatmapPoints || []} />
          </MapContainer>
          {!heatmapPoints && (
            <div className="absolute inset-0 z-[1000] flex items-center justify-center bg-white/70">
              <Spinner label="Loading heatmap…" />
            </div>
          )}
        </div>
        {heatmapPoints && heatmapPoints.length === 0 && (
          <p className="mt-2 text-xs text-slate-400">No resolved issues in this period/category yet.</p>
        )}
      </div>

      <div className="card mt-5">
        <h2 className="mb-1 text-sm font-bold text-slate-600">Recurring Hotspots</h2>
        <p className="mb-3 text-xs text-slate-400">Planning insight from clustered nearby reports — not a guaranteed diagnosis.</p>
        {!hotspots ? (
          <Spinner label="Loading…" />
        ) : hotspots.length === 0 ? (
          <p className="text-sm text-slate-400">No recurring hotspots detected.</p>
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {hotspots.map((h, i) => (
              <div key={i} className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                <p className="font-semibold text-amber-900">{h.label}</p>
                <p className="text-sm text-amber-800">Primary issue: {h.primary_issue_type}</p>
                <p className="text-xs text-amber-700">
                  {h.report_count} reports · {h.issue_count} clustered issues · last {h.period_days} days · avg recurrence {h.avg_recurrence_days} days
                </p>
                <p className="mt-2 text-xs italic text-amber-700">{h.recommendation}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </StaffLayout>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wide text-slate-400">{label}</p>
      <p className={`text-sm font-bold ${accent || "text-slate-800"}`}>{value}</p>
    </div>
  );
}
