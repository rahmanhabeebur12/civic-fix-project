import { useEffect } from "react";

/**
 * Lightweight refetch-on-focus for citizen tracking pages — the backend
 * status is the source of truth, so a citizen reopening/refocusing Track
 * Report or My Reports should see the latest persisted status rather
 * than whatever was fetched on the previous visit. Deliberately not
 * WebSockets/polling — just a refetch when the tab becomes relevant
 * again, which is enough for a citizen checking back on a report.
 */
export function useRevalidateOnFocus(callback: () => void) {
  useEffect(() => {
    function handleVisibility() {
      if (document.visibilityState === "visible") callback();
    }
    window.addEventListener("focus", callback);
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.removeEventListener("focus", callback);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [callback]);
}
