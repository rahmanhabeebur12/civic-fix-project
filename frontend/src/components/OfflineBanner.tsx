import { useConnectivity } from "@/hooks/useConnectivity";
import { useTranslation } from "@/hooks/useTranslation";

export function OfflineBanner() {
  const { isOnline } = useConnectivity();
  const { t } = useTranslation();

  if (isOnline) return null;

  return (
    <div className="mb-4 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      <p className="font-semibold">📴 {t.offline}</p>
      <p className="mt-1">{t.offlineBanner}</p>
    </div>
  );
}
