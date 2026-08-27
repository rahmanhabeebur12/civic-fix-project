import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CitizenLayout } from "@/components/CitizenLayout";
import { Spinner } from "@/components/Spinner";
import { PriorityBadge, StatusBadge } from "@/components/Badges";
import { useTranslation } from "@/hooks/useTranslation";
import { useGeolocation } from "@/hooks/useGeolocation";
import { useAppStore } from "@/store/appStore";
import { api, ApiError } from "@/services/api";
import type { NearbyIssueItem } from "@/types";

const RADIUS_OPTIONS = [1, 3, 5];

function formatDistance(meters: number): string {
  if (meters < 1000) return `${Math.round(meters)}m`;
  return `${(meters / 1000).toFixed(1)}km`;
}

export default function NearbyIssuesPage() {
  const { t } = useTranslation();
  const citizen = useAppStore((s) => s.citizen);
  const setCitizen = useAppStore((s) => s.setCitizen);
  const { location, status, capture } = useGeolocation();

  const [radiusKm, setRadiusKm] = useState(3);
  const [issues, setIssues] = useState<NearbyIssueItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [supportingId, setSupportingId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Record<string, string>>({});
  const [formFor, setFormFor] = useState<string | null>(null);
  const [name, setName] = useState(citizen?.name || "");
  const [mobile, setMobile] = useState(citizen?.mobile || "");

  useEffect(() => {
    capture();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!location) return;
    setIssues(null);
    api
      .nearbyIssues(location.latitude, location.longitude, radiusKm)
      .then(setIssues)
      .catch(() => setError(t.errorGeneric));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location, radiusKm]);

  async function handleSupport(complaintId: string) {
    const trimmedName = name.trim();
    const trimmedMobile = mobile.trim();
    if (trimmedName.length < 2 || !/^\d{10}$/.test(trimmedMobile)) {
      setFormFor(complaintId);
      return;
    }
    setSupportingId(complaintId);
    try {
      await api.addSupport(complaintId, {
        client_report_id: crypto.randomUUID(),
        name: trimmedName,
        mobile: trimmedMobile,
        language: "en",
      });
      setCitizen({ name: trimmedName, mobile: trimmedMobile });
      setFeedback((f) => ({ ...f, [complaintId]: t.supportSent }));
      setFormFor(null);
    } catch (e) {
      setFeedback((f) => ({ ...f, [complaintId]: e instanceof ApiError ? e.message : t.supportFailed }));
    } finally {
      setSupportingId(null);
    }
  }

  return (
    <CitizenLayout showBack>
      <h1 className="text-xl font-bold text-navy-800">{t.nearbyIssuesTitle}</h1>
      <p className="mb-4 text-sm text-slate-500">{t.nearbyIssuesHint}</p>

      <div className="mb-4">
        <p className="mb-1 text-xs font-semibold uppercase text-slate-400">{t.nearbyRadius}</p>
        <div className="flex gap-2">
          {RADIUS_OPTIONS.map((km) => (
            <button
              key={km}
              onClick={() => setRadiusKm(km)}
              className={`tap-target flex-1 rounded-lg px-4 py-2 text-sm font-semibold ${
                radiusKm === km ? "bg-navy-800 text-white" : "border border-slate-300 bg-white text-slate-600"
              }`}
            >
              {km} km
            </button>
          ))}
        </div>
      </div>

      {status === "idle" || status === "loading" ? (
        <Spinner label={t.nearbyLoading} />
      ) : status === "denied" || status === "error" ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-4 text-center text-sm text-amber-800">
          <p className="mb-2">{t.nearbyLocationNeeded}</p>
          <button className="btn-secondary" onClick={capture}>{t.nearbyEnableLocation}</button>
        </div>
      ) : !issues ? (
        <Spinner label={t.nearbyLoading} />
      ) : error ? (
        <p className="text-sm text-red-600">{error}</p>
      ) : issues.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-10 text-center">
          <p className="text-sm text-slate-400">{t.nearbyNone}</p>
          <Link to="/report" className="btn-primary mt-4 inline-flex">{t.nearbyReportNew}</Link>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {issues.map((issue) => (
            <div key={issue.complaint_id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-bold text-navy-800">{issue.issue_type}</p>
                  <p className="text-xs text-slate-400">{issue.category}</p>
                </div>
                <PriorityBadge level={issue.priority_level} />
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
                <StatusBadge status={issue.status} />
                <span>📍 {formatDistance(issue.distance_meters)} {t.nearbyAway}</span>
                <span>· {issue.reporter_count} {t.reportersCount}</span>
              </div>

              {feedback[issue.complaint_id] ? (
                <p className="mt-3 text-sm font-medium text-brand-700">{feedback[issue.complaint_id]}</p>
              ) : formFor === issue.complaint_id ? (
                <div className="mt-3 flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <input className="input-field" placeholder={t.yourName} value={name} onChange={(e) => setName(e.target.value)} />
                  <input
                    className="input-field"
                    placeholder={t.yourMobile}
                    inputMode="numeric"
                    value={mobile}
                    onChange={(e) => setMobile(e.target.value.replace(/\D/g, "").slice(0, 10))}
                  />
                  <button className="btn-primary" disabled={supportingId === issue.complaint_id} onClick={() => handleSupport(issue.complaint_id)}>
                    {supportingId === issue.complaint_id ? t.submitting : t.addSupport}
                  </button>
                </div>
              ) : (
                <div className="mt-3 flex gap-2">
                  <Link
                    to={`/track/${issue.complaint_id}`}
                    className="tap-target flex flex-1 items-center justify-center rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
                  >
                    {t.viewIssue}
                  </Link>
                  <button
                    className="tap-target flex-1 rounded-lg bg-navy-800 px-3 py-2 text-sm font-semibold text-white"
                    disabled={supportingId === issue.complaint_id}
                    onClick={() => handleSupport(issue.complaint_id)}
                  >
                    {supportingId === issue.complaint_id ? t.submitting : `🤝 ${t.addSupport}`}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </CitizenLayout>
  );
}
