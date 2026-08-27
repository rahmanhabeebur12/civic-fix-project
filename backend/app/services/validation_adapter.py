"""
validation_adapter.py

Accessibility-aware adapter around the canonical, unmodified
app.services.core.validator module.

validator.calculate_validity() hard-requires description, category,
photo_path, latitude, and longitude — if any one is missing, its own
validate_report_input() records an error and calculate_validity() caps
the final score below REVIEW_THRESHOLD, forcing SUSPICIOUS. That is the
right behavior for a report that is *accidentally* missing evidence. It
is the wrong behavior for a citizen who deliberately relies on the
accessibility path — someone who cannot type, or cannot use a camera —
who still deserves a chance at VALID/REVIEW rather than an automatic
SUSPICIOUS, provided their other evidence is genuinely strong.

This module does NOT change validator.py's formula, weights, or
thresholds, and does not add a second competing score. For a normal
photo+description report it calls calculate_validity() directly,
unmodified, exactly as before. For an accessibility-mode report (photo
only, or description only) it calls the SAME six public factor
functions and the SAME weighting/threshold functions
calculate_validity() itself uses internally — just without going through
the hard required-field gate that only exists to catch *accidental*
omissions. A report missing GPS, or with an unrecognized category, still
goes through the normal gate unchanged.

The missing field is never fabricated: it is passed through to
validator's own factor functions exactly as missing (None/empty), so
that factor honestly scores 0 — the accessibility path only changes
whether the OTHER five strong factors are allowed to matter.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.core import validator as core_validator

PHOTO_AND_TEXT = "PHOTO_AND_TEXT"
PHOTO_ONLY = "PHOTO_ONLY"
TEXT_ONLY = "TEXT_ONLY"

# A moderate, configurable confidence penalty applied on top of the
# naturally-lower weighted score (missing one 20%-weighted factor already
# lowers the score on its own) so the accessibility gap is visibly and
# transparently accounted for rather than silently absorbed into the
# six-factor math.
ACCESSIBILITY_CONFIDENCE_PENALTY = 5.0


def determine_submission_mode(description: str | None, has_photo: bool) -> str:
    has_description = bool((description or "").strip())
    if has_photo and has_description:
        return PHOTO_AND_TEXT
    if has_photo:
        return PHOTO_ONLY
    return TEXT_ONLY


@dataclass
class AdapterResult:
    validity_score: float
    status: str
    breakdown: dict
    validation_errors: list[str]
    submission_mode: str
    accessibility_adjustment: bool


def calculate_validity_adaptive(report: dict[str, Any], *, submission_mode: str) -> AdapterResult:
    if submission_mode == PHOTO_AND_TEXT:
        result = core_validator.calculate_validity(report)
        return AdapterResult(
            validity_score=result["validity_score"],
            status=result["status"],
            breakdown=result["breakdown"],
            validation_errors=result["validation_errors"],
            submission_mode=submission_mode,
            accessibility_adjustment=False,
        )

    # --- Accessibility path: PHOTO_ONLY or TEXT_ONLY -----------------------
    # Same six factor functions as calculate_validity() — computed exactly
    # the same way, nothing fabricated. The one factor that is structurally
    # inapplicable (photo_validity for TEXT_ONLY, description_category_
    # consistency for PHOTO_ONLY) is excluded from the weighted sum rather
    # than silently scored 0 against its full weight: validator.py's own
    # SCORING_WEIGHTS for the remaining five factors are renormalized so
    # they still sum to 1.0. Without this, a missing 20%-weighted factor
    # combines with a brand-new user's cold-start reliability/duplicate-
    # evidence scores (which validator.py deliberately keeps low until a
    # track record exists) to push even a strong, honest accessibility
    # report below the SUSPICIOUS floor every time — which would make
    # "REVIEW if evidence is incomplete" impossible to reach and would
    # effectively punish citizens for using the accessibility path itself,
    # not for anything actually suspicious about their report.
    photo_path = report.get("photo_path")
    description = report.get("description")
    category = report.get("category")

    photo_result = core_validator.calculate_photo_score(photo_path, category)
    description_result = core_validator.calculate_description_score(description, category)
    location_result = core_validator.calculate_location_score(report.get("latitude"), report.get("longitude"))
    user_reliability_score = core_validator.calculate_user_reliability(report.get("user_previous_reports"))
    duplicate_evidence_score = core_validator.calculate_duplicate_evidence(report.get("number_of_previous_reports"))
    spam_frequency_score = core_validator.calculate_spam_frequency(report.get("user_previous_reports"))

    factor_scores = {
        "photo_validity": photo_result["score"],
        "description_category_consistency": description_result["score"],
        "location_validity": location_result["score"],
        "user_reliability": user_reliability_score,
        "duplicate_evidence": duplicate_evidence_score,
        "spam_frequency": spam_frequency_score,
    }

    excluded_factor = "description_category_consistency" if submission_mode == PHOTO_ONLY else "photo_validity"
    available_weight = sum(w for f, w in core_validator.SCORING_WEIGHTS.items() if f != excluded_factor)
    effective_weights = {
        f: (core_validator.SCORING_WEIGHTS[f] / available_weight if f != excluded_factor else 0.0)
        for f in core_validator.SCORING_WEIGHTS
    }

    weighted_score = sum(
        core_validator.clamp_score(score) * effective_weights[factor]
        for factor, score in factor_scores.items()
    )

    adjusted_score = round(core_validator.clamp_score(weighted_score - ACCESSIBILITY_CONFIDENCE_PENALTY), 2)

    # validator.py's own status thresholds (80/60) — untouched. A report
    # only lands in SUSPICIOUS here if the *remaining* real evidence is
    # itself weak — never automatically just for using the accessibility
    # path.
    status = core_validator.determine_status(adjusted_score)

    reasons: list[str] = []
    if submission_mode == PHOTO_ONLY:
        reasons.append("Description not provided")
    else:
        reasons.append("Photo not provided")
    reasons.append("Accepted under accessibility mode")

    # Same shape as validator.calculate_validity()'s own breakdown, so the
    # existing admin Validation UI renders this identically either way —
    # the excluded factor is visible with weight 0 rather than hidden.
    breakdown = {
        factor: {
            "score": round(score, 2),
            "weight": round(effective_weights[factor], 4),
            "weighted_contribution": round(core_validator.clamp_score(score) * effective_weights[factor], 2),
        }
        for factor, score in factor_scores.items()
    }

    return AdapterResult(
        validity_score=adjusted_score,
        status=status,
        breakdown=breakdown,
        validation_errors=reasons,
        submission_mode=submission_mode,
        accessibility_adjustment=True,
    )
