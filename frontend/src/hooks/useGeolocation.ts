import { useCallback, useState } from "react";

export interface LocationResult {
  latitude: number;
  longitude: number;
  accuracy: number;
  timestamp: number;
}

export function useGeolocation() {
  const [location, setLocation] = useState<LocationResult | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "denied" | "error">("idle");

  const capture = useCallback(() => {
    if (!("geolocation" in navigator)) {
      setStatus("error");
      return;
    }
    setStatus("loading");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
          timestamp: pos.timestamp,
        });
        setStatus("success");
      },
      (err) => {
        setStatus(err.code === err.PERMISSION_DENIED ? "denied" : "error");
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  }, []);

  const setManualLocation = useCallback((lat: number, lng: number) => {
    setLocation({ latitude: lat, longitude: lng, accuracy: 0, timestamp: Date.now() });
    setStatus("success");
  }, []);

  return { location, status, capture, setManualLocation };
}
