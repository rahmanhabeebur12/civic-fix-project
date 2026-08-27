import { useCallback, useEffect, useRef, useState } from "react";
import {
  isSpeechRecognitionSupported,
  startListening,
  type SpeechRecognitionSession,
  type SpeechRecognitionState,
} from "@/services/speechRecognitionService";

/**
 * React state machine around speechRecognitionService. Speech input is
 * English-only (see speechRecognitionService.ts). The resulting text is
 * handed back via onResult exactly like typed input — callers must still
 * let the citizen review/edit it before it's treated as the report
 * description (see DescriptionStep.tsx).
 */
export function useSpeechRecognition(onResult: (text: string) => void) {
  const [state, setState] = useState<SpeechRecognitionState>("idle");
  const [errorReason, setErrorReason] = useState<"no-speech" | "not-allowed" | "network" | "other" | null>(null);
  const sessionRef = useRef<SpeechRecognitionSession | null>(null);
  const supported = isSpeechRecognitionSupported();

  const start = useCallback(() => {
    if (!supported) return;
    setErrorReason(null);
    const session = startListening({
      onStateChange: setState,
      onResult,
      onError: setErrorReason,
    });
    sessionRef.current = session;
    if (!session) setState("error");
  }, [onResult, supported]);

  const stop = useCallback(() => {
    sessionRef.current?.stop();
  }, []);

  const reset = useCallback(() => {
    setState("idle");
    setErrorReason(null);
  }, []);

  useEffect(() => {
    return () => sessionRef.current?.stop();
  }, []);

  return { supported, state, errorReason, start, stop, reset };
}
