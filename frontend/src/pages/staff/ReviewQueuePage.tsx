import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { StaffLayout } from "@/components/StaffLayout";
import { ValidityBadge } from "@/components/Badges";
import { Spinner } from "@/components/Spinner";
import { api, imageUrl, ApiError } from "@/services/api";
import type { StaffIssueSummary } from "@/types";

export default function ReviewQueuePage() {
  const [issues, setIssues] = useState<StaffIssueSummary[] | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setError(null);
    api
      .staffIssues({ status: "MANUAL_REVIEW" })
      .then((result) => {
        setIssues(result);
        setError(null);
      })
      .catch((e) => {
        // A genuine failure must still clear the spinner, but showing
        // "No manual-review reports" would be misleading — the request
        // failed, it didn't legitimately return zero rows.
        setIssues([]);
        setError(e instanceof ApiError ? e.message : "Something went wrong. Please try again.");
      });
  }

  useEffect(load, []);

  async function decide(id: number, decision: "APPROVED" | "REJECTED") {
    setBusyId(id);
    setError(null);
    try {
      await api.reviewDecision(id, decision);
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Action failed.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <StaffLayout>
      <h1 className="mb-1 text-xl font-bold text-slate-800">Review Queue</h1>
      <p className="mb-5 text-sm text-slate-500">Reports flagged REVIEW or SUSPICIOUS by the validity engine, awaiting manual staff decision.</p>

      {error && <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

      {!issues ? (
        <Spinner label="Loading…" />
      ) : issues.length === 0 && !error ? (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-400">No manual-review reports.</p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {issues.map((issue) => (
            <div key={issue.id} className="card">
              {issue.image_url && <img src={imageUrl(issue.image_url)} className="mb-3 h-40 w-full rounded-lg object-cover" />}
              <div className="mb-2 flex items-center justify-between">
                <p className="font-semibold text-slate-800">{issue.complaint_id}</p>
                <ValidityBadge status={issue.validity_status} />
              </div>
              <p className="text-sm text-slate-600">{issue.issue_type}</p>
              <p className="mt-1 text-xs text-slate-400">{issue.latitude.toFixed(4)}, {issue.longitude.toFixed(4)}</p>
              {issue.review_reasons.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {issue.review_reasons.map((r) => (
                    <span key={r} className="rounded-full bg-purple-50 px-2 py-0.5 text-[10px] font-semibold text-purple-700">{r.replace(/_/g, " ")}</span>
                  ))}
                </div>
              )}
              <Link to={`/staff/issues/${issue.id}`} className="mt-1 inline-block text-xs font-semibold text-brand-700 underline">
                View full details & flags →
              </Link>
              <div className="mt-3 flex gap-2">
                <button className="btn-primary flex-1 py-2 text-sm" disabled={busyId === issue.id} onClick={() => decide(issue.id, "APPROVED")}>Approve</button>
                <button className="btn-danger flex-1 py-2 text-sm" disabled={busyId === issue.id} onClick={() => decide(issue.id, "REJECTED")}>Reject</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </StaffLayout>
  );
}
