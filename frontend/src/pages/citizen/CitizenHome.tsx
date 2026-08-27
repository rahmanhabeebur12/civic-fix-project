import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { CitizenLayout } from "@/components/CitizenLayout";
import { useTranslation } from "@/hooks/useTranslation";
import { useAppStore } from "@/store/appStore";
import { OfflineBanner } from "@/components/OfflineBanner";
import { OnboardingGuide, hasSeenOnboarding } from "@/components/OnboardingGuide";
import { getPendingReports } from "@/services/offlineReportService";

export default function CitizenHome() {
  const { t, language, setLanguage } = useTranslation();
  const [showOnboarding, setShowOnboarding] = useState(() => !hasSeenOnboarding());
  const citizenAuthIdentity = useAppStore((s) => s.citizenAuthIdentity);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    getPendingReports().then((r) => setPendingCount(r.length)).catch(() => {});
  }, []);

  const loggedIn = !!citizenAuthIdentity;

  return (
    <CitizenLayout>
      {showOnboarding && <OnboardingGuide onDone={() => setShowOnboarding(false)} />}
      <OfflineBanner />

      <div className="mb-6 mt-2 text-center">
        {loggedIn ? (
          <>
            <p className="text-xl font-bold text-navy-800">{t.helloName}, {citizenAuthIdentity!.name.split(" ")[0]}</p>
            <p className="mt-1 text-sm text-slate-500">{t.whatWouldYouLikeToDo}</p>
          </>
        ) : (
          <>
            <p className="text-lg font-medium text-slate-500">{t.homeGreeting}</p>
            <p className="mt-1 text-sm text-slate-400">{t.tagline}</p>
          </>
        )}
      </div>

      {!loggedIn && (
        <Link
          to="/login"
          className="mb-5 flex items-center justify-between rounded-2xl border border-navy-200 bg-navy-50 px-4 py-3 text-sm font-semibold text-navy-800 shadow-sm"
        >
          <span>👋 {t.loginWelcomeBack} / {t.createAccount}</span>
          <span>→</span>
        </Link>
      )}

      {/* Primary action */}
      <Link
        to="/report"
        className="tap-target flex items-center gap-4 rounded-2xl bg-navy-800 px-5 py-5 text-white shadow-md transition hover:bg-navy-900"
      >
        <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white/15 text-2xl">📷</span>
        <span className="text-left">
          <span className="block text-lg font-bold">{t.homeReportIssue}</span>
          <span className="block text-sm text-white/80">{t.homeReportIssueHint}</span>
        </span>
      </Link>
      <Link to="/report?assisted=1" className="mt-2 block text-center text-xs font-semibold text-brand-700 underline">
        {t.needHelpReporting} {t.useAssistedMode}
      </Link>

      {/* Secondary actions */}
      <div className="mt-4 grid grid-cols-2 gap-3">
        <HomeCard to="/my-reports" icon="📋" title={t.homeTrackReports} hint={t.homeMyReportsHint} />
        <HomeCard to="/nearby-issues" icon="📍" title={t.homeNearbyIssues} hint={t.homeNearbyIssuesHint} />
        <HomeCard to="/track" icon="🔍" title={t.track} hint={t.homeTrackReportHint} />
        <HomeCard to="/pending-reports" icon="⏳" title={t.pendingReports} hint={t.homeOfflineReportsHint} badge={pendingCount || undefined} />
        {loggedIn && <HomeCard to="/profile" icon="👤" title={t.profileTitle} hint={t.homeProfileHint} />}
      </div>

      <div className="mt-8">
        <p className="mb-2 text-center text-sm font-medium text-slate-500">{t.selectLanguage}</p>
        <div className="flex justify-center gap-3">
          <button
            onClick={() => setLanguage("en")}
            className={`tap-target rounded-xl border px-5 py-2 text-base font-semibold ${
              language === "en" ? "border-brand-600 bg-brand-50 text-brand-700" : "border-slate-300 bg-white text-slate-600"
            }`}
          >
            {t.english}
          </button>
          <button
            onClick={() => setLanguage("ta")}
            className={`tap-target rounded-xl border px-5 py-2 text-base font-semibold ${
              language === "ta" ? "border-brand-600 bg-brand-50 text-brand-700" : "border-slate-300 bg-white text-slate-600"
            }`}
          >
            {t.tamil}
          </button>
        </div>
      </div>

      <div className="mt-8 flex flex-col items-center gap-2 text-center">
        <button onClick={() => setShowOnboarding(true)} className="text-xs text-slate-400 underline">
          {language === "ta" ? "இது எப்படி வேலை செய்கிறது?" : "How does this work?"}
        </button>
        {loggedIn && (
          <Link to="/profile" className="text-xs text-slate-400 underline">
            {citizenAuthIdentity!.name} · {t.profileTitle}
          </Link>
        )}
        <Link to="/staff/login" className="text-xs text-slate-400 underline">
          Municipal Staff Login
        </Link>
      </div>
    </CitizenLayout>
  );
}

function HomeCard({ to, icon, title, hint, badge }: { to: string; icon: string; title: string; hint: string; badge?: number }) {
  return (
    <Link
      to={to}
      className="tap-target relative flex flex-col items-start gap-1.5 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-brand-300 hover:shadow-md"
    >
      {badge != null && (
        <span className="absolute right-3 top-3 flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-500 px-1 text-[11px] font-bold text-white">
          {badge}
        </span>
      )}
      <span className="text-2xl">{icon}</span>
      <span className="text-sm font-bold text-navy-800">{title}</span>
      <span className="text-xs leading-snug text-slate-500">{hint}</span>
    </Link>
  );
}
