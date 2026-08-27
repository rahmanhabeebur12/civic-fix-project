"""
Rule-based severity/impact inference.

This module does NOT calculate priority. It only produces the structured
attributes (severity 1-5, impact_level 1-5) that the canonical
app/services/core/priority.py needs as input — the "AI/rule-based
understanding" step, not the final civic decision. The actual weighted
priority score comes exclusively from priority.calculate_priority().
"""
from dataclasses import dataclass

from app.services.taxonomy import ISSUE_TYPES

# Context keywords that escalate severity by one level when present in the
# description or nearby-location context (e.g. "near a school").
DANGER_KEYWORDS = ["school", "hospital", "children", "kids", "busy road", "blocking", "highway", "market"]

# Taxonomy base_severity (LOW/MEDIUM/HIGH/CRITICAL) -> priority.py's 1-5 scale.
BASE_SEVERITY_TO_LEVEL = {"LOW": 2, "MEDIUM": 3, "HIGH": 4, "CRITICAL": 5}
LEVEL_TO_LABEL = {1: "LOW", 2: "LOW", 3: "MEDIUM", 4: "HIGH", 5: "CRITICAL"}

# Categories with broader public-health impact get a +1 impact bump.
HIGH_IMPACT_CATEGORIES = {"Sewerage", "Drainage", "Water Supply", "Sanitation"}

REOPEN_PRIORITY_BOOST_DEFAULT = 15


@dataclass
class SeverityResult:
    severity: int  # 1-5, for priority.calculate_priority()
    label: str  # LOW/MEDIUM/HIGH/CRITICAL, for display/SLA lookups
    reason: str


def infer_severity(issue_type: str, description: str, location_context: str) -> SeverityResult:
    cfg = ISSUE_TYPES.get(issue_type, ISSUE_TYPES["Other"])
    base_label = cfg["base_severity"]
    level = BASE_SEVERITY_TO_LEVEL.get(base_label, 3)
    reasons = [f"Base severity for '{issue_type}' is {base_label}."]

    text = f"{description or ''} {location_context or ''}".lower()
    hit_keywords = [k for k in DANGER_KEYWORDS if k in text]

    if hit_keywords and level < 5:
        level = min(5, level + 1)
        reasons.append(f"Escalated due to proximity/context: {', '.join(hit_keywords)}.")

    return SeverityResult(severity=level, label=LEVEL_TO_LABEL[level], reason=" ".join(reasons))


def infer_impact_level(issue_type: str, severity_level: int) -> int:
    """Rule-based public-impact inference. Defaults to mirroring severity
    (a more severe issue usually affects the public more), with a +1 bump
    for categories with broader public-health consequences."""
    cfg = ISSUE_TYPES.get(issue_type, ISSUE_TYPES["Other"])
    impact = severity_level

    if cfg["category"] in HIGH_IMPACT_CATEGORIES:
        impact = min(5, impact + 1)

    return max(1, min(5, impact))


def apply_reopen_boost(current_score: int, boost: int = REOPEN_PRIORITY_BOOST_DEFAULT) -> int:
    return max(0, min(100, current_score + boost))
