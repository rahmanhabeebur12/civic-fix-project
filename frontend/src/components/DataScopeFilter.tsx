import type { DataScope } from "@/types";

const OPTIONS: { value: DataScope; label: string }[] = [
  { value: "live", label: "Live Reports" },
  { value: "demo", label: "Demo Data" },
  { value: "all", label: "All Reports" },
];

export function DataScopeFilter({ value, onChange }: { value: DataScope; onChange: (v: DataScope) => void }) {
  return (
    <div className="inline-flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition ${
            value === opt.value ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-50"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
