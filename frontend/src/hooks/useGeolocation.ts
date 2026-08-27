import { useCallback, useEffect, useRef, useState } from "react";

export interface LocationResult {
  latitude: number;
  longitude: number;
  accuracy: number;
  timestamp: number;
}

export type GeolocationStatus = "idle" | "loading" | "success" | "denied" | "error";

// Poor-accuracy threshold — the UI should warn, not pretend precision it
// doesn't have (see LocationStep.tsx / NearbyIssuesPage.tsx).
export const POOR_ACCURACY_METERS = 500;

const HIGH_ACCURACY_OPTIONS: PositionOptions = { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 };
const LOW_ACCURACY_OPTIONS: PositionOptions = { enableHighAccuracy: false, timeout: 10000, maximumAge: 60000 };

// Last successful fix this browser tab has seen, offered as an explicit,
// clearly-labeled fallback if a later capture fails — never used silently
// in place of a real attempt, and never a hardcoded/default city
// coordinate.
let lastKnownLocation: LocationResult | null = null;

function getPosition(options: PositionOptions): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, options);
  });
}

/**
 * Single shared location service for every citizen GPS flow (report
 * wizard's LocationStep, NearbyIssuesPage). One high-accuracy attempt,
 * then one low-accuracy retry before giving up — GPS/WiFi positioning is
 * inherently flaky, especially on desktop or indoors, so a single strict
 * attempt was the main cause of "location capture sometimes fails".
 */
export function useGeolocation() {
  const [location, setLocation] = useState<LocationResult | null>(null);
  const [status, setStatus] = useState<GeolocationStatus>("idle");
  const capturingRef = useRef(false);

  // Pre-check permission state where supported, purely to avoid an
  // unnecessary prompt/attempt when we already know it's denied — the
  // browser itself never re-prompts once denied, so this cannot cause
  // repeated prompts either way.
  useEffect(() => {
    if (!("permissions" in navigator)) return;
    navigator.permissions
      ?.query({ name: "geolocation" as PermissionName })
      .then((result) => {
        if (result.state === "denied") setStatus("denied");
      })
      .catch(() => {
        // Permissions API not supported for this query in this browser —
        // fall through silently, getCurrentPosition still works normally.
      });
  }, []);

  const capture = useCallback(async () => {
    if (capturingRef.current) return; // avoid overlapping attempts
    if (!("geolocation" in navigator)) {
      setStatus("error");
      return;
    }
    capturingRef.current = true;
    setStatus("loading");

    try {
      let pos: GeolocationPosition;
      try {
        pos = await getPosition(HIGH_ACCURACY_OPTIONS);
      } catch (firstErr: any) {
        if (firstErr?.code === firstErr?.PERMISSION_DENIED) {
          setStatus("denied");
          return;
        }
        // Timeout or position-unavailable on the strict attempt -> retry
        // once with a more forgiving, lower-accuracy configuration.
        pos = await getPosition(LOW_ACCURACY_OPTIONS);
      }

      const result: LocationResult = {
        latitude: pos.coords.latitude,
        longitude: pos.coords.longitude,
        accuracy: pos.coords.accuracy,
        timestamp: pos.timestamp,
      };
      lastKnownLocation = result;
      setLocation(result);
      setStatus("success");
    } catch (err: any) {
      if (err?.code === err?.PERMISSION_DENIED) {
        setStatus("denied");
      } else {
        setStatus("error");
      }
    } finally {
      capturingRef.current = false;
    }
  }, []);

  const setManualLocation = useCallback((lat: number, lng: number) => {
    const result: LocationResult = { latitude: lat, longitude: lng, accuracy: 0, timestamp: Date.now() };
    lastKnownLocation = result;
    setLocation(result);
    setStatus("success");
  }, []);

  const useLastKnownLocation = useCallback(() => {
    if (!lastKnownLocation) return false;
    setLocation(lastKnownLocation);
    setStatus("success");
    return true;
  }, []);

  return {
    location,
    status,
    capture,
    setManualLocation,
    lastKnownLocation,
    useLastKnownLocation,
    isPoorAccuracy: location != null && location.accuracy > POOR_ACCURACY_METERS,
  };
}
