import { useRef, useState } from "react";
import { useTranslation } from "@/hooks/useTranslation";

const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/jpg"];
const MAX_SIZE_MB = 8;

export function PhotoStep({
  photo,
  onPhotoSelected,
  onNext,
  onBack,
}: {
  photo: File | null;
  onPhotoSelected: (file: File | null) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const previewUrl = photo ? URL.createObjectURL(photo) : null;

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!ALLOWED_TYPES.includes(file.type)) {
      setError(t.errorInvalidFile);
      return;
    }
    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`Image must be smaller than ${MAX_SIZE_MB}MB.`);
      return;
    }
    setError(null);
    onPhotoSelected(file);
  }

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-bold text-navy-800">{t.photoStepTitle}</h2>

      {previewUrl ? (
        <div className="overflow-hidden rounded-2xl border border-slate-200">
          <img src={previewUrl} alt="Preview" className="h-64 w-full object-cover" />
        </div>
      ) : (
        <div className="flex h-64 items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 text-slate-400">
          No photo yet
        </div>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      <input ref={cameraInputRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={handleFile} />
      <input ref={uploadInputRef} type="file" accept="image/*" className="hidden" onChange={handleFile} />

      <div className="flex gap-3">
        <button className="btn-secondary flex-1" onClick={() => cameraInputRef.current?.click()}>
          📷 {photo ? t.retakePhoto : t.takePhoto}
        </button>
        <button className="btn-secondary flex-1" onClick={() => uploadInputRef.current?.click()}>
          🖼️ {t.uploadPhoto}
        </button>
      </div>

      {!photo && (
        <div className="text-center">
          <p className="mb-1 text-xs text-slate-400">{t.skipPhotoHint}</p>
          <button type="button" className="text-sm font-semibold text-brand-700 underline" onClick={onNext}>
            {t.skipPhoto}
          </button>
        </div>
      )}

      <div className="mt-4 flex gap-3">
        <button className="btn-secondary flex-1" onClick={onBack}>
          {t.back}
        </button>
        <button className="btn-primary flex-1" onClick={onNext}>
          {t.next}
        </button>
      </div>
    </div>
  );
}
