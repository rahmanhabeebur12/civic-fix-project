import { useEffect, useState } from "react";
import { useAppStore } from "@/store/appStore";
import { SYNC_UPDATE_EVENT } from "@/services/syncService";
import { getPendingReports } from "@/services/offlineReportService";

export function useConnectivity() {
  const isOnline = useAppStore((s) => s.isOnline);
  const setOnline = useAppStore((s) => s.setOnline);
  const [pendingCount, setPendingCount] = useState(0);
  const [syncingCount, setSyncingCount] = useState(0);

  useEffect(() => {
    const onOnline = () => setOnline(true);
    const onOffline = () => setOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, [setOnline]);

  useEffect(() => {
    const refresh = async () => {
      const reports = await getPendingReports();
      setPendingCount(reports.filter((r) => r.sync_status === "PENDING_SYNC" || r.sync_status === "SYNC_FAILED").length);
      setSyncingCount(reports.filter((r) => r.sync_status === "SYNCING").length);
    };
    refresh();
    window.addEventListener(SYNC_UPDATE_EVENT, refresh);
    const interval = setInterval(refresh, 5000);
    return () => {
      window.removeEventListener(SYNC_UPDATE_EVENT, refresh);
      clearInterval(interval);
    };
  }, []);

  const status: "online" | "offline" | "syncing" = !isOnline ? "offline" : syncingCount > 0 ? "syncing" : "online";

  return { isOnline, status, pendingCount };
}
