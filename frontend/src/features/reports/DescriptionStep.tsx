import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "@/hooks/useTranslation";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";

export function DescriptionStep({
  description,
  hasPhoto,
  onDescriptionChange,
  onVoiceResult,
  onNext,
  onBack,
}: {
  description: string;
  hasPhoto: boolean;
  onDescriptionChange: (v: string) => void;
  /** Called when the citizen accepts a voice transcript — flags the
   * description as voice-sourced for analytics only; the text itself
   * still flows through onDescriptionChange like any typed text. */
  onVoiceResult: (v: string) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const { t } = useTranslation();
  const [error, setError] = useState<string | null>(null);
  const [pendingTranscript, setPendingTranscript] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  const handleTranscript = useCallback((text: string) => {
    setPendingTranscript(text);
  }, []);

  const { supported, state, errorReason, start, stop, reset } = useSpeechRecognition(handleTranscript);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const goOnline = () => setIsOnline(true);
    const goOffline = () => setIsOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  // Accessibility: a description is only mandatory here when no photo was
  // provided in the previous step — a citizen who already has a photo can
  // skip this entirely (photo-only submission is accepted by the backend).
  function handleNext() {
    if (!hasPhoto && description.trim().length < 3) {
      setError(t.descriptionRequired);
      return;
    }
    setError(null);
    onNext();
  }

  function acceptTranscript(focusForEdit: boolean) {
    if (pendingTranscript == null) return;
    const merged = (description ? description + " " : "") + pendingTranscript;
    onVoiceResult(merged);
    setPendingTranscript(null);
    reset();
    if (focusForEdit) {
      // Let the field render with the new value before focusing it.
      setTimeout(() => textareaRef.current?.focus(), 0);
    }
  }

  function discardAndListenAgain() {
    setPendingTranscript(null);
    reset();
    start();
  }

  const micLabel =
    state === "listening" ? t.micListening : state === "processing" ? t.micWorking : state === "error" ? t.micTryAgain : t.speak;

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-xl font-bold text-navy-800">{t.describeProblem}</h2>
      <p className="text-sm text-slate-500">{t.describeHint}</p>

      <textarea
        ref={textareaRef}
        className="input-field min-h-[120px] resize-none"
        value={description}
        onChange={(e) => onDescriptionChange(e.target.value)}
        placeholder={t.describeProblem}
        autoFocus
      />

      {/* Voice input: never submitted blindly — the citizen must accept the
          recognized text (or edit/retry it) before it becomes the description. */}
      {pendingTranscript !== null ? (
        <div className="rounded-xl border border-brand-200 bg-brand-50 p-3">
          <p className="mb-2 text-sm text-slate-700">
            <span className="font-semibold">{t.youSaid}</span> “{pendingTranscript}”
          </p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="tap-target rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700" onClick={() => acceptTranscript(true)}>
              {t.editText}
            </button>
            <button type="button" className="tap-target rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700" onClick={discardAndListenAgain}>
              🎤 {t.speakAgain}
            </button>
            <button type="button" className="tap-target rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white" onClick={() => acceptTranscript(false)}>
              {t.next}
            </button>
          </div>
        </div>
      ) : supported && isOnline ? (
        <button
          type="button"
          onClick={state === "listening" ? stop : state === "processing" ? undefined : start}
          disabled={state === "processing"}
          className={`tap-target flex items-center justify-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold ${
            state === "listening"
              ? "border-red-300 bg-red-50 text-red-700 animate-pulse"
              : state === "error"
                ? "border-amber-300 bg-amber-50 text-amber-700"
                : "border-slate-300 bg-white text-slate-700"
          }`}
        >
          🎤 {micLabel}
        </button>
      ) : (
        <p className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-500">
          {!supported ? t.voiceNotSupported : t.voiceUnavailableOffline}
        </p>
      )}

      {errorReason === "no-speech" && pendingTranscript === null && (
        <p className="text-sm text-amber-700">{t.micDidNotCatch}</p>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {hasPhoto && !description.trim() && pendingTranscript === null && (
        <div className="text-center">
          <p className="mb-1 text-xs text-slate-400">{t.skipDescriptionHint}</p>
          <button type="button" className="text-sm font-semibold text-brand-700 underline" onClick={handleNext}>
            {t.skipDescription}
          </button>
        </div>
      )}

      <div className="mt-4 flex gap-3">
        <button className="btn-secondary flex-1" onClick={onBack}>
          {t.back}
        </button>
        <button className="btn-primary flex-1" onClick={handleNext}>
          {t.next}
        </button>
      </div>
    </div>
  );
}
