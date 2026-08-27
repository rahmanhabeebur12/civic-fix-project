import { useState } from "react";
import { useTranslation } from "@/hooks/useTranslation";

const STORAGE_KEY = "civicfix:onboarding-seen";

const STEPS = [
  { emoji: "📷", en: "Take a photo of the problem", ta: "பிரச்சனையின் புகைப்படத்தை எடுக்கவும்" },
  { emoji: "🎤", en: "Speak or type what's wrong", ta: "என்ன தவறு என்று பேசுங்கள் அல்லது தட்டச்சு செய்யுங்கள்" },
  { emoji: "📍", en: "Your location is captured automatically", ta: "உங்கள் இடம் தானாக பதிவு செய்யப்படும்" },
  { emoji: "✅", en: "Review what you've entered", ta: "நீங்கள் உள்ளிட்டதை மறுபரிசீலனை செய்யவும்" },
  { emoji: "🚀", en: "Submit — that's it!", ta: "சமர்ப்பிக்கவும் — முடிந்தது!" },
];

export function hasSeenOnboarding(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) === "true";
  } catch {
    return true; // if storage is unavailable, don't force it on every visit
  }
}

function markOnboardingSeen() {
  try {
    localStorage.setItem(STORAGE_KEY, "true");
  } catch {
    // best-effort only
  }
}

/**
 * Lightweight first-time visual guide for low-digital-literacy users.
 * No heavy media/AI video — a simple animated step illustration built
 * from plain CSS + emoji, so it can never fail to load. Never blocks
 * reporting: Skip is always one tap away, and there is no autoplay sound.
 */
export function OnboardingGuide({ onDone }: { onDone: () => void }) {
  const { language } = useTranslation();
  const [step, setStep] = useState(0);
  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;

  function finish() {
    markOnboardingSeen();
    onDone();
  }

  function next() {
    if (isLast) finish();
    else setStep((s) => s + 1);
  }

  function replay() {
    setStep(0);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4">
      <div className="w-full max-w-sm rounded-3xl bg-white p-6 text-center shadow-xl">
        <div key={step} className="onboarding-step-anim flex h-40 items-center justify-center text-7xl">
          {current.emoji}
        </div>
        <p className="mt-4 text-lg font-semibold text-slate-800">{language === "ta" ? current.ta : current.en}</p>

        <div className="mt-5 flex justify-center gap-1.5">
          {STEPS.map((_, i) => (
            <span key={i} className={`h-1.5 w-6 rounded-full ${i === step ? "bg-brand-600" : "bg-slate-200"}`} />
          ))}
        </div>

        <div className="mt-6 flex gap-3">
          <button className="btn-secondary flex-1" onClick={finish}>
            {language === "ta" ? "தவிர்" : "Skip"}
          </button>
          <button className="btn-primary flex-1" onClick={next}>
            {isLast ? (language === "ta" ? "தொடங்குங்கள்" : "Get Started") : language === "ta" ? "அடுத்து" : "Next"}
          </button>
        </div>

        {isLast && (
          <button className="mt-3 text-xs font-semibold text-brand-700 underline" onClick={replay}>
            {language === "ta" ? "மீண்டும் காட்டு" : "Replay"}
          </button>
        )}
      </div>

      <style>{`
        .onboarding-step-anim {
          animation: onboarding-pop 0.35s ease-out;
        }
        @keyframes onboarding-pop {
          0% { transform: scale(0.6); opacity: 0; }
          100% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
}
