/**
 * Single shared source of truth for how citizen-facing pages (Track
 * Report, My Reports) translate the REAL backend Issue.status into
 * friendly text and timeline progress. Both pages must import from here
 * rather than maintaining their own mapping, so they can never disagree.
 *
 * The backend status (app/models/issue.py Issue.status, set exclusively
 * by app/services/report_pipeline.py and app/routers/issues.py) is
 * always the source of truth — nothing here invents or guesses a status.
 */

export const CITIZEN_STATUS_LABELS: Record<string, string> = {
  SUBMITTED: "Submitted",
  MANUAL_REVIEW: "Under Review",
  ASSIGNED: "Assigned",
  ACCEPTED: "Accepted",
  IN_PROGRESS: "In Progress",
  AWAITING_CITIZEN_VERIFICATION: "Awaiting Your Verification",
  RESOLVED: "Resolved",
  REOPENED: "Reopened",
  REJECTED: "Rejected",
};

export function getCitizenStatusLabel(status: string): string {
  return CITIZEN_STATUS_LABELS[status] || status.replace(/_/g, " ");
}

export const CITIZEN_STATUS_MESSAGES: Record<string, string> = {
  SUBMITTED: "Your report has been received and is waiting for review or assignment.",
  MANUAL_REVIEW: "Your report is being reviewed before it's assigned to a department.",
  ASSIGNED: "Your report has been assigned to the relevant department.",
  ACCEPTED: "The department has accepted your report.",
  IN_PROGRESS: "Work on this issue has started.",
  AWAITING_CITIZEN_VERIFICATION: "The department says this has been fixed — please confirm below.",
  RESOLVED: "This issue has been resolved.",
  REOPENED: "This issue has been reopened and is being worked on again.",
  REJECTED: "This report was not accepted after review.",
};

export function getCitizenStatusMessage(status: string): string {
  return CITIZEN_STATUS_MESSAGES[status] || "";
}

// The real main-path lifecycle, in order (mirrors report_pipeline.py /
// routers/issues.py exactly). MANUAL_REVIEW and REJECTED are side
// states — not points on this line — so a report sitting in
// MANUAL_REVIEW has NOT reached "Assigned" yet, even though it comes
// "after" SUBMITTED chronologically.
export const TIMELINE_STATUSES = [
  "SUBMITTED",
  "ASSIGNED",
  "ACCEPTED",
  "IN_PROGRESS",
  "AWAITING_CITIZEN_VERIFICATION",
  "RESOLVED",
] as const;

/**
 * How many timeline steps are genuinely complete for a given backend
 * status. This is the exact root cause of reports appearing "Accepted"
 * or "In Progress" before staff had actually done that: the previous
 * version fell back to the LAST timeline index for any status it didn't
 * recognize (MANUAL_REVIEW, REJECTED, TRANSFERRED), which marked every
 * step in between — including Accepted and In Progress — as done.
 *
 * Never assume a stage was reached that the backend hasn't confirmed.
 */
export function getTimelineStepIndex(status: string): number {
  const idx = TIMELINE_STATUSES.indexOf(status as (typeof TIMELINE_STATUSES)[number]);
  if (idx !== -1) return idx;
  if (status === "REOPENED") {
    // A citizen rejected the resolution evidence -> back to active work,
    // same position as IN_PROGRESS. This mirrors the one case the
    // previous logic already handled correctly.
    return TIMELINE_STATUSES.indexOf("IN_PROGRESS");
  }
  // MANUAL_REVIEW, REJECTED, or anything unexpected: the only thing
  // confirmed to have happened is the initial submission.
  return 0;
}
