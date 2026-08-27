import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CitizenLayout } from "@/components/CitizenLayout";
import { useTranslation } from "@/hooks/useTranslation";
import { useRevalidateOnFocus } from "@/hooks/useRevalidateOnFocus";
import { useAppStore } from "@/store/appStore";
import { api } from "@/services/api";
import { imageUrl } from "@/services/api";
import { getPendingReports } from "@/services/offlineReportService";
import { PriorityBadge, StatusBadge } from "@/components/Badges";
import { Spinner } from "@/components/Spinner";
import { getCitizenStatusLabel } from "@/constants/citizenStatus";
import type { MyReportSummary } from "@/types";

export default function MyReportsPage() {
  const { t } = useTranslation();
  const citizen = useAppStore((s) => s.citizen);
  const navigate = useNavigate();
  const [reports, setReports] = useState<MyReportSummary[] | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [trackInput, setTrackInput] = useState("");
  const hasLoadedOnceRef = useRef(false);

  const load = useCallback(() => {
    getPendingReports().then((r) => setPendingCount(r.length));
    if (citizen?.mobile) {
      api
        .myReports(citizen.mobile)
        .then((result) => {
          setReports(result);
          hasLoadedOnceRef.current = true;
        })
        .catch(() => {
          // Same principle as Track Report: the backend is the source of
          // truth, but if a refresh fails (e.g. offline) after we've
          // already shown real data once, keep showing it rather than
          // blanking to an empty list.
          if (!hasLoadedOnceRef.current) setReports([]);
        });
    } else {
      setReports([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [citizen]);

  useEffect(load, [load]);
  useRevalidateOnFocus(load);

  return (
    <CitizenLayout showBack>
      <h1 className="mb-4 text-xl font-bold text-slate-800">{t.myReports}</h1>

      {pendingCount > 0 && (
        <Link to="/pending-reports" className="mb-4 flex items-center justify-between rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span>{pendingCount} {t.pendingReports}</span>
          <span>→</span>
        </Link>
      )}

      <form
        className="mb-5 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (trackInput.trim()) navigate(`/track/${trackInput.trim()}`);
        }}
      >
        <input
          className="input-field"
          placeholder={t.trackByComplaintId}
          value={trackInput}
          onChange={(e) => setTrackInput(e.target.value)}
        />
        <button className="btn-secondary" type="submit">
          {t.track}
        </button>
      </form>

      {reports === null && <Spinner label="Loading…" />}

      {reports !== null && reports.length === 0 && (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-400">{t.noReportsYet}</p>
      )}

      <div className="flex flex-col gap-3">
        {reports?.map((r) => (
          <Link key={r.complaint_id} to={`/track/${r.complaint_id}`} className="card flex gap-3">
            {r.image_url && <img src={imageUrl(r.image_url)} alt="" className="h-16 w-16 rounded-lg object-cover" />}
            <div className="flex-1">
              <p className="text-sm font-semibold text-slate-800">{r.issue_type}</p>
              <p className="text-xs text-slate-400">{r.complaint_id}</p>
              <div className="mt-1 flex gap-2">
                <StatusBadge status={r.status} label={getCitizenStatusLabel(r.status)} />
                <PriorityBadge level={r.priority_level} />
              </div>
            </div>
          </Link>
        ))}
      </div>
    </CitizenLayout>
  );
}
