import { useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { CitizenLayout } from "@/components/CitizenLayout";
import { VOICE_GUIDANCE_EN } from "@/constants/voiceGuidance";
import { useTranslation } from "@/hooks/useTranslation";
import { useVoiceGuidance } from "@/hooks/useVoiceGuidance";
import { PriorityBadge, StatusBadge } from "@/components/Badges";
import type { ReportSubmitResponse } from "@/types";

export default function ReportSuccess() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const result = (location.state as { result?: ReportSubmitResponse } | null)?.result;
  const guidance = useVoiceGuidance();

  useEffect(() => {
    if (result) guidance.speak(VOICE_GUIDANCE_EN.successStep);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result]);

  if (!result) {
    navigate("/", { replace: true });
    return null;
  }

  return (
    <CitizenLayout>
      <div className="flex flex-col items-center text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-green-100 text-4xl">✅</div>
        <h1 className="mt-4 text-xl font-bold text-slate-800">{t.submittedSuccessTitle}</h1>

        {result.is_duplicate && (
          <p className="mt-2 rounded-xl bg-sky-50 px-4 py-2 text-sm text-sky-800">
            {t.linkedToExisting} {result.reporter_count} {t.reportersCount}.
          </p>
        )}

        <div className="card mt-6 w-full text-left">
          <Row label={t.complaintId} value={result.complaint_id} bold />
          <Row label={t.issueLabel} value={result.issue_type} />
          <Row label={t.departmentLabel} value={result.department} />
          <div className="flex items-center justify-between py-2">
            <span className="text-sm text-slate-500">{t.priorityLabel}</span>
            <PriorityBadge level={result.priority_level} />
          </div>
          <div className="flex items-center justify-between py-2">
            <span className="text-sm text-slate-500">{t.statusLabel}</span>
            <StatusBadge status={result.status} />
          </div>
        </div>

        <Link to={`/track/${result.complaint_id}`} className="btn-primary mt-6 w-full">
          {t.track}
        </Link>
        <Link to="/" className="btn-secondary mt-3 w-full">
          {t.appName}
        </Link>
      </div>
    </CitizenLayout>
  );
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-2 last:border-0">
      <span className="text-sm text-slate-500">{label}</span>
      <span className={bold ? "font-bold text-brand-700" : "text-slate-800"}>{value}</span>
    </div>
  );
}
