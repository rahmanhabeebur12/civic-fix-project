import { Link } from "react-router-dom";
import { CitizenLayout } from "@/components/CitizenLayout";
import { useTranslation } from "@/hooks/useTranslation";

export default function ReportSavedOffline() {
  const { t } = useTranslation();

  return (
    <CitizenLayout>
      <div className="flex flex-col items-center text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-amber-100 text-4xl">📥</div>
        <h1 className="mt-4 text-xl font-bold text-slate-800">{t.savedOfflineTitle}</h1>
        <p className="mt-2 text-sm text-slate-600">{t.savedOfflineBody}</p>
        <p className="mt-3 rounded-full bg-amber-50 px-4 py-1.5 text-sm font-medium text-amber-800">{t.savedOfflineStatus}</p>

        <Link to="/pending-reports" className="btn-primary mt-6 w-full">
          {t.pendingReports}
        </Link>
        <Link to="/" className="btn-secondary mt-3 w-full">
          {t.appName}
        </Link>
      </div>
    </CitizenLayout>
  );
}
