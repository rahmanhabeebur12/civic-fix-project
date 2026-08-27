import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CitizenLayout } from "@/components/CitizenLayout";
import { VoiceGuidanceBar } from "@/components/VoiceGuidanceBar";
import { VOICE_GUIDANCE_EN } from "@/constants/voiceGuidance";
import { useTranslation } from "@/hooks/useTranslation";
import { useVoiceGuidance } from "@/hooks/useVoiceGuidance";
import { useAppStore } from "@/store/appStore";
import { IdentityStep } from "@/features/reports/IdentityStep";
import { PhotoStep } from "@/features/reports/PhotoStep";
import { LocationStep } from "@/features/reports/LocationStep";
import { DescriptionStep } from "@/features/reports/DescriptionStep";
import { ReviewStep } from "@/features/reports/ReviewStep";
import type { LocationResult } from "@/hooks/useGeolocation";
import { api, ApiError } from "@/services/api";
import { saveOfflineReport } from "@/services/offlineReportService";
import { syncPendingReports } from "@/services/syncService";
import type { DescriptionSource, OfflineReport } from "@/types";

type Step = "identity" | "photo" | "location" | "description" | "review";

export default function ReportWizard() {
  const { t, language } = useTranslation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const assistedEntry = searchParams.get("assisted") === "1";
  const citizen = useAppStore((s) => s.citizen);
  const setCitizen = useAppStore((s) => s.setCitizen);

  const [step, setStep] = useState<Step>(citizen ? "photo" : "identity");
  const [photo, setPhoto] = useState<File | null>(null);
  const [location, setLocation] = useState<LocationResult | null>(null);
  const [description, setDescription] = useState("");
  const [descriptionSource, setDescriptionSource] = useState<DescriptionSource>("TYPED");
  const [submitting, setSubmitting] = useState(false);
  const [submitLabel, setSubmitLabel] = useState<string | undefined>();
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const steps: Step[] = citizen ? ["photo", "location", "description", "review"] : ["identity", "photo", "location", "description", "review"];
  const stepIndex = steps.indexOf(step);

  // Optional spoken step guidance. Off-page (home, tracking, etc.) never
  // speaks — only this wizard, and only while the citizen has it enabled.
  // Guidance is always spoken in English, regardless of the citizen's
  // selected UI language (see constants/voiceGuidance.ts).
  const guidance = useVoiceGuidance();
  useEffect(() => {
    if (assistedEntry) guidance.setEnabled(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [assistedEntry]);
  useEffect(() => {
    const guideText: Partial<Record<Step, string>> = {
      identity: VOICE_GUIDANCE_EN.languageStep,
      photo: VOICE_GUIDANCE_EN.photoStep,
      description: VOICE_GUIDANCE_EN.descriptionStep,
      location: VOICE_GUIDANCE_EN.locationStep,
      review: VOICE_GUIDANCE_EN.reviewStep,
    };
    const text = guideText[step];
    if (text) guidance.speak(text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  function handleDescriptionChange(v: string) {
    setDescription(v);
    setDescriptionSource("TYPED");
  }

  function handleVoiceResult(v: string) {
    setDescription(v);
    setDescriptionSource("VOICE");
  }

  async function handleSubmit() {
    if (!location) return;
    // Accessibility: a photo and a description are not both required —
    // either is enough. Only block submission when neither is present.
    if (!photo && !description.trim()) {
      setErrorMsg(t.neitherProvidedError);
      return;
    }
    guidance.speak(VOICE_GUIDANCE_EN.submitStep);
    setSubmitting(true);
    setErrorMsg(null);

    const activeCitizen = citizen!;
    const clientReportId = crypto.randomUUID();

    const buildFormData = () => {
      const form = new FormData();
      form.set("client_report_id", clientReportId);
      form.set("description", description);
      form.set("latitude", String(location.latitude));
      form.set("longitude", String(location.longitude));
      form.set("accuracy", String(location.accuracy));
      form.set("language", language);
      form.set("name", activeCitizen.name);
      form.set("mobile", activeCitizen.mobile);
      form.set("was_offline", "false");
      form.set("description_source", descriptionSource);
      if (photo) form.set("image", photo);
      return form;
    };

    if (navigator.onLine) {
      try {
        setSubmitLabel(t.analyzingReport);
        const result = await api.submitReport(buildFormData());
        setSubmitting(false);
        navigate("/report/success", { state: { result } });
        return;
      } catch (err) {
        // Network failure mid-submission -> fall through to offline save.
        if (!(err instanceof ApiError)) {
          await saveOffline();
          return;
        }
        setSubmitting(false);
        setErrorMsg(err.message);
        return;
      }
    }

    await saveOffline();

    async function saveOffline() {
      setSubmitLabel(t.savingReport);
      const offlineReport: OfflineReport = {
        client_report_id: clientReportId,
        description,
        original_description: description,
        latitude: location!.latitude,
        longitude: location!.longitude,
        accuracy: location!.accuracy,
        imageBlob: photo,
        imageType: photo?.type ?? null,
        language,
        name: activeCitizen.name,
        mobile: activeCitizen.mobile,
        created_at: new Date().toISOString(),
        sync_status: "PENDING_SYNC",
        sync_attempts: 0,
        last_sync_attempt: null,
        description_source: descriptionSource,
      };
      await saveOfflineReport(offlineReport);
      setSubmitting(false);
      navigate("/report/saved-offline");
      if (navigator.onLine) syncPendingReports();
    }
  }

  return (
    <CitizenLayout showBack>
      <div className="mb-4 flex items-center gap-1">
        {steps.map((s, i) => (
          <div key={s} className={`h-1.5 flex-1 rounded-full ${i <= stepIndex ? "bg-brand-600" : "bg-slate-200"}`} />
        ))}
      </div>

      <VoiceGuidanceBar
        enabled={guidance.enabled}
        onToggle={guidance.setEnabled}
        onReplay={guidance.replay}
        uiLanguage={language}
      />

      {errorMsg && <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{errorMsg}</div>}

      {step === "identity" && (
        <IdentityStep
          onNext={(name, mobile) => {
            setCitizen({ name, mobile });
            setStep("photo");
          }}
        />
      )}

      {step === "photo" && (
        <PhotoStep
          photo={photo}
          onPhotoSelected={setPhoto}
          onNext={() => setStep("location")}
          onBack={() => (citizen ? navigate("/") : setStep("identity"))}
        />
      )}

      {step === "location" && (
        <LocationStep
          location={location}
          onLocationSet={setLocation}
          onNext={() => setStep("description")}
          onBack={() => setStep("photo")}
        />
      )}

      {step === "description" && (
        <DescriptionStep
          description={description}
          hasPhoto={!!photo}
          onDescriptionChange={handleDescriptionChange}
          onVoiceResult={handleVoiceResult}
          onNext={() => setStep("review")}
          onBack={() => setStep("location")}
        />
      )}

      {step === "review" && (
        <ReviewStep
          photo={photo}
          description={description}
          location={location}
          submitting={submitting}
          submitLabel={submitLabel}
          onSubmit={handleSubmit}
          onBack={() => setStep("description")}
        />
      )}
    </CitizenLayout>
  );
}
