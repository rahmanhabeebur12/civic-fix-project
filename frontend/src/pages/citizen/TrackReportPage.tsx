import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { CitizenLayout } from "@/components/CitizenLayout";
import { useTranslation } from "@/hooks/useTranslation";
import { useRevalidateOnFocus } from "@/hooks/useRevalidateOnFocus";
import { api, imageUrl, ApiError } from "@/services/api";
import { PriorityBadge, StatusBadge } from "@/components/Badges";
import { Spinner } from "@/components/Spinner";
import { getCitizenStatusLabel, getCitizenStatusMessage, getTimelineStepIndex } from "@/constants/citizenStatus";
import type { IssueTrackingResponse } from "@/types";

const TIMELINE_STEPS = [
  { status: "SUBMITTED", labelKey: "timelineSubmitted" as const },
  { status: "ASSIGNED", labelKey: "timelineAssigned" as const },
  { status: "ACCEPTED", labelKey: "timelineAccepted" as const },
  { status: "IN_PROGRESS", labelKey: "timelineInProgress" as const },
  { status: "AWAITING_CITIZEN_VERIFICATION", labelKey: "timelineAwaiting" as const },
  { status: "RESOLVED", labelKey: "timelineResolved" as const },
];

export default function TrackReportPage() {
  const { t } = useTranslation();
  const { complaintId } = useParams<{ complaintId: string }>();
  const [issue, setIssue] = useState<IssueTrackingResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showingStale, setShowingStale] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<Date | null>(null);
  const [feedback, setFeedback] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [confirmedResult, setConfirmedResult] = useState<"fixed" | "reopened" | null>(null);
  const hasLoadedOnceRef = useRef(false);

  const load = useCallback(() => {
    if (!complaintId) return;
    api
      .trackReport(complaintId)
      .then((result) => {
        setIssue(result);
        setError(null);
        setShowingStale(false);
        setLastUpdatedAt(new Date());
        hasLoadedOnceRef.current = true;
      })
      .catch((e) => {
        // The backend status is the source of truth — if a refetch fails
        // (e.g. offline) while we already have a previously-loaded
        // report on screen, keep showing that instead of replacing it
        // with a hard error or (worse) a guessed newer status.
        if (hasLoadedOnceRef.current) {
          setShowingStale(true);
        } else {
          setError(e instanceof ApiError ? e.message : t.errorGeneric);
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [complaintId]);

  useEffect(load, [load]);
  useRevalidateOnFocus(load);

  if (error) {
    return (
      <CitizenLayout showBack>
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">{error}</p>
      </CitizenLayout>
    );
  }

  if (!issue) {
    return (
      <CitizenLayout showBack>
        <Spinner label="Loading…" />
      </CitizenLayout>
    );
  }

  // The backend status is the sole source of truth for how far this
  // report has actually progressed — see constants/citizenStatus.ts.
  const currentStepIndex = getTimelineStepIndex(issue.status);
  const latestResolution = issue.resolutions[issue.resolutions.length - 1];
  const awaitingVerification = issue.status === "AWAITING_CITIZEN_VERIFICATION" && latestResolution && latestResolution.citizen_confirmed === null;

  async function handleConfirm(confirmed: boolean) {
    if (!complaintId) return;
    setConfirming(true);
    try {
      await api.confirmResolution(complaintId, confirmed, feedback || undefined);
      setConfirmedResult(confirmed ? "fixed" : "reopened");
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : t.errorGeneric);
    } finally {
      setConfirming(false);
    }
  }

  return (
    <CitizenLayout showBack>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-800">{issue.complaint_id}</h1>
        <StatusBadge status={issue.status} label={getCitizenStatusLabel(issue.status)} />
      </div>

      {getCitizenStatusMessage(issue.status) && (
        <p className="mb-4 text-sm text-slate-500">{getCitizenStatusMessage(issue.status)}</p>
      )}

      {showingStale && (
        <p className="mb-4 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-500">
          {t.trackingOfflineNotice}
          {lastUpdatedAt && ` ${t.lastUpdatedLabel} ${lastUpdatedAt.toLocaleTimeString()}`}
        </p>
      )}

      {issue.image_url && (
        <img src={imageUrl(issue.image_url)} alt="" className="mb-4 h-48 w-full rounded-2xl object-cover" />
      )}

      <div className="card mb-4">
        <p className="text-sm text-slate-800">{issue.description}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <PriorityBadge level={issue.priority_level} />
          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">{issue.issue_type}</span>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
          <Info label={t.departmentLabel} value={issue.department} />
          <Info label="Reports" value={String(issue.reporter_count)} />
        </div>
      </div>

      <div className="card mb-4">
        <p className="mb-3 text-sm font-bold text-slate-600">Status Timeline</p>
        <ol className="flex flex-col gap-3">
          {TIMELINE_STEPS.map((step, i) => {
            const done = i < currentStepIndex || issue.status === "RESOLVED";
            const active = i === currentStepIndex && issue.status !== "RESOLVED";
            return (
              <li key={step.status} className="flex items-center gap-3">
                <span
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    done ? "bg-green-500 text-white" : active ? "bg-brand-500 text-white" : "border border-slate-300 text-slate-400"
                  }`}
                >
                  {done ? "✓" : active ? "●" : "○"}
                </span>
                <span className={done || active ? "text-slate-800" : "text-slate-400"}>{t[step.labelKey]}</span>
              </li>
            );
          })}
        </ol>
      </div>

      {latestResolution && (
        <div className="card mb-4">
          <p className="mb-3 text-sm font-bold text-slate-600">Before / After</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="mb-1 text-center text-xs font-semibold text-slate-400">{t.beforePhoto}</p>
              <img src={imageUrl(issue.image_url)} alt="Before" className="h-32 w-full rounded-lg object-cover" />
            </div>
            <div>
              <p className="mb-1 text-center text-xs font-semibold text-slate-400">{t.afterPhoto}</p>
              <img src={imageUrl(latestResolution.image_url)} alt="After" className="h-32 w-full rounded-lg object-cover" />
            </div>
          </div>
          <p className="mt-3 text-sm text-slate-600">{latestResolution.note}</p>
        </div>
      )}

      {awaitingVerification && !confirmedResult && (
        <div className="card mb-4 border-brand-200 bg-brand-50">
          <p className="mb-3 text-center font-semibold text-slate-800">{t.hasIssueBeenFixed}</p>
          <div className="flex flex-col gap-2">
            <button className="btn-primary" disabled={confirming} onClick={() => handleConfirm(true)}>
              {t.yesFixed}
            </button>
            <button className="btn-secondary" disabled={confirming} onClick={() => handleConfirm(false)}>
              {t.noStillExists}
            </button>
          </div>
          <textarea
            className="input-field mt-3"
            placeholder={t.reasonStillUnresolved}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
          />
        </div>
      )}

      {confirmedResult === "fixed" && (
        <p className="mb-4 rounded-xl bg-green-50 px-4 py-3 text-center text-sm font-medium text-green-800">{t.thankYouConfirmed}</p>
      )}
      {confirmedResult === "reopened" && (
        <p className="mb-4 rounded-xl bg-red-50 px-4 py-3 text-center text-sm font-medium text-red-800">{t.thankYouReopened}</p>
      )}
    </CitizenLayout>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-slate-400">{label}</p>
      <p className="font-medium text-slate-800">{value}</p>
    </div>
  );
}
