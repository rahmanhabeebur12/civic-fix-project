import type { KPISummary } from "@/types";

export function KPICards({ summary }: { summary: KPISummary }) {
  const cards: { label: string; value: string | number; accent?: string }[] = [
    { label: "Open Issues", value: summary.open_issues },
    { label: "Critical Issues", value: summary.critical_issues, accent: "text-red-600" },
    { label: "In Progress", value: summary.in_progress, accent: "text-amber-600" },
    { label: "Resolved Today", value: summary.resolved_today, accent: "text-green-600" },
    { label: "Avg Response Time", value: `${summary.avg_response_time_hours}h` },
    { label: "Avg Resolution Time", value: `${summary.avg_resolution_time_hours}h` },
    { label: "Pending Backlog", value: summary.pending_backlog },
    { label: "Reopened Issues", value: summary.reopened_issues, accent: "text-red-600" },
    { label: "Manual Review Queue", value: summary.manual_review_queue, accent: "text-purple-600" },
    { label: "Overdue Issues", value: summary.overdue_issues, accent: "text-red-600" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {cards.map((c) => (
        <div key={c.label} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium text-slate-500">{c.label}</p>
          <p className={`mt-1 text-2xl font-bold ${c.accent || "text-slate-800"}`}>{c.value}</p>
        </div>
      ))}
    </div>
  );
}
