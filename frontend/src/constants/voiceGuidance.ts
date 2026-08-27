/**
 * Spoken step-guidance sentences for the citizen report wizard.
 *
 * Voice guidance is English-only regardless of the selected UI language
 * (see hooks/useVoiceGuidance.ts) — these sentences are never displayed as
 * text, only spoken, so they live outside the bilingual i18n dictionary
 * rather than as translated keys.
 */
export const VOICE_GUIDANCE_EN = {
  languageStep: "Choose the language you'd like to use.",
  photoStep: "Take or upload a photo of the problem. If you can't add a photo, you can describe it instead.",
  descriptionStep: "Now describe the problem. You can type it, or tap the microphone and speak instead.",
  locationStep: "Your location has been captured.",
  reviewStep: "Please review your report before sending it.",
  submitStep: "Submit your report.",
  successStep: "Your report has been submitted successfully.",
};
