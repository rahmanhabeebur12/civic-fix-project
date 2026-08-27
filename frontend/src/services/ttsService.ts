/**
 * ttsService.ts
 *
 * Provider-independent text-to-speech for voice guidance.
 *
 * Tries the backend-proxied ElevenLabs endpoint first (only when online —
 * it needs the network either way), and falls back to the browser's own
 * window.speechSynthesis on ANY failure: network error, backend not
 * configured (TTS_PROVIDER=browser), timeout, or non-2xx response. The
 * backend never hands the frontend an ElevenLabs API key — this service
 * only ever sends plain text and receives back audio bytes or nothing.
 *
 * Cost/rate control on the frontend side: identical in-flight requests
 * for the same sentence are shared rather than duplicated, and the
 * backend itself caches generated audio per sentence for the process
 * lifetime (see app/services/tts_service.py).
 */
import { api } from "@/services/api";

// Voice guidance is English-only (see hooks/useVoiceGuidance.ts) —
// regardless of the citizen's selected UI language, spoken guidance and
// speech input both always use this locale.
const TTS_LOCALE = "en-IN";
const BACKEND_TTS_TIMEOUT_MS = 6000;
const VOICES_READY_TIMEOUT_MS = 1000;

let currentAudio: HTMLAudioElement | null = null;
const pendingBackendRequests = new Map<string, Promise<Blob | null>>();
let voicesReadyPromise: Promise<SpeechSynthesisVoice[]> | null = null;

function stopBrowserSpeech() {
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

function stopBackendAudio() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio.src = "";
    currentAudio = null;
  }
}

/** Stops any voice guidance currently playing, from either source. */
export function stop(): void {
  stopBackendAudio();
  stopBrowserSpeech();
}

export function isBrowserTTSSupported(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/**
 * Many browsers (notably Chrome) load their voice list asynchronously —
 * the very first getVoices() call right after page load can return an
 * empty array even though voices are on their way. Wait once for the
 * voiceschanged event, bounded by a short timeout, so a guidance sentence
 * spoken early in the session still gets a real voice.
 */
function waitForVoices(): Promise<SpeechSynthesisVoice[]> {
  if (!isBrowserTTSSupported()) return Promise.resolve([]);
  const synth = window.speechSynthesis;
  const existing = synth.getVoices();
  if (existing.length) return Promise.resolve(existing);

  if (!voicesReadyPromise) {
    voicesReadyPromise = new Promise((resolve) => {
      const timer = setTimeout(() => resolve(synth.getVoices()), VOICES_READY_TIMEOUT_MS);
      const onReady = () => {
        clearTimeout(timer);
        resolve(synth.getVoices());
      };
      if (typeof synth.addEventListener === "function") {
        synth.addEventListener("voiceschanged", onReady, { once: true });
      } else {
        synth.onvoiceschanged = onReady;
      }
    });
  }
  return voicesReadyPromise;
}

async function pickBrowserVoice(): Promise<SpeechSynthesisVoice | null> {
  if (!isBrowserTTSSupported()) return null;
  const voices = await waitForVoices();
  if (!voices.length) return null;

  const exact = voices.find((v) => v.lang === TTS_LOCALE);
  if (exact) return exact;

  const prefixMatch = voices.find((v) => v.lang?.toLowerCase().startsWith("en"));
  if (prefixMatch) return prefixMatch;

  return voices[0];
}

async function speakWithBrowser(text: string): Promise<boolean> {
  if (!isBrowserTTSSupported() || !text.trim()) return false;
  stopBrowserSpeech();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = TTS_LOCALE;
  const voice = await pickBrowserVoice();
  if (voice) utterance.voice = voice;
  window.speechSynthesis.speak(utterance);
  return true;
}

async function fetchBackendAudio(text: string): Promise<Blob | null> {
  const key = text.trim();
  if (!key) return null;

  const existing = pendingBackendRequests.get(key);
  if (existing) return existing;

  const request = (async () => {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), BACKEND_TTS_TIMEOUT_MS);
      const res = await fetch(`${api.base}/accessibility/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: key }),
        signal: controller.signal,
      });
      clearTimeout(timer);
      if (!res.ok) return null;
      return await res.blob();
    } catch {
      // Network error, timeout, offline, backend not configured — any
      // failure here just means "use the browser instead".
      return null;
    } finally {
      pendingBackendRequests.delete(key);
    }
  })();

  pendingBackendRequests.set(key, request);
  return request;
}

/**
 * Speaks `text` aloud (always in English — see TTS_LOCALE). Tries the
 * backend (ElevenLabs) first when online, then always falls back to the
 * browser's speechSynthesis. Never throws — a failure on both sides simply
 * means nothing is spoken.
 */
export async function speak(text: string): Promise<void> {
  const trimmed = (text || "").trim();
  if (!trimmed) return;
  stop();

  if (typeof navigator !== "undefined" && navigator.onLine) {
    const blob = await fetchBackendAudio(trimmed);
    if (blob && blob.size > 0) {
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      currentAudio = audio;
      audio.addEventListener("ended", () => URL.revokeObjectURL(url), { once: true });
      try {
        await audio.play();
        return;
      } catch {
        URL.revokeObjectURL(url);
        currentAudio = null;
        // fall through to browser TTS
      }
    }
  }

  await speakWithBrowser(trimmed);
}
