/**
 * speechRecognitionService.ts
 *
 * Thin wrapper around the browser's native SpeechRecognition API (Web
 * Speech API). There is no server-side STT provider in CivicFix — speech-
 * to-text only ever runs in the citizen's own browser, and the resulting
 * text is treated exactly like typed text by the rest of the app (see
 * hooks/useSpeechRecognition.ts and features/reports/DescriptionStep.tsx).
 *
 * States: "idle" | "listening" | "processing" | "done" | "error"
 *
 * Speech input is English-only — regardless of the citizen's selected UI
 * language, the microphone always listens for en-IN. Typing remains
 * available in every supported UI language.
 */
const STT_LOCALE = "en-IN";

export type SpeechRecognitionState = "idle" | "listening" | "processing" | "done" | "error";

export function isSpeechRecognitionSupported(): boolean {
  if (typeof window === "undefined") return false;
  return !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);
}

interface StartOptions {
  onStateChange: (state: SpeechRecognitionState) => void;
  onResult: (transcript: string) => void;
  onError?: (reason: "no-speech" | "not-allowed" | "network" | "other") => void;
}

export interface SpeechRecognitionSession {
  stop: () => void;
}

/**
 * Starts one speech-recognition session. Returns a handle with `stop()`,
 * or null immediately if the browser doesn't support speech recognition
 * at all (callers should check isSpeechRecognitionSupported() first and
 * show a friendly fallback message instead of calling this).
 */
export function startListening(options: StartOptions): SpeechRecognitionSession | null {
  const Ctor = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
  if (!Ctor) return null;

  const recognition = new Ctor();
  recognition.lang = STT_LOCALE;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  // onend always fires last (after onresult/onerror, if either fired).
  // Track whether one of them already gave a terminal state so onend only
  // has to handle the "stopped with nothing captured yet" case.
  let settled = false;

  recognition.onstart = () => options.onStateChange("listening");

  // Some engines pause between "audio captured" and "result ready" —
  // reflect that as a distinct, simple "processing" state rather than
  // leaving the mic looking stuck in "listening".
  recognition.onspeechend = () => options.onStateChange("processing");
  recognition.onaudioend = () => options.onStateChange("processing");

  recognition.onresult = (event: any) => {
    const transcript = event.results?.[0]?.[0]?.transcript;
    settled = true;
    if (transcript && transcript.trim()) {
      options.onResult(transcript.trim());
      options.onStateChange("done");
    } else {
      options.onStateChange("error");
      options.onError?.("no-speech");
    }
  };

  recognition.onerror = (event: any) => {
    settled = true;
    options.onStateChange("error");
    const code = event?.error;
    if (code === "no-speech") options.onError?.("no-speech");
    else if (code === "not-allowed" || code === "service-not-allowed") options.onError?.("not-allowed");
    else if (code === "network") options.onError?.("network");
    else options.onError?.("other");
  };

  recognition.onend = () => {
    // If nothing else already moved us to "done"/"error", the session
    // just ended quietly (e.g. stopped by the citizen before speaking) —
    // go back to idle rather than leaving the UI stuck mid-state.
    if (!settled) options.onStateChange("idle");
  };

  try {
    recognition.start();
  } catch {
    options.onStateChange("error");
    options.onError?.("other");
    return null;
  }

  return {
    stop: () => {
      try {
        recognition.stop();
      } catch {
        // already stopped — nothing to do
      }
    },
  };
}
