import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CitizenLayout } from "@/components/CitizenLayout";
import { useTranslation } from "@/hooks/useTranslation";

export default function TrackReportEntryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [complaintId, setComplaintId] = useState("");

  return (
    <CitizenLayout showBack>
      <div className="mx-auto flex max-w-sm flex-col items-center pt-6 text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-navy-100 text-3xl">📋</span>
        <h1 className="mt-4 text-xl font-bold text-navy-800">{t.trackByComplaintId}</h1>

        <form
          className="mt-6 flex w-full flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (complaintId.trim()) navigate(`/track/${complaintId.trim()}`);
          }}
        >
          <input
            className="input-field text-center text-lg"
            placeholder="CIV-2026-0001"
            value={complaintId}
            onChange={(e) => setComplaintId(e.target.value)}
            autoFocus
          />
          <button className="btn-primary" type="submit" disabled={!complaintId.trim()}>
            {t.track}
          </button>
        </form>
      </div>
    </CitizenLayout>
  );
}
