import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CitizenLayout } from "@/components/CitizenLayout";
import { useTranslation } from "@/hooks/useTranslation";
import { useAppStore } from "@/store/appStore";
import { api, ApiError } from "@/services/api";

type Mode = "login" | "register";

export default function LoginPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const setCitizenAuth = useAppStore((s) => s.setCitizenAuth);

  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [mobile, setMobile] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const mobileValid = /^\d{10}$/.test(mobile);
  const canSubmit = mode === "login"
    ? mobileValid && password.length > 0
    : name.trim().length >= 2 && mobileValid && password.length >= 4;

  async function handleSubmit() {
    if (!canSubmit || busy) return;
    setBusy(true);
    setError(null);
    try {
      const result = mode === "login" ? await api.citizenLogin(mobile, password) : await api.citizenRegister(name.trim(), mobile, password);
      setCitizenAuth(result.access_token, { name: result.name, mobile: result.mobile });
      navigate("/");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : mode === "login" ? t.loginFailedMessage : t.registerFailedMessage);
    } finally {
      setBusy(false);
    }
  }

  return (
    <CitizenLayout showBack>
      <div className="mx-auto flex max-w-sm flex-col items-center pt-4 text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-navy-700 text-xl font-bold text-white shadow-sm">CF</span>
        <h1 className="mt-4 text-2xl font-bold text-navy-800">{mode === "login" ? t.loginWelcomeBack : t.registerTitle}</h1>
        <p className="mt-1 text-sm text-slate-500">{mode === "login" ? t.loginSubtitle : t.registerSubtitle}</p>

        <div className="mt-8 flex w-full flex-col gap-3 text-left">
          {mode === "register" && (
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">{t.yourName}</label>
              <input className="input-field" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Ravi Kumar" autoFocus />
            </div>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">{t.yourMobile}</label>
            <input
              className="input-field"
              value={mobile}
              onChange={(e) => setMobile(e.target.value.replace(/\D/g, "").slice(0, 10))}
              placeholder="10-digit mobile number"
              inputMode="numeric"
              autoFocus={mode === "login"}
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">{mode === "login" ? t.password : t.choosePassword}</label>
            <input
              className="input-field"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>

          {error && <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

          <button className="btn-primary mt-2" disabled={!canSubmit || busy} onClick={handleSubmit}>
            {busy ? t.submitting : mode === "login" ? t.login : t.createAccount}
          </button>

          <button
            type="button"
            className="text-sm font-semibold text-brand-700 underline"
            onClick={() => {
              setMode(mode === "login" ? "register" : "login");
              setError(null);
            }}
          >
            {mode === "login" ? t.needAccount : t.alreadyHaveAccount}
          </button>
        </div>

        <div className="mt-10 w-full border-t border-slate-200 pt-6">
          <button className="btn-secondary w-full" onClick={() => navigate("/")}>
            {t.continueAsGuest}
          </button>
        </div>
      </div>
    </CitizenLayout>
  );
}
