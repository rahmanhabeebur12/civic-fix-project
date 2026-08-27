import { Link, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import { ConnectivityIndicator } from "@/components/ConnectivityIndicator";
import { useTranslation } from "@/hooks/useTranslation";

export function CitizenLayout({ children, showBack }: { children: ReactNode; showBack?: boolean }) {
  const { t } = useTranslation();
  const navigate = useNavigate();

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col bg-slate-50">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
        <div className="flex items-center gap-2">
          {showBack && (
            <button
              onClick={() => navigate(-1)}
              aria-label={t.back}
              className="tap-target flex items-center justify-center rounded-lg px-2 text-xl text-slate-600 hover:bg-slate-100"
            >
              ←
            </button>
          )}
          <Link to="/" className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-sm font-bold text-white">CF</span>
            <span className="text-lg font-bold text-brand-800">{t.appName}</span>
          </Link>
        </div>
        <ConnectivityIndicator />
      </header>
      <main className="flex-1 px-4 py-5">{children}</main>
    </div>
  );
}
