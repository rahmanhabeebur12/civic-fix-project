import { useCallback, useEffect, useRef, useState } from "react";
import * as ttsService from "@/services/ttsService";

const STORAGE_KEY = "civicfix:voice-guidance-enabled";

function readStoredPreference(): boolean {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw === null ? true : raw === "true";
  } catch {
    return true;
  }
}

/**
 * Spoken step guidance for the citizen report wizard. Voice guidance is
 * optional and off-page (home/tracking/etc never call this) — it only
 * ever speaks when a wizard step explicitly asks it to, and only while
 * the citizen's ON/OFF preference (remembered in localStorage) is on.
 * Guidance is always spoken in English (see ttsService.ts), independent
 * of the citizen's selected UI language.
 */
export function useVoiceGuidance() {
  const [enabled, setEnabledState] = useState<boolean>(readStoredPreference);
  const lastTextRef = useRef<string>("");

  const setEnabled = useCallback((value: boolean) => {
    setEnabledState(value);
    try {
      localStorage.setItem(STORAGE_KEY, String(value));
    } catch {
      // localStorage unavailable (private mode etc.) — preference just
      // won't persist across sessions; guidance still works this session.
    }
    if (!value) ttsService.stop();
  }, []);

  const speak = useCallback(
    (text: string) => {
      lastTextRef.current = text;
      if (!enabled || !text.trim()) return;
      void ttsService.speak(text);
    },
    [enabled]
  );

  const replay = useCallback(() => {
    if (lastTextRef.current.trim()) void ttsService.speak(lastTextRef.current);
  }, []);

  useEffect(() => {
    return () => ttsService.stop();
  }, []);

  return { enabled, setEnabled, speak, replay };
}
