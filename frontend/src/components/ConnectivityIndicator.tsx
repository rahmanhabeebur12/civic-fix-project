import { useConnectivity } from "@/hooks/useConnectivity";
import { useTranslation } from "@/hooks/useTranslation";

export function ConnectivityIndicator() {
  const { status, pendingCount } = useConnectivity();
  const { t } = useTranslation();

  const dotColor = status === "online" ? "bg-green-500" : status === "syncing" ? "bg-amber-500 animate-pulse" : "bg-red-500";
  const label = status === "online" ? t.online : status === "syncing" ? t.syncing : t.offline;

  return (
    <div className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 shadow-sm">
      <span className={`h-2 w-2 rounded-full ${dotColor}`} />
      {label}
      {pendingCount > 0 && (
        <span className="ml-1 rounded-full bg-slate-200 px-1.5 py-0.5 text-[10px] font-semibold text-slate-700">{pendingCount}</span>
      )}
    </div>
  );
}
