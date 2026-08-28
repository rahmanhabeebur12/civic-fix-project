"""
review_routing.py

Orchestration layer that decides whether a citizen report needs
MANUAL_REVIEW, and explains why to staff -- without changing the
canonical, unmodified app.services.core.validator / duplicate / priority
modules in any way. It only reads their already-computed outputs
(validity status, AI classification confidence/category, duplicate
action) plus one existing pure validator.py factor function
(calculate_description_score, called read-only, exactly as
validation_adapter.py already does for other factors) and combines them
into one routing decision plus a list of staff-facing reasons.

Used from two places that must never disagree with each other:
  - report_pipeline.py, at submission time, to decide issue.status
  - routers/issues.py's compute_review_reasons(), at read time, to
    explain an already-persisted issue's review_reasons field

Both call evaluate_manual_review() with the same kind of inputs (live
values at submission time; the same values reconstructed from persisted
Issue/IssueReport fields at read time), so "why was this flagged" and
"was this actually flagged" can never drift apart.

Routing rule: a report reaches the normal active workflow (SUBMITTED ->
ASSIGNED) only when the system has enough confidence to proceed. Any
uncertainty signal below sends it to MANUAL_REVIEW instead -- never to
REJECTED; only a staff member's explicit review-decision can reject a
report.
"""
from __future__ import annotations

from app.services.core import validator as core_validator

# Reused by report_pipeline.py's "AI classified as ... (N% confidence)"
# status-history note and by issues.py, so the threshold lives in one
# place.
LOW_AI_CONFIDENCE_THRESHOLD = 0.5

# basic_description_quality() is validator.py's real (non-placeholder)
# rule-based text signal -- length, repetition, alphanumeric content.
# Below this, a description is too thin to trust on its own, regardless
# of what the overall weighted validity score lands on.
WEAK_DESCRIPTION_QUALITY_THRESHOLD = 70.0

REASON_VAGUE_DESCRIPTION = "Description is too vague"
REASON_INSUFFICIENT_VISUAL_EVIDENCE = "Insufficient visual evidence"
REASON_LOW_AI_CONFIDENCE = "Low AI confidence"
REASON_CATEGORY_UNCERTAIN = "Category uncertain"
REASON_PHOTO_TEXT_CONFLICT = "Photo and description conflict"
REASON_POSSIBLE_DUPLICATE = "Possible duplicate"
REASON_INSUFFICIENT_EVIDENCE = "Insufficient evidence"
REASON_VALIDATION_REQUIRES_REVIEW = "Validation requires review"


def evaluate_manual_review(
    *,
    validity_status: str,
    ai_confidence: float,
    category: str,
    duplicate_action: str,
    has_photo: bool,
    description: str | None,
    validator_category: str,
) -> tuple[bool, list[str]]:
    """Returns (is_manual_review, reasons). `reasons` is empty exactly
    when is_manual_review is False -- staff never see a review flag
    without a concrete reason attached."""
    has_description = bool((description or "").strip())
    reasons: list[str] = []

    # The canonical validator's own verdict is always the first signal.
    # REVIEW and SUSPICIOUS both route to manual review (never straight
    # to REJECTED) -- SUSPICIOUS gets the stronger "insufficient
    # evidence" phrasing since its score is further below the floor.
    if validity_status == "REVIEW":
        reasons.append(REASON_VALIDATION_REQUIRES_REVIEW)
    elif validity_status == "SUSPICIOUS":
        reasons.append(REASON_INSUFFICIENT_EVIDENCE)

    # A POSSIBLE duplicate (duplicate.py's own REVIEW action) is never
    # auto-merged -- it still creates its own issue, but staff should
    # confirm it isn't the same problem as an existing one.
    if duplicate_action == "REVIEW":
        reasons.append(REASON_POSSIBLE_DUPLICATE)

    # The AI/rule-based understanding layer honestly reported "Other"
    # (see issue_understanding_service._normalize_category) -- nothing
    # matched a known civic issue type closely enough to route reliably.
    if category == "Other":
        reasons.append(REASON_CATEGORY_UNCERTAIN)

    # Low AI confidence, in context: with both photo and text present,
    # a low-confidence read most plausibly means the two pieces of
    # evidence didn't reconcile; with only one modality, it means that
    # modality's evidence itself wasn't strong enough on its own.
    if ai_confidence < LOW_AI_CONFIDENCE_THRESHOLD:
        if has_photo and has_description:
            reasons.append(REASON_PHOTO_TEXT_CONFLICT)
        elif has_photo:
            reasons.append(REASON_INSUFFICIENT_VISUAL_EVIDENCE)
        else:
            reasons.append(REASON_LOW_AI_CONFIDENCE)

    # basic_description_quality() catches empty/near-empty, excessively
    # short, repeated-character, or low-alphanumeric text -- a real
    # quality problem independent of whatever the photo shows. Only
    # evaluated when text was actually provided (a PHOTO_ONLY report's
    # intentionally-absent description is not "vague", it's absent by
    # design -- see determine_submission_mode).
    if has_description:
        description_quality = core_validator.calculate_description_score(
            description, validator_category,
        )["basic_quality_score"]
        if description_quality < WEAK_DESCRIPTION_QUALITY_THRESHOLD:
            reasons.append(REASON_VAGUE_DESCRIPTION)

    # De-duplicate while preserving the order reasons were found in.
    seen: set[str] = set()
    ordered_reasons = [r for r in reasons if not (r in seen or seen.add(r))]

    return (len(ordered_reasons) > 0, ordered_reasons)
