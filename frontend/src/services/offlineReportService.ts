import { openDB, type DBSchema, type IDBPDatabase } from "idb";
import type { OfflineReport, SyncStatus } from "@/types";

interface CivicFixDB extends DBSchema {
  reports: {
    key: string; // client_report_id
    value: OfflineReport;
    indexes: { "by-status": SyncStatus };
  };
}

const DB_NAME = "civicfix-offline";
const DB_VERSION = 1;

let dbPromise: Promise<IDBPDatabase<CivicFixDB>> | null = null;

function getDb() {
  if (!dbPromise) {
    dbPromise = openDB<CivicFixDB>(DB_NAME, DB_VERSION, {
      upgrade(db) {
        const store = db.createObjectStore("reports", { keyPath: "client_report_id" });
        store.createIndex("by-status", "sync_status");
      },
    });
  }
  return dbPromise;
}

export async function saveOfflineReport(report: OfflineReport): Promise<void> {
  const db = await getDb();
  await db.put("reports", report);
}

export async function getPendingReports(): Promise<OfflineReport[]> {
  const db = await getDb();
  const all = await db.getAll("reports");
  return all.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
}

export async function getReport(clientReportId: string): Promise<OfflineReport | undefined> {
  const db = await getDb();
  return db.get("reports", clientReportId);
}

export async function updateSyncStatus(
  clientReportId: string,
  status: SyncStatus,
  extra: Partial<OfflineReport> = {}
): Promise<void> {
  const db = await getDb();
  const existing = await db.get("reports", clientReportId);
  if (!existing) return;
  await db.put("reports", { ...existing, sync_status: status, last_sync_attempt: new Date().toISOString(), ...extra });
}

export async function deleteSyncedReport(clientReportId: string): Promise<void> {
  const db = await getDb();
  await db.delete("reports", clientReportId);
}

export async function incrementSyncAttempts(clientReportId: string): Promise<void> {
  const db = await getDb();
  const existing = await db.get("reports", clientReportId);
  if (!existing) return;
  await db.put("reports", { ...existing, sync_attempts: (existing.sync_attempts || 0) + 1 });
}
