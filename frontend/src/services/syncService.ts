import { checkHealth, api, ApiError } from "@/services/api";
import {
  getPendingReports, updateSyncStatus, deleteSyncedReport, incrementSyncAttempts,
} from "@/services/offlineReportService";
import type { OfflineReport } from "@/types";

export const SYNC_UPDATE_EVENT = "civicfix:sync-update";

function emitUpdate() {
  window.dispatchEvent(new CustomEvent(SYNC_UPDATE_EVENT));
}

function reportToFormData(report: OfflineReport): FormData {
  const form = new FormData();
  form.set("client_report_id", report.client_report_id);
  form.set("description", report.description);
  form.set("latitude", String(report.latitude));
  form.set("longitude", String(report.longitude));
  if (report.accuracy != null) form.set("accuracy", String(report.accuracy));
  form.set("language", report.language);
  form.set("name", report.name);
  form.set("mobile", report.mobile);
  form.set("was_offline", "true");
  form.set("description_source", report.description_source || "TYPED");
  // Accessibility: a report may have been saved offline with only a
  // photo or only a description — never both required.
  if (report.imageBlob && report.imageType) {
    const ext = report.imageType.includes("png") ? "png" : report.imageType.includes("webp") ? "webp" : "jpg";
    form.set("image", new File([report.imageBlob], `report.${ext}`, { type: report.imageType }));
  }
  return form;
}

let syncing = false;

export async function syncPendingReports(): Promise<void> {
  if (syncing) return;
  syncing = true;
  try {
    const backendUp = await checkHealth();
    if (!backendUp) return;

    const pending = (await getPendingReports()).filter(
      (r) => r.sync_status === "PENDING_SYNC" || r.sync_status === "SYNC_FAILED"
    );

    for (const report of pending) {
      await updateSyncStatus(report.client_report_id, "SYNCING");
      emitUpdate();
      try {
        const result = await api.submitReport(reportToFormData(report));
        await updateSyncStatus(report.client_report_id, "SYNCED", { complaint_id: result.complaint_id });
        emitUpdate();
        // Keep the SYNCED record briefly visible, then remove it from the local queue.
        setTimeout(() => {
          deleteSyncedReport(report.client_report_id).then(emitUpdate);
        }, 4000);
      } catch (err) {
        await incrementSyncAttempts(report.client_report_id);
        const message = err instanceof ApiError ? err.message : "Could not reach the server.";
        await updateSyncStatus(report.client_report_id, "SYNC_FAILED", { error_message: message });
        emitUpdate();
      }
    }
  } finally {
    syncing = false;
  }
}

export async function retryFailedReports(): Promise<void> {
  const db = await getPendingReports();
  const failed = db.filter((r) => r.sync_status === "SYNC_FAILED");
  for (const r of failed) {
    await updateSyncStatus(r.client_report_id, "PENDING_SYNC");
  }
  emitUpdate();
  await syncPendingReports();
}

let listenersRegistered = false;

export function registerConnectivityListeners() {
  if (listenersRegistered) return;
  listenersRegistered = true;

  window.addEventListener("online", () => {
    syncPendingReports();
  });

  // Also attempt a sync shortly after load, in case reports were queued
  // while the app was closed and connectivity is already back.
  if (navigator.onLine) {
    setTimeout(() => syncPendingReports(), 1500);
  }

  // Periodic safety-net retry every 30s while online, in case the online
  // event was missed (e.g. flaky connections).
  setInterval(() => {
    if (navigator.onLine) syncPendingReports();
  }, 30000);
}
