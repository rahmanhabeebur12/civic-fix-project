import { useEffect, useState } from "react";
import { useTranslation } from "@/hooks/useTranslation";
import { useGeolocation, type LocationResult } from "@/hooks/useGeolocation";
import { LocationPickerMap } from "@/components/LocationPickerMap";

export function LocationStep({
  location,
  onLocationSet,
  onNext,
  onBack,
}: {
  location: LocationResult | null;
  onLocationSet: (loc: LocationResult) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const { location: captured, status, capture, setManualLocation, lastKnownLocation, useLastKnownLocation, isPoorAccuracy } = useGeolocation();
  const [showMapPicker, setShowMapPicker] = useState(false);

  // Reuse a location already captured earlier in this report session
  // instead of triggering GPS again unnecessarily.
  useEffect(() => {
    if (!location) capture();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (captured) onLocationSet(captured);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [captured]);

  const effectiveLocation = location;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-bold text-navy-800">{t.locationStepTitle}</h2>

      {status === "loading" && (
        <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3">
          <span className="h-4 w-4 animate-ping rounded-full bg-brand-500" />
          <span className="text-sm text-slate-600">{t.capturingLocation}</span>
        </div>
      )}

      {status === "success" && effectiveLocation && (
        <div className="rounded-xl border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-800">
          ✅ {t.locationCaptured}
          <div className="mt-1 text-xs text-green-700">
            {effectiveLocation.latitude.toFixed(5)}, {effectiveLocation.longitude.toFixed(5)} (±{Math.round(effectiveLocation.accuracy)}m)
          </div>
        </div>
      )}

      {status === "success" && isPoorAccuracy && !showMapPicker && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <p>{t.locationPoorAccuracy}</p>
          <div className="mt-2 flex gap-2">
            <button className="btn-secondary" onClick={capture}>{t.retryLocation}</button>
            <button className="btn-secondary" onClick={() => setShowMapPicker(true)}>{t.locationChooseOnMap}</button>
          </div>
        </div>
      )}

      {(status === "denied" || status === "error") && !showMapPicker && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <p>{status === "denied" ? t.locationDenied : t.locationUnableToGet}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <button className="btn-secondary" onClick={capture}>
              {t.retryLocation}
            </button>
            <button className="btn-secondary" onClick={() => setShowMapPicker(true)}>
              {t.locationChooseOnMap}
            </button>
            {lastKnownLocation && (
              <button className="btn-secondary" onClick={useLastKnownLocation}>
                {t.useLastKnownLocation}
              </button>
            )}
          </div>
        </div>
      )}

      {showMapPicker && (
        <LocationPickerMap
          initialCenter={effectiveLocation ? [effectiveLocation.latitude, effectiveLocation.longitude] : undefined}
          onConfirm={(lat, lng) => {
            setManualLocation(lat, lng);
            setShowMapPicker(false);
          }}
        />
      )}

      <div className="mt-4 flex gap-3">
        <button className="btn-secondary flex-1" onClick={onBack}>
          {t.back}
        </button>
        <button className="btn-primary flex-1" disabled={!effectiveLocation} onClick={onNext}>
          {t.next}
        </button>
      </div>
    </div>
  );
}
