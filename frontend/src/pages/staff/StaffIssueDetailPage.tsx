import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { StaffLayout } from "@/components/StaffLayout";
import { PriorityBadge, SeverityBadge, StatusBadge, ValidityBadge, DuplicateConfidenceBadge, DemoBadge } from "@/components/Badges";
import { Spinner } from "@/components/Spinner";
import { api, imageUrl, ApiError } from "@/services/api";
import type { Department, StaffIssueDetail } from "@/types";

const PRIORITY_WEIGHTS: Record<string, number> = {
  severity: 30, reporters: 20, location: 20, age: 15, impact: 15,
};
const PRIORITY_LABELS: Record<string, string> = {
  severity: "Severity", reporters: "Reporters", location: "Location", age: "Age", impact: "Public Impact",
};

const VALIDITY_LABELS: Record<string, string> = {
  photo_validity: "Photo Score",
  description_category_consistency: "Description Score",
  location_validity: "Location Score",
  user_reliability: "User Reliability",
  duplicate_evidence: "Duplicate Evidence",
  spam_frequency: "Spam / Frequency",
};

export default function StaffIssueDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const issueId = Number(id);
  const [issue, setIssue] = useState<StaffIssueDetail | null>(null);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [showTransfer, setShowTransfer] = useState(false);
  const [transferDept, setTransferDept] = useState<string>("");
  const [showResolve, setShowResolve] = useState(false);
  const [resolveNote, setResolveNote] = useState("");
  const [resolveImage, setResolveImage] = useState<File | null>(null);

  function load() {
    api.staffIssueDetail(issueId).then(setIssue).catch((e) => setError(e instanceof ApiError ? e.message : "Failed to load."));
  }

  useEffect(() => {
    load();
    api.departments().then(setDepartments).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [issueId]);

  async function runAction(fn: () => Promise<any>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !issue) {
    return (
      <StaffLayout>
        <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-sm text-red-700">{error}</p>
      </StaffLayout>
    );
  }

  if (!issue) {
    return (
      <StaffLayout>
        <Spinner label="Loading issue…" />
      </StaffLayout>
    );
  }

  const latestResolution = issue.resolutions[issue.resolutions.length - 1];
  const priorityBreakdown = issue.priority_breakdown;
  const validityBreakdown = issue.validity_breakdown;
  const duplicateBreakdown = issue.duplicate_breakdown;

  return (
    <StaffLayout>
      <button className="mb-3 text-sm text-slate-500 hover:underline" onClick={() => navigate(-1)}>← Back</button>

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">{issue.complaint_id}</h1>
          <p className="text-sm text-slate-500">{issue.issue_type} · {issue.category}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <StatusBadge status={issue.status} />
          <SeverityBadge level={issue.severity} />
          <PriorityBadge level={issue.priority_level} />
          <ValidityBadge status={issue.validity_status} />
          {issue.is_overdue && <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700">OVERDUE (SLA {issue.sla_hours}h)</span>}
          {issue.is_demo && <DemoBadge />}
        </div>
      </div>

      {issue.review_reasons.length > 0 && (
        <div className="mb-5 rounded-xl border border-purple-200 bg-purple-50 px-4 py-3">
          <p className="mb-1.5 text-xs font-bold uppercase tracking-wide text-purple-700">Why this needs review</p>
          <div className="flex flex-wrap gap-1.5">
            {issue.review_reasons.map((r) => (
              <span key={r} className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-purple-700">{r.replace(/_/g, " ")}</span>
            ))}
          </div>
        </div>
      )}

      {error && <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="flex flex-col gap-5 lg:col-span-2">
          {/* Images */}
          <div className="card">
            <h2 className="mb-3 text-sm font-bold text-slate-600">Evidence</h2>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <p className="mb-1 text-center text-xs font-semibold text-slate-400">Before (Citizen)</p>
                {issue.image_url && <img src={imageUrl(issue.image_url)} className="h-48 w-full rounded-lg object-cover" />}
              </div>
              <div>
                <p className="mb-1 text-center text-xs font-semibold text-slate-400">After (Resolution)</p>
                {latestResolution ? (
                  <img src={imageUrl(latestResolution.image_url)} className="h-48 w-full rounded-lg object-cover" />
                ) : (
                  <div className="flex h-48 items-center justify-center rounded-lg border-2 border-dashed border-slate-200 text-xs text-slate-400">
                    No resolution yet
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Description & AI */}
          <div className="card">
            <h2 className="mb-2 text-sm font-bold text-slate-600">Description</h2>
            <p className="text-sm text-slate-800">{issue.original_description}</p>
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <Info label="AI Confidence" value={`${Math.round(issue.ai_confidence * 100)}%`} />
              <Info label="Severity Reason" value={issue.severity_reason} span2 />
              <Info label="Location Context" value={issue.location_context} span2 />
              <Info label="Coordinates" value={`${issue.latitude.toFixed(5)}, ${issue.longitude.toFixed(5)}`} />
            </div>
            <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-500">AI reasoning: {issue.ai_reasoning}</p>
          </div>

          {/* VALIDATION */}
          <div className="card">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-600">Validation</h2>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">{issue.validity_score}/100</span>
                <ValidityBadge status={issue.validity_status} />
              </div>
            </div>
            <div className="flex flex-col gap-2">
              {Object.entries(VALIDITY_LABELS).map(([key, label]) => {
                const factor = (validityBreakdown as any)?.[key];
                return (
                  <BreakdownBar
                    key={key}
                    label={label}
                    score={factor?.score}
                    weightPct={factor ? Math.round(factor.weight * 100) : undefined}
                  />
                );
              })}
            </div>
            {issue.validation_errors.length > 0 && (
              <div className="mt-3">
                <p className="mb-1 text-xs font-semibold text-slate-500">Validation Errors</p>
                <div className="flex flex-wrap gap-1">
                  {issue.validation_errors.map((e, i) => (
                    <span key={i} className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] text-red-700">{e}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* DUPLICATE ANALYSIS */}
          <div className="card">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-600">Duplicate Analysis</h2>
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-400">{issue.duplicate_score}/100</span>
                <DuplicateConfidenceBadge confidence={issue.duplicate_confidence} />
              </div>
            </div>
            <div className="mb-3 flex flex-wrap gap-3 text-xs text-slate-500">
              <span>Decision: <strong className="text-slate-700">{issue.duplicate_action}</strong></span>
              {issue.duplicate_distance_meters != null && <span>Distance: <strong className="text-slate-700">{issue.duplicate_distance_meters}m</strong></span>}
            </div>
            <div className="flex flex-col gap-2">
              <BreakdownBar label="Location" score={duplicateBreakdown?.location} weightPct={40} />
              <BreakdownBar label="Category" score={duplicateBreakdown?.category} weightPct={25} />
              <BreakdownBar label="Description" score={duplicateBreakdown?.description} weightPct={25} />
              <BreakdownBar label="Photo" score={duplicateBreakdown?.photo} weightPct={10} />
            </div>
          </div>

          {/* PRIORITY */}
          <div className="card">
            <h2 className="mb-3 text-sm font-bold text-slate-600">Priority ({issue.priority_score}/100 · {issue.priority_level})</h2>
            <div className="flex flex-col gap-2">
              {Object.entries(PRIORITY_LABELS).map(([key, label]) => (
                <BreakdownBar
                  key={key}
                  label={label}
                  score={(priorityBreakdown as any)?.[key]}
                  weightPct={PRIORITY_WEIGHTS[key]}
                />
              ))}
            </div>
            {issue.priority_reasons.length > 0 && (
              <ul className="mt-3 flex flex-col gap-1 text-xs text-slate-500">
                {issue.priority_reasons.map((r, i) => <li key={i}>• {r}</li>)}
              </ul>
            )}
          </div>

          {/* Reports */}
          <div className="card">
            <h2 className="mb-3 text-sm font-bold text-slate-600">Citizen Reports ({issue.reports.length})</h2>
            <div className="flex flex-col gap-3">
              {issue.reports.map((r) => (
                <div key={r.id} className="rounded-lg border border-slate-100 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-slate-800">{r.original_description}</span>
                    <ValidityBadge status={r.validity_status} />
                  </div>
                  <p className="mt-1 text-xs text-slate-400">Validity score: {r.validity_score}/100 {r.was_offline && "· Synced from offline"}</p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {r.validation_errors.map((f, i) => (
                      <span key={`ve-${i}`} className="rounded-full bg-red-50 px-2 py-0.5 text-[10px] text-red-700">{f}</span>
                    ))}
                    {r.supplemental_flags.map((f, i) => (
                      <span key={`sf-${i}`} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600">{f}</span>
                    ))}
                  </div>
                  {r.reporter_reliability && (
                    <p className="mt-2 text-[11px] text-slate-400">
                      Reporter reliability:{" "}
                      <span className={
                        r.reporter_reliability.label === "TRUSTED" ? "font-semibold text-green-700"
                        : r.reporter_reliability.label === "BUILDING" ? "font-semibold text-amber-700"
                        : "font-semibold text-slate-500"
                      }>
                        {r.reporter_reliability.label}
                      </span>{" "}
                      ({r.reporter_reliability.score}/100, {r.reporter_reliability.resolved_as_genuine} confirmed genuine · trust context only, does not affect priority)
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Timeline */}
          <div className="card">
            <h2 className="mb-3 text-sm font-bold text-slate-600">Timeline</h2>
            <ol className="flex flex-col gap-2">
              {issue.timeline.map((t, i) => (
                <li key={i} className="flex items-start gap-3 text-sm">
                  <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-brand-500" />
                  <div>
                    <p className="font-medium text-slate-800">{t.status.replace(/_/g, " ")} <span className="text-xs text-slate-400">by {t.changed_by}</span></p>
                    <p className="text-xs text-slate-500">{t.note}</p>
                    <p className="text-[11px] text-slate-400">{new Date(t.timestamp).toLocaleString()}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </div>

        {/* Actions sidebar */}
        <div className="flex flex-col gap-4">
          <div className="card">
            <h2 className="mb-3 text-sm font-bold text-slate-600">Actions</h2>
            <div className="flex flex-col gap-2">
              {issue.status === "MANUAL_REVIEW" && (
                <>
                  <button className="btn-primary" disabled={busy} onClick={() => runAction(() => api.reviewDecision(issueId, "APPROVED"))}>Approve Review</button>
                  <button className="btn-danger" disabled={busy} onClick={() => runAction(() => api.reviewDecision(issueId, "REJECTED"))}>Reject</button>
                </>
              )}
              {["SUBMITTED", "AI_VERIFIED", "ASSIGNED"].includes(issue.status) && (
                <button className="btn-primary" disabled={busy} onClick={() => runAction(() => api.acceptIssue(issueId))}>Accept Issue</button>
              )}
              {["ACCEPTED", "REOPENED"].includes(issue.status) && (
                <button className="btn-primary" disabled={busy} onClick={() => runAction(() => api.startWork(issueId))}>
                  {issue.status === "REOPENED" ? "Resume Work" : "Start Work"}
                </button>
              )}
              {issue.status === "IN_PROGRESS" && (
                <button className="btn-primary" disabled={busy} onClick={() => setShowResolve(true)}>Upload Resolution</button>
              )}
              <button className="btn-secondary" disabled={busy} onClick={() => setShowTransfer(true)}>Transfer Department</button>
            </div>
          </div>

          <div className="card">
            <h2 className="mb-2 text-sm font-bold text-slate-600">Add Internal Note</h2>
            <textarea className="input-field mb-2 min-h-[80px]" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Internal note visible to staff…" />
            <button
              className="btn-secondary w-full"
              disabled={busy || !note.trim()}
              onClick={() => runAction(async () => { await api.addNote(issueId, note); setNote(""); })}
            >
              Add Note
            </button>
          </div>

          <div className="card text-sm">
            <h2 className="mb-2 text-sm font-bold text-slate-600">Details</h2>
            <Info label="Department" value={issue.department || "Unassigned"} />
            <Info label="Supporting Dept." value={issue.supporting_department || "—"} />
            <Info label="Location Type" value={issue.location_type} />
            <Info label="Reporter Count" value={String(issue.reporter_count)} />
            <Info label="Reopen Count" value={String(issue.reopen_count)} />
            <Info label="Created" value={new Date(issue.created_at).toLocaleString()} />
            {issue.accepted_at && <Info label="Accepted" value={new Date(issue.accepted_at).toLocaleString()} />}
            {issue.work_started_at && <Info label="Work Started" value={new Date(issue.work_started_at).toLocaleString()} />}
            {issue.resolved_at && <Info label="Resolved" value={new Date(issue.resolved_at).toLocaleString()} />}
          </div>
        </div>
      </div>

      {showTransfer && (
        <Modal onClose={() => setShowTransfer(false)} title="Transfer Department">
          <select className="input-field mb-3" value={transferDept} onChange={(e) => setTransferDept(e.target.value)}>
            <option value="">Select department…</option>
            {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <button
            className="btn-primary w-full"
            disabled={!transferDept || busy}
            onClick={() =>
              runAction(async () => {
                await api.transferIssue(issueId, Number(transferDept));
                setShowTransfer(false);
              })
            }
          >
            Transfer
          </button>
        </Modal>
      )}

      {showResolve && (
        <Modal onClose={() => setShowResolve(false)} title="Upload Resolution Evidence">
          <input type="file" accept="image/*" className="input-field mb-3" onChange={(e) => setResolveImage(e.target.files?.[0] || null)} />
          <textarea
            className="input-field mb-3 min-h-[80px]"
            placeholder="Resolution note (e.g. Repair completed and affected area restored.)"
            value={resolveNote}
            onChange={(e) => setResolveNote(e.target.value)}
          />
          <button
            className="btn-primary w-full"
            disabled={!resolveImage || !resolveNote.trim() || busy}
            onClick={() =>
              runAction(async () => {
                const form = new FormData();
                form.set("note", resolveNote);
                form.set("image", resolveImage!);
                await api.resolveIssue(issueId, form);
                setShowResolve(false);
                setResolveNote("");
                setResolveImage(null);
              })
            }
          >
            {busy ? "Uploading…" : "Submit Resolution"}
          </button>
        </Modal>
      )}
    </StaffLayout>
  );
}

function Info({ label, value, span2 }: { label: string; value: string; span2?: boolean }) {
  return (
    <div className={span2 ? "col-span-2" : undefined}>
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-sm font-medium text-slate-800">{value || "—"}</p>
    </div>
  );
}

function BreakdownBar({ label, score, weightPct }: { label: string; score?: number; weightPct?: number }) {
  const value = score ?? 0;
  const pct = Math.min(100, Math.max(0, value));
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-500">
        <span>{label}{weightPct != null && <span className="text-slate-400"> ({weightPct}%)</span>}</span>
        <span>{value}/100</span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-100">
        <div className="h-2 rounded-full bg-brand-500" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="w-full max-w-sm rounded-2xl bg-white p-5 shadow-xl">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="font-bold text-slate-800">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}
