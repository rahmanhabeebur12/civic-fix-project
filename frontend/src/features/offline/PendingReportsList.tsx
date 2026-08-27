import { useEffect, useState } from "react";
import { useTranslation } from "@/hooks/useTranslation";
import { getPendingReports } from "@/services/offlineReportService";
import { retryFailedReports, SYNC_UPDATE_EVENT } from "@/services/syncService";
import type { OfflineReport } from "@/types";

const STATUS_LABEL_KEY: Record<string, keyof ReturnType<typeof useTranslation>["t"]> = {
  PENDING_SYNC: "waitingToSync",
  SYNCING: "syncing",
  SYNCED: "synced",
  SYNC_FAILED: "syncFailed",
};

const STATUS_STYLE: Record<string, string> = {
  PENDING_SYNC: "bg-amber-100 text-amber-800",
  SYNCING: "bg-sky-100 text-sky-800 animate-pulse",
  SYNCED: "bg-green-100 text-green-800",
  SYNC_FAILED: "bg-red-100 text-red-800",
};

export function PendingReportsList() {
  const { t } = useTranslation();
  const [reports, setReports] = useState<OfflineReport[]>([]);

  useEffect(() => {
    const refresh = () => getPendingReports().then(setReports);
    refresh();
    window.addEventListener(SYNC_UPDATE_EVENT, refresh);
    return () => window.removeEventListener(SYNC_UPDATE_EVENT, refresh);
  }, []);

  if (reports.length === 0) {
    return <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-400">{t.noPendingReports}</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {reports.map((r) => {
        const previewUrl = r.imageBlob ? URL.createObjectURL(r.imageBlob) : null;
        return (
          <div key={r.client_report_id} className="card flex gap-3">
            {previewUrl ? (
              <img src={previewUrl} alt="" className="h-16 w-16 rounded-lg object-cover" />
            ) : (
              <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-2xl">📝</div>
            )}
            <div className="flex-1">
              <p className="line-clamp-1 text-sm font-semibold text-slate-800">{r.description || "(No description — photo only)"}</p>
              <p className="mt-0.5 text-xs text-slate-400">
                {t.savedAt} {new Date(r.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </p>
              <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLE[r.sync_status]}`}>
                {t[STATUS_LABEL_KEY[r.sync_status]]}
              </span>
              {r.sync_status === "SYNC_FAILED" && (
                <button className="ml-2 text-xs font-semibold text-brand-700 underline" onClick={() => retryFailedReports()}>
                  Retry
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
