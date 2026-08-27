import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CitizenLayout } from "@/components/CitizenLayout";
import { useTranslation } from "@/hooks/useTranslation";
import { useAppStore } from "@/store/appStore";
import { api } from "@/services/api";
import type { NotificationItem } from "@/types";

export default function NotificationsPage() {
  const { t } = useTranslation();
  const citizen = useAppStore((s) => s.citizen);
  const [items, setItems] = useState<NotificationItem[] | null>(null);

  useEffect(() => {
    if (citizen?.mobile) {
      api.notifications(citizen.mobile).then(setItems).catch(() => setItems([]));
    } else {
      setItems([]);
    }
  }, [citizen]);

  return (
    <CitizenLayout showBack>
      <h1 className="mb-4 text-xl font-bold text-slate-800">{t.notifications}</h1>

      {items !== null && items.length === 0 && (
        <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-400">{t.noNotifications}</p>
      )}

      <div className="flex flex-col gap-3">
        {items?.map((n) => (
          <Link key={n.id} to={n.complaint_id ? `/track/${n.complaint_id}` : "#"} className="card">
            <p className="text-sm font-semibold text-slate-800">{n.title}</p>
            <p className="mt-1 text-sm text-slate-600">{n.message}</p>
            <p className="mt-2 text-xs text-slate-400">{new Date(n.created_at).toLocaleString()}</p>
          </Link>
        ))}
      </div>
    </CitizenLayout>
  );
}
