import { useEffect, useState } from "react";
import { useTranslation } from "@/hooks/useTranslation";
import { useGeolocation, type LocationResult } from "@/hooks/useGeolocation";

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
  const { location: captured, status, capture, setManualLocation } = useGeolocation();
  const [manualMode, setManualMode] = useState(false);
  const [manualLat, setManualLat] = useState("");
  const [manualLng, setManualLng] = useState("");

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

      {(status === "denied" || status === "error") && !manualMode && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <p>{t.locationDenied}</p>
          <div className="mt-2 flex gap-2">
            <button className="btn-secondary" onClick={capture}>
              {t.retryLocation}
            </button>
            <button className="btn-secondary" onClick={() => setManualMode(true)}>
              {t.enterLocationManually}
            </button>
          </div>
        </div>
      )}

      {manualMode && (
        <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">{t.latitude}</label>
            <input className="input-field" value={manualLat} onChange={(e) => setManualLat(e.target.value)} inputMode="decimal" />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">{t.longitude}</label>
            <input className="input-field" value={manualLng} onChange={(e) => setManualLng(e.target.value)} inputMode="decimal" />
          </div>
          <button
            className="btn-secondary"
            onClick={() => {
              const lat = parseFloat(manualLat);
              const lng = parseFloat(manualLng);
              if (!isNaN(lat) && !isNaN(lng)) setManualLocation(lat, lng);
            }}
          >
            {t.locationCaptured}
          </button>
        </div>
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
