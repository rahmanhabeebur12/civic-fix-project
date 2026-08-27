import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAppStore } from "@/store/appStore";

export function RequireStaffAuth({ children }: { children: ReactNode }) {
  const staffToken = useAppStore((s) => s.staffToken);
  if (!staffToken) return <Navigate to="/staff/login" replace />;
  return <>{children}</>;
}
