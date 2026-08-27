import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CitizenLayout } from "@/components/CitizenLayout";
import { Spinner } from "@/components/Spinner";
import { useTranslation } from "@/hooks/useTranslation";
import { useAppStore } from "@/store/appStore";
import { api } from "@/services/api";
import type { CitizenProfile } from "@/types";

const RELIABILITY_STYLE: Record<string, string> = {
  NEW: "bg-slate-100 text-slate-600",
  BUILDING: "bg-amber-100 text-amber-800",
  TRUSTED: "bg-green-100 text-green-800",
};

export default function ProfilePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const citizenToken = useAppStore((s) => s.citizenToken);
  const clearCitizenAuth = useAppStore((s) => s.clearCitizenAuth);

  const [profile, setProfile] = useState<CitizenProfile | null>(null);

  useEffect(() => {
    if (!citizenToken) {
      navigate("/login", { replace: true });
      return;
    }
    api.citizenProfile().then(setProfile).catch(() => navigate("/login", { replace: true }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [citizenToken]);

  function handleLogout() {
    clearCitizenAuth();
    navigate("/");
  }

  const reliabilityLabel = profile
    ? profile.reliability_label === "TRUSTED"
      ? t.reliabilityTrusted
      : profile.reliability_label === "BUILDING"
        ? t.reliabilityBuilding
        : t.reliabilityNew
    : "";

  return (
    <CitizenLayout showBack>
      <h1 className="mb-5 text-xl font-bold text-navy-800">{t.profileTitle}</h1>

      {!profile ? (
        <Spinner label="…" />
      ) : (
        <>
          <div className="rounded-2xl border border-slate-200 bg-white p-5 text-center shadow-sm">
            <span className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-navy-700 text-2xl font-bold text-white">
              {profile.name.trim().charAt(0).toUpperCase() || "?"}
            </span>
            <p className="mt-3 text-lg font-bold text-slate-800">{profile.name}</p>
            <p className="text-sm text-slate-500">{profile.mobile}</p>
            <span className={`mt-3 inline-block rounded-full px-3 py-1 text-xs font-bold ${RELIABILITY_STYLE[profile.reliability_label]}`}>
              {reliabilityLabel}
            </span>
            <p className="mt-2 text-xs text-slate-400">{t.reliabilityNote}</p>
          </div>

          <div className="mt-4 grid grid-cols-3 gap-3">
            <StatCard value={profile.total_reports} label={t.myReportsCount} />
            <StatCard value={profile.resolved_reports} label={t.resolvedReportsCount} />
            <StatCard value={profile.supported_issues} label={t.supportedIssuesCount} />
          </div>

          <button className="btn-danger mt-8 w-full" onClick={handleLogout}>
            {t.logout}
          </button>
        </>
      )}
    </CitizenLayout>
  );
}

function StatCard({ value, label }: { value: number; label: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white py-4 text-center shadow-sm">
      <p className="text-2xl font-bold text-navy-700">{value}</p>
      <p className="mt-0.5 text-xs text-slate-500">{label}</p>
    </div>
  );
}
