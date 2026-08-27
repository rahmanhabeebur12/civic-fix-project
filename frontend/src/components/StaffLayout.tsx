import { Link, useLocation, useNavigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAppStore } from "@/store/appStore";

const NAV = [
  { to: "/staff/dashboard", label: "Dashboard" },
  { to: "/staff/issues", label: "Issues" },
  { to: "/staff/review-queue", label: "Review Queue" },
  { to: "/staff/past-issues", label: "Past Issues" },
  { to: "/staff/analytics", label: "Analytics" },
];

export function StaffLayout({ children }: { children: ReactNode }) {
  const { staffProfile, clearStaffAuth } = useAppStore();
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <div className="flex min-h-screen bg-slate-100">
      <aside className="hidden w-56 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-4">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-600 text-sm font-bold text-white">CF</span>
          <span className="font-bold text-slate-800">CivicFix</span>
        </div>
        <nav className="flex flex-1 flex-col gap-1 p-3">
          {NAV.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className={`rounded-lg px-3 py-2 text-sm font-medium ${
                location.pathname.startsWith(item.to) ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-50"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="border-t border-slate-200 p-3">
          <p className="text-sm font-semibold text-slate-800">{staffProfile?.full_name}</p>
          <p className="text-xs text-slate-400">{staffProfile?.role} {staffProfile?.department ? `· ${staffProfile.department}` : ""}</p>
          <button
            className="mt-2 w-full rounded-lg border border-slate-200 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            onClick={() => {
              clearStaffAuth();
              navigate("/staff/login");
            }}
          >
            Log Out
          </button>
        </div>
      </aside>

      <div className="flex-1 overflow-x-hidden">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3 md:hidden">
          <span className="font-bold text-slate-800">CivicFix Staff</span>
          <button
            className="text-xs font-semibold text-slate-600"
            onClick={() => {
              clearStaffAuth();
              navigate("/staff/login");
            }}
          >
            Log Out
          </button>
        </header>
        <div className="mx-auto max-w-7xl px-4 py-6 md:px-8">{children}</div>
      </div>
    </div>
  );
}
