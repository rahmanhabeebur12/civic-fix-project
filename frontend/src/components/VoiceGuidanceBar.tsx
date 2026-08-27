import { useTranslation } from "@/hooks/useTranslation";
import type { Language } from "@/types";

/**
 * ON/OFF + replay control for spoken step guidance in the report wizard.
 * Large touch targets, high contrast, plain language — no mention of
 * "TTS" or "speech synthesis" anywhere in the UI.
 *
 * Voice guidance is English-only. When the citizen's UI language is
 * Tamil, the Tamil UI text is untouched — only a small note explains that
 * spoken guidance itself is still in English.
 */
export function VoiceGuidanceBar({
  enabled,
  onToggle,
  onReplay,
  uiLanguage,
}: {
  enabled: boolean;
  onToggle: (value: boolean) => void;
  onReplay: () => void;
  uiLanguage: Language;
}) {
  const { t } = useTranslation();

  return (
    <div className="mb-4 flex flex-col gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => onToggle(!enabled)}
          aria-pressed={enabled}
          className={`tap-target rounded-lg px-3 py-2 text-sm font-semibold ${
            enabled ? "bg-brand-600 text-white" : "bg-white text-slate-600 border border-slate-300"
          }`}
        >
          {enabled ? `🔊 ${t.voiceGuidanceOn}` : `🔇 ${t.voiceGuidanceOff}`}
        </button>

        {enabled && (
          <button
            type="button"
            onClick={onReplay}
            className="tap-target rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700"
          >
            🔁 {t.hearInstruction}
          </button>
        )}
      </div>

      {enabled && uiLanguage === "ta" && <p className="text-xs text-slate-400">{t.voiceGuidanceEnglishOnlyNote}</p>}
    </div>
  );
}
