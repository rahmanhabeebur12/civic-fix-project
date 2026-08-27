import { CitizenLayout } from "@/components/CitizenLayout";
import { useTranslation } from "@/hooks/useTranslation";
import { PendingReportsList } from "@/features/offline/PendingReportsList";

export default function PendingReportsPage() {
  const { t } = useTranslation();
  return (
    <CitizenLayout showBack>
      <h1 className="mb-4 text-xl font-bold text-slate-800">{t.pendingReports}</h1>
      <PendingReportsList />
    </CitizenLayout>
  );
}
