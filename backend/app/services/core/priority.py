"""
priority.py

Priority scoring for valid civic issue reports.

This module calculates how urgently a valid civic issue should be handled.
Report validity is intentionally outside the scope of this module and should
be checked separately by validator.py before calculate_priority() is called.

Python 3.10+
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEVERITY_WEIGHT = 0.30
REPORTER_WEIGHT = 0.20
LOCATION_WEIGHT = 0.20
AGE_WEIGHT = 0.15
IMPACT_WEIGHT = 0.15

SCORE_MIN = 0.0
SCORE_MAX = 100.0

# Severity and public-impact values use a five-level scale.
LEVEL_SCORE_MAPPING: dict[int, float] = {
    1: 20.0,
    2: 40.0,
    3: 60.0,
    4: 80.0,
    5: 100.0,
}

SEVERITY_SCORES = LEVEL_SCORE_MAPPING
IMPACT_SCORES = LEVEL_SCORE_MAPPING

LOCATION_SCORES: dict[str, float] = {
    "normal_area": 40.0,
    "residential_area": 50.0,
    "market": 60.0,
    "busy_road": 70.0,
    "public_transport": 80.0,
    "school": 100.0,
    "hospital": 100.0,
    "critical_infrastructure": 100.0,
}

# Reporter ranges are evaluated from highest threshold downward.
REPORTER_SCORE_THRESHOLDS: tuple[tuple[int, float], ...] = (
    (11, 100.0),
    (7, 80.0),
    (4, 60.0),
    (2, 40.0),
    (1, 20.0),
)

AGE_THRESHOLDS_HOURS: tuple[tuple[float, float], ...] = (
    (6.0, 20.0),       # Less than 6 hours
    (24.0, 40.0),      # 6–24 hours
    (72.0, 60.0),      # 1–3 days
    (168.0, 80.0),      # 3–7 days
    (float("inf"), 100.0),  # More than 7 days
)

# Lower bound is inclusive; upper bound is exclusive.
PRIORITY_THRESHOLDS: tuple[tuple[float, str], ...] = (
    (90.0, "CRITICAL"),
    (75.0, "HIGH"),
    (50.0, "MEDIUM"),
    (0.0, "LOW"),
)

EMERGENCY_LOCATION_TYPES: frozenset[str] = frozenset(
    {
        "school",
        "hospital",
        "critical_infrastructure",
    }
)

EMERGENCY_MINIMUM_SCORE = 90.0

# Safe defaults for malformed or missing values.
DEFAULT_SEVERITY_SCORE = SEVERITY_SCORES[1]
DEFAULT_REPORTER_SCORE = 0.0
DEFAULT_LOCATION_SCORE = LOCATION_SCORES["normal_area"]
DEFAULT_AGE_SCORE = AGE_THRESHOLDS_HOURS[0][1]
DEFAULT_IMPACT_SCORE = IMPACT_SCORES[1]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clamp_score(score: float) -> float:
    """Clamp a numeric score to the inclusive range 0–100."""
    try:
        numeric_score = float(score)
    except (TypeError, ValueError):
        return SCORE_MIN

    if numeric_score != numeric_score:  # NaN check
        return SCORE_MIN

    return max(SCORE_MIN, min(SCORE_MAX, numeric_score))


def _parse_positive_int(value: Any) -> int | None:
    """
    Convert a value to a non-negative integer when it is safely possible.

    Boolean values are rejected because True/False are usually accidental
    inputs when a numeric field is expected.
    """
    if isinstance(value, bool):
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    if numeric_value != numeric_value:  # NaN
        return None

    if numeric_value < 0:
        return None

    if not numeric_value.is_integer():
        return None

    return int(numeric_value)


def _normalize_location_type(location_type: Any) -> str:
    """Normalize a location type into a safe lookup key."""
    if not isinstance(location_type, str):
        return ""

    return location_type.strip().lower()


def _parse_created_at(created_at: Any) -> datetime | None:
    """
    Parse an ISO 8601 timestamp.

    Naive timestamps are interpreted using the local system timezone.
    Timezone-aware timestamps are converted to the local timezone for
    comparison. A trailing ``Z`` is supported.
    """
    if not isinstance(created_at, str) or not created_at.strip():
        return None

    timestamp = created_at.strip()

    # datetime.fromisoformat() accepts +00:00 but not Z on some Python
    # versions, so normalize a trailing Z explicitly.
    if timestamp.endswith(("Z", "z")):
        timestamp = timestamp[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(timestamp)
    except (TypeError, ValueError):
        return None

    local_now = datetime.now().astimezone()

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=local_now.tzinfo)

    return parsed.astimezone(local_now.tzinfo)


# ---------------------------------------------------------------------------
# Factor scoring
# ---------------------------------------------------------------------------

def calculate_severity_score(severity: Any) -> float:
    """
    Convert severity from 1–5 into a 0–100 score.

    Mapping:
        1 -> 20
        2 -> 40
        3 -> 60
        4 -> 80
        5 -> 100

    Invalid, missing, or unsupported values receive the safest low-severity
    default rather than causing an exception.
    """
    if isinstance(severity, bool):
        return DEFAULT_SEVERITY_SCORE

    try:
        numeric_severity = float(severity)
    except (TypeError, ValueError):
        return DEFAULT_SEVERITY_SCORE

    if (
        numeric_severity != numeric_severity
        or not numeric_severity.is_integer()
    ):
        return DEFAULT_SEVERITY_SCORE

    return SEVERITY_SCORES.get(
        int(numeric_severity),
        DEFAULT_SEVERITY_SCORE,
    )


def calculate_reporter_score(number_of_reporters: Any) -> float:
    """
    Convert the number of independent reporters into a 0–100 score.

    Mapping:
        1       -> 20
        2–3     -> 40
        4–6     -> 60
        7–10    -> 80
        11+     -> 100

    Invalid, missing, or negative values receive a score of 0.
    """
    reporters = _parse_positive_int(number_of_reporters)

    if reporters is None or reporters == 0:
        return DEFAULT_REPORTER_SCORE

    for minimum_reporters, score in REPORTER_SCORE_THRESHOLDS:
        if reporters >= minimum_reporters:
            return score

    return DEFAULT_REPORTER_SCORE


def calculate_location_score(location_type: Any) -> float:
    """
    Convert a location type into its configured importance score.

    Unknown location types use the ``normal_area`` score.
    """
    normalized_location = _normalize_location_type(location_type)

    return LOCATION_SCORES.get(
        normalized_location,
        DEFAULT_LOCATION_SCORE,
    )


def calculate_age_score(created_at: Any) -> float:
    """
    Convert issue age into a 0–100 score.

    Mapping:
        < 6 hours    -> 20
        6–24 hours   -> 40
        1–3 days     -> 60
        3–7 days     -> 80
        > 7 days     -> 100

    Invalid or missing timestamps receive the minimum age score so that a
    malformed timestamp does not artificially make an issue urgent.
    Future timestamps are treated as the minimum age.
    """
    parsed_timestamp = _parse_created_at(created_at)

    if parsed_timestamp is None:
        return DEFAULT_AGE_SCORE

    now = datetime.now(parsed_timestamp.tzinfo)

    age_hours = (now - parsed_timestamp).total_seconds() / 3600.0

    # A future timestamp should not receive an elevated age score.
    if age_hours < 0:
        age_hours = 0.0

    for maximum_hours, score in AGE_THRESHOLDS_HOURS:
        if age_hours < maximum_hours:
            return score

    return 100.0


def calculate_impact_score(impact_level: Any) -> float:
    """
    Convert public impact level from 1–5 into a 0–100 score.

    Mapping:
        1 -> 20
        2 -> 40
        3 -> 60
        4 -> 80
        5 -> 100

    Invalid, missing, or unsupported values receive the lowest impact score.
    """
    if isinstance(impact_level, bool):
        return DEFAULT_IMPACT_SCORE

    try:
        numeric_impact = float(impact_level)
    except (TypeError, ValueError):
        return DEFAULT_IMPACT_SCORE

    if (
        numeric_impact != numeric_impact
        or not numeric_impact.is_integer()
    ):
        return DEFAULT_IMPACT_SCORE

    return IMPACT_SCORES.get(
        int(numeric_impact),
        DEFAULT_IMPACT_SCORE,
    )


# ---------------------------------------------------------------------------
# Priority level and emergency handling
# ---------------------------------------------------------------------------

def get_priority_level(score: Any) -> str:
    """
    Convert a 0–100 priority score into a priority level.

    Thresholds:
        90–100 -> CRITICAL
        75–89  -> HIGH
        50–74  -> MEDIUM
        0–49   -> LOW
    """
    normalized_score = _clamp_score(
        float(score) if _is_numeric(score) else SCORE_MIN
    )

    for minimum_score, level in PRIORITY_THRESHOLDS:
        if normalized_score >= minimum_score:
            return level

    return "LOW"


def _is_numeric(value: Any) -> bool:
    """Return True when a value can safely be converted to a finite float."""
    if isinstance(value, bool):
        return False

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False

    return numeric_value == numeric_value and numeric_value not in (
        float("inf"),
        float("-inf"),
    )


def apply_emergency_override(score: Any, issue: Mapping[str, Any]) -> float:
    """
    Apply the emergency minimum-priority rule.

    A score is raised to at least 90 when severity is 5 and the location is
    a school, hospital, or critical infrastructure.

    This function only changes priority. It does not perform or imply
    validity checks.
    """
    base_score = _clamp_score(
        float(score) if _is_numeric(score) else SCORE_MIN
    )

    if not isinstance(issue, Mapping):
        return base_score

    severity_is_critical = False

    severity = issue.get("severity")
    if not isinstance(severity, bool):
        try:
            severity_is_critical = float(severity) == 5.0
        except (TypeError, ValueError):
            severity_is_critical = False

    location_type = _normalize_location_type(
        issue.get("location_type")
    )

    if severity_is_critical and location_type in EMERGENCY_LOCATION_TYPES:
        return max(base_score, EMERGENCY_MINIMUM_SCORE)

    return base_score


# ---------------------------------------------------------------------------
# Reason generation
# ---------------------------------------------------------------------------

def generate_priority_reasons(
    issue: Mapping[str, Any],
    breakdown: Mapping[str, float],
) -> list[str]:
    """
    Generate human-readable explanations for the calculated priority.

    Reasons are based on the supplied issue data and factor scores rather
    than on the final priority level alone.
    """
    if not isinstance(issue, Mapping):
        issue = {}

    reasons: list[str] = []

    severity = issue.get("severity")
    severity_score = breakdown.get("severity", DEFAULT_SEVERITY_SCORE)

    if severity_score >= 100:
        reasons.append("Critical severity")
    elif severity_score >= 80:
        reasons.append("High severity")
    elif severity_score >= 60:
        reasons.append("Moderate severity")

    reporters = _parse_positive_int(issue.get("number_of_reporters"))
    if reporters is not None:
        if reporters >= 11:
            reasons.append("Many independent citizens reported this issue")
        elif reporters >= 2:
            reasons.append("Multiple citizens reported this issue")

    location_type = _normalize_location_type(issue.get("location_type"))

    location_descriptions = {
        "normal_area": "normal area",
        "residential_area": "residential area",
        "market": "market",
        "busy_road": "busy road",
        "public_transport": "public transport area",
        "school": "school",
        "hospital": "hospital",
        "critical_infrastructure": "critical infrastructure",
    }

    if location_type in location_descriptions:
        location_score = breakdown.get(
            "location",
            DEFAULT_LOCATION_SCORE,
        )
        if location_score >= 60:
            reasons.append(
                f"Issue is located near a "
                f"{location_descriptions[location_type]}"
            )

    age_score = breakdown.get("age", DEFAULT_AGE_SCORE)
    if age_score >= 100:
        reasons.append("Issue has remained unresolved for more than 7 days")
    elif age_score >= 80:
        reasons.append("Issue has remained unresolved for several days")
    elif age_score >= 60:
        reasons.append("Issue has remained unresolved for more than a day")

    impact_score = breakdown.get("impact", DEFAULT_IMPACT_SCORE)
    if impact_score >= 100:
        reasons.append("Very high public impact")
    elif impact_score >= 80:
        reasons.append("High public impact")
    elif impact_score >= 60:
        reasons.append("Moderate public impact")

    if (
        severity == 5
        and location_type in EMERGENCY_LOCATION_TYPES
    ):
        reasons.append(
            "Emergency override applied due to critical severity "
            "at a sensitive location"
        )

    return reasons


# ---------------------------------------------------------------------------
# Main priority calculation
# ---------------------------------------------------------------------------

def calculate_priority(issue: Mapping[str, Any]) -> dict[str, Any]:
    """
    Calculate the priority of a valid civic issue.

    Parameters:
        issue: Mapping containing severity, number_of_reporters,
            location_type, created_at, and impact_level.

    Returns:
        A JSON-friendly dictionary containing the final priority score,
        priority level, individual factor scores, and human-readable reasons.

    Notes:
        This function assumes that the caller has already verified the issue
        with validator.py. No validity calculation is performed here.
    """
    if not isinstance(issue, Mapping):
        issue = {}

    severity_score = _clamp_score(
        calculate_severity_score(issue.get("severity"))
    )
    reporter_score = _clamp_score(
        calculate_reporter_score(issue.get("number_of_reporters"))
    )
    location_score = _clamp_score(
        calculate_location_score(issue.get("location_type"))
    )
    age_score = _clamp_score(
        calculate_age_score(issue.get("created_at"))
    )
    impact_score = _clamp_score(
        calculate_impact_score(issue.get("impact_level"))
    )

    weighted_score = (
        severity_score * SEVERITY_WEIGHT
        + reporter_score * REPORTER_WEIGHT
        + location_score * LOCATION_WEIGHT
        + age_score * AGE_WEIGHT
        + impact_score * IMPACT_WEIGHT
    )

    priority_score = apply_emergency_override(weighted_score, issue)
    priority_score = round(_clamp_score(priority_score))

    breakdown: dict[str, float | int] = {
        "severity": round(severity_score),
        "reporters": round(reporter_score),
        "location": round(location_score),
        "age": round(age_score),
        "impact": round(impact_score),
    }

    return {
        "priority_score": priority_score,
        "priority_level": get_priority_level(priority_score),
        "breakdown": breakdown,
        "reasons": generate_priority_reasons(issue, breakdown),
    }


# ---------------------------------------------------------------------------
# Standalone tests / demonstration
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pprint import pprint

    TEST_TIMESTAMP = "2026-08-27T08:30:00"

    test_cases: list[tuple[str, dict[str, Any]]] = [
        (
            "LOW priority — minor footpath issue",
            {
                "severity": 1,
                "number_of_reporters": 1,
                "location_type": "normal_area",
                "created_at": TEST_TIMESTAMP,
                "impact_level": 1,
            },
        ),
        (
            "MEDIUM priority — moderate garbage issue",
            {
                "severity": 3,
                "number_of_reporters": 5,
                "location_type": "residential_area",
                "created_at": TEST_TIMESTAMP,
                "impact_level": 3,
            },
        ),
        (
            "HIGH priority — serious pothole on busy road",
            {
                "severity": 4,
                "number_of_reporters": 8,
                "location_type": "busy_road",
                "created_at": TEST_TIMESTAMP,
                "impact_level": 4,
            },
        ),
        (
            "CRITICAL priority — drainage/safety issue near school",
            {
                "severity": 5,
                "number_of_reporters": 8,
                "location_type": "school",
                "created_at": TEST_TIMESTAMP,
                "impact_level": 5,
            },
        ),
    ]

    print("=" * 72)
    print("CIVIC ISSUE PRIORITY TESTS")
    print("=" * 72)

    for title, issue in test_cases:
        print(f"\n{title}")
        print("-" * len(title))
        print("Issue:")
        pprint(issue, sort_dicts=False)
        print("Result:")
        pprint(calculate_priority(issue), sort_dicts=False)

    print("\n" + "=" * 72)
    print("EMERGENCY OVERRIDE TEST")
    print("=" * 72)

    emergency_issue = {
        "severity": 5,
        "number_of_reporters": 1,
        "location_type": "hospital",
        "created_at": TEST_TIMESTAMP,
        "impact_level": 1,
    }

    normal_weighted_score = (
        calculate_severity_score(emergency_issue["severity"])
        * SEVERITY_WEIGHT
        + calculate_reporter_score(emergency_issue["number_of_reporters"])
        * REPORTER_WEIGHT
        + calculate_location_score(emergency_issue["location_type"])
        * LOCATION_WEIGHT
        + calculate_age_score(emergency_issue["created_at"])
        * AGE_WEIGHT
        + calculate_impact_score(emergency_issue["impact_level"])
        * IMPACT_WEIGHT
    )

    overridden_score = apply_emergency_override(
        normal_weighted_score,
        emergency_issue,
    )

    print(f"Weighted score before override: {normal_weighted_score:.2f}")
    print(f"Score after emergency override: {overridden_score:.2f}")
    print(f"Priority level: {get_priority_level(overridden_score)}")
    print("\nFull result:")
    pprint(calculate_priority(emergency_issue), sort_dicts=False)