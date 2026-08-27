import { useState } from "react";
import { useTranslation } from "@/hooks/useTranslation";

export function IdentityStep({ onNext }: { onNext: (name: string, mobile: string) => void }) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [mobile, setMobile] = useState("");
  const canContinue = name.trim().length >= 2 && /^\d{10}$/.test(mobile.trim());

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-slate-500">{t.guestNote}</p>
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">{t.yourName}</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="input-field"
          placeholder="e.g. Ravi Kumar"
          autoFocus
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">{t.yourMobile}</label>
        <input
          value={mobile}
          onChange={(e) => setMobile(e.target.value.replace(/\D/g, "").slice(0, 10))}
          className="input-field"
          placeholder="10-digit mobile number"
          inputMode="numeric"
        />
      </div>
      <button className="btn-primary mt-4" disabled={!canContinue} onClick={() => onNext(name.trim(), mobile.trim())}>
        {t.next}
      </button>
    </div>
  );
}
