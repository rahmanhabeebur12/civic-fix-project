import { useTranslation } from "@/hooks/useTranslation";
import type { LocationResult } from "@/hooks/useGeolocation";

export function ReviewStep({
  photo,
  description,
  location,
  submitting,
  submitLabel,
  onSubmit,
  onBack,
}: {
  photo: File | null;
  description: string;
  location: LocationResult | null;
  submitting: boolean;
  submitLabel?: string;
  onSubmit: () => void;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const previewUrl = photo ? URL.createObjectURL(photo) : null;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-bold text-navy-800">{t.reviewYourReport}</h2>

      {previewUrl && (
        <div className="overflow-hidden rounded-2xl border border-slate-200">
          <img src={previewUrl} alt="Report" className="h-56 w-full object-cover" />
        </div>
      )}

      <div className="card">
        <p className="text-xs font-semibold uppercase text-slate-400">{t.stepDescription}</p>
        <p className="mt-1 text-slate-800">{description || "—"}</p>
      </div>

      <div className="card">
        <p className="text-xs font-semibold uppercase text-slate-400">{t.stepLocation}</p>
        <p className="mt-1 text-slate-800">
          {location ? `${location.latitude.toFixed(5)}, ${location.longitude.toFixed(5)}` : "—"}
        </p>
      </div>

      <div className="mt-4 flex gap-3">
        <button className="btn-secondary flex-1" disabled={submitting} onClick={onBack}>
          {t.back}
        </button>
        <button className="btn-primary flex-1" disabled={submitting} onClick={onSubmit}>
          {submitting ? (submitLabel || t.submitting) : t.submitReport}
        </button>
      </div>
    </div>
  );
}
