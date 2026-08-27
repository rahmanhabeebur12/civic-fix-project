const PRIORITY_STYLES: Record<string, string> = {
  LOW: "bg-slate-100 text-slate-700",
  MEDIUM: "bg-amber-100 text-amber-800",
  HIGH: "bg-orange-100 text-orange-800",
  CRITICAL: "bg-red-100 text-red-800",
};

const SEVERITY_STYLES: Record<string, string> = {
  LOW: "bg-slate-100 text-slate-700",
  MEDIUM: "bg-amber-100 text-amber-800",
  HIGH: "bg-orange-100 text-orange-800",
  CRITICAL: "bg-red-100 text-red-800",
};

const STATUS_STYLES: Record<string, string> = {
  SUBMITTED: "bg-slate-100 text-slate-700",
  AI_VERIFIED: "bg-sky-100 text-sky-800",
  MANUAL_REVIEW: "bg-purple-100 text-purple-800",
  ASSIGNED: "bg-indigo-100 text-indigo-800",
  ACCEPTED: "bg-blue-100 text-blue-800",
  IN_PROGRESS: "bg-amber-100 text-amber-800",
  AWAITING_CITIZEN_VERIFICATION: "bg-cyan-100 text-cyan-800",
  RESOLVED: "bg-green-100 text-green-800",
  REOPENED: "bg-red-100 text-red-800",
  REJECTED: "bg-slate-200 text-slate-600",
  TRANSFERRED: "bg-indigo-100 text-indigo-800",
};

const VALIDITY_STYLES: Record<string, string> = {
  VALID: "bg-green-100 text-green-800",
  REVIEW: "bg-amber-100 text-amber-800",
  SUSPICIOUS: "bg-red-100 text-red-800",
};

const DUPLICATE_CONFIDENCE_STYLES: Record<string, string> = {
  HIGH: "bg-red-100 text-red-800",
  POSSIBLE: "bg-amber-100 text-amber-800",
  NONE: "bg-slate-100 text-slate-700",
};

function Badge({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${className}`}>
      {label.replace(/_/g, " ")}
    </span>
  );
}

export function PriorityBadge({ level }: { level: string }) {
  return <Badge label={level} className={PRIORITY_STYLES[level] || "bg-slate-100 text-slate-700"} />;
}

export function SeverityBadge({ level }: { level: string }) {
  return <Badge label={level} className={SEVERITY_STYLES[level] || "bg-slate-100 text-slate-700"} />;
}

export function StatusBadge({ status }: { status: string }) {
  return <Badge label={status} className={STATUS_STYLES[status] || "bg-slate-100 text-slate-700"} />;
}

export function ValidityBadge({ status }: { status: string }) {
  return <Badge label={status} className={VALIDITY_STYLES[status] || "bg-slate-100 text-slate-700"} />;
}

export function DuplicateConfidenceBadge({ confidence }: { confidence: string }) {
  return <Badge label={confidence} className={DUPLICATE_CONFIDENCE_STYLES[confidence] || "bg-slate-100 text-slate-700"} />;
}

export function DemoBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-dashed border-violet-300 bg-violet-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-violet-700">
      🧪 Demo Data
    </span>
  );
}
