
"""
validator.py

Rule-based validator for a crowdsourced civic issue reporting system.

The module is intentionally independent of Flask, databases, external APIs,
and machine-learning libraries.

Architecture:
    1. Validate the report's basic structure and required fields.
    2. Validate the selected civic category.
    3. Validate the photo path and basic image-file properties.
    4. Perform basic description-quality checks.
    5. Use a placeholder for future AI/NLP category matching.
    6. Perform basic GPS coordinate validation.
    7. Use a placeholder for future geospatial verification.
    8. Calculate user reliability from reporting history.
    9. Calculate duplicate evidence from previous reports.
   10. Calculate spam/frequency risk from user history.
   11. Combine all six factors using configurable weights.
   12. Return a structured result suitable for later Flask integration.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from numbers import Real
from typing import Any, Dict, List, Optional


# ============================================================================
# CONFIGURATION
# ============================================================================

# The six required scoring factors.
PHOTO_WEIGHT = 0.20
DESCRIPTION_WEIGHT = 0.20
LOCATION_WEIGHT = 0.20
USER_RELIABILITY_WEIGHT = 0.15
DUPLICATE_WEIGHT = 0.15
SPAM_FREQUENCY_WEIGHT = 0.10

SCORING_WEIGHTS: Dict[str, float] = {
    "photo_validity": PHOTO_WEIGHT,
    "description_category_consistency": DESCRIPTION_WEIGHT,
    "location_validity": LOCATION_WEIGHT,
    "user_reliability": USER_RELIABILITY_WEIGHT,
    "duplicate_evidence": DUPLICATE_WEIGHT,
    "spam_frequency": SPAM_FREQUENCY_WEIGHT,
}

# Status thresholds.
VALID_THRESHOLD = 80.0
REVIEW_THRESHOLD = 60.0

MIN_SCORE = 0.0
MAX_SCORE = 100.0

# Supported categories can be expanded later.
VALID_CATEGORIES = {
    "pothole",
    "road_damage",
    "streetlight",
    "garbage",
    "waste",
    "water_leak",
    "drainage",
    "flooding",
    "traffic_signal",
    "broken_sidewalk",
    "sidewalk",
    "illegal_dumping",
    "sewage",
    "public_toilet",
    "tree_damage",
    "fallen_tree",
    "stray_animal",
    "noise",
    "other",
}

# Basic image extensions. This does NOT verify image contents.
VALID_IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
}

# A reasonable maximum description length for a civic report.
MAX_DESCRIPTION_LENGTH = 5000

# Future timestamps beyond this tolerance are considered suspicious.
FUTURE_TIMESTAMP_TOLERANCE_SECONDS = 300


# ============================================================================
# GENERAL HELPERS
# ============================================================================

def clamp_score(score: Real) -> float:
    """
    Clamp a score to the allowed 0-100 range.

    Args:
        score: Numeric score.

    Returns:
        Score between 0.0 and 100.0.
    """
    return max(MIN_SCORE, min(MAX_SCORE, float(score)))


def is_numeric(value: Any) -> bool:
    """
    Determine whether a value is a numeric value without accepting booleans.

    Args:
        value: Value to check.

    Returns:
        True if the value is a real number and is not a boolean.
    """
    return isinstance(value, Real) and not isinstance(value, bool)


def is_non_empty(value: Any) -> bool:
    """
    Determine whether a value exists and is not an empty string.

    Args:
        value: Value to check.

    Returns:
        True if the value contains usable data.
    """
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    return True


def safe_non_negative_integer(value: Any, default: int = 0) -> int:
    """
    Convert a numeric count into a safe non-negative integer.

    Args:
        value: Value to convert.
        default: Value returned when conversion is not possible.

    Returns:
        Non-negative integer.
    """
    if not is_numeric(value):
        return default

    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return default


# ============================================================================
# CATEGORY VALIDATION
# ============================================================================

def normalize_category(category: Any) -> Optional[str]:
    """
    Normalize a category for consistent rule-based validation.

    Args:
        category: Category supplied by the user.

    Returns:
        Normalized category or None if it is not usable.
    """
    if not isinstance(category, str):
        return None

    normalized = category.strip().lower()

    if not normalized:
        return None

    return normalized


def validate_category(category: Any) -> Dict[str, Any]:
    """
    Validate whether the report contains a supported civic category.

    This is basic category validation only. It does not determine whether
    the description semantically matches the category.

    Args:
        category: User-selected category.

    Returns:
        Structured category validation result.
    """
    normalized = normalize_category(category)

    if normalized is None:
        return {
            "valid": False,
            "category": None,
            "error": "category must be a non-empty string",
        }

    if normalized not in VALID_CATEGORIES:
        return {
            "valid": False,
            "category": normalized,
            "error": f"unsupported category: {normalized}",
        }

    return {
        "valid": True,
        "category": normalized,
        "error": None,
    }


# ============================================================================
# TIMESTAMP VALIDATION
# ============================================================================

def parse_timestamp(timestamp: Any) -> Optional[datetime]:
    """
    Parse a supported ISO-8601 timestamp.

    Args:
        timestamp: Timestamp value from the report.

    Returns:
        Parsed datetime, or None if parsing fails.
    """
    if not isinstance(timestamp, str) or not timestamp.strip():
        return None

    value = timestamp.strip()

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))

        # Treat a timezone-naive timestamp as local application time.
        if parsed.tzinfo is None:
            return parsed

        return parsed
    except ValueError:
        return None


def validate_timestamp(timestamp: Any) -> Dict[str, Any]:
    """
    Validate timestamp format and detect timestamps significantly in the future.

    Timestamp validation is supplementary to the six required scoring factors.

    Args:
        timestamp: Report timestamp.

    Returns:
        Structured timestamp validation result.
    """
    if not is_non_empty(timestamp):
        return {
            "valid": True,
            "provided": False,
            "error": None,
        }

    parsed = parse_timestamp(timestamp)

    if parsed is None:
        return {
            "valid": False,
            "provided": True,
            "error": "timestamp must be a valid ISO-8601 timestamp",
        }

    now = datetime.now(timezone.utc)

    if parsed.tzinfo is None:
        # Naive timestamps are compared against naive UTC for a safe,
        # deterministic prototype check.
        comparison_time = now.replace(tzinfo=None)
    else:
        comparison_time = parsed.astimezone(timezone.utc)

    if comparison_time.timestamp() > now.timestamp() + FUTURE_TIMESTAMP_TOLERANCE_SECONDS:
        return {
            "valid": False,
            "provided": True,
            "error": "timestamp is too far in the future",
        }

    return {
        "valid": True,
        "provided": True,
        "error": None,
    }


# ============================================================================
# DESCRIPTION VALIDATION
# ============================================================================

def basic_description_quality(description: Any) -> float:
    """
    Perform basic rule-based checks on description quality.

    This intentionally does NOT determine whether the description semantically
    matches the selected category. That task belongs to the future NLP
    placeholder.

    Rules include:
        - Missing/empty description -> 0
        - Very short descriptions -> lower score
        - Excessively long descriptions -> lower score
        - Meaningful text -> higher score
        - Excessive repeated characters -> lower score
        - Excessive whitespace -> lower score

    Args:
        description: User-provided description.

    Returns:
        Basic description-quality score from 0-100.
    """
    if not isinstance(description, str):
        return 0.0

    text = description.strip()

    if not text:
        return 0.0

    score = 100.0

    length = len(text)

    if length < 10:
        score -= 35
    elif length < 20:
        score -= 15

    if length > MAX_DESCRIPTION_LENGTH:
        score -= 25

    # A description consisting almost entirely of one repeated character
    # is unlikely to be useful.
    if len(set(text.lower().replace(" ", ""))) <= 2 and length >= 10:
        score -= 50

    # Penalize obvious excessive character repetition such as "!!!!!!!".
    repeated_patterns = ("!!!", "???", "...", "111", "aaa", "xxx")
    lowered = text.lower()

    if any(pattern in lowered for pattern in repeated_patterns):
        score -= 15

    # A useful civic report normally contains several alphanumeric characters.
    alphanumeric_count = sum(character.isalnum() for character in text)

    if alphanumeric_count < 5:
        score -= 25

    return clamp_score(score)


# TODO: FUTURE AI/NLP DESCRIPTION ANALYSIS
# Replace this function with an NLP model that checks:
# - whether the description is meaningful
# - whether it matches the selected category
# - whether the description is spam
# - whether the description appears unrelated to the civic issue
def analyze_description(description: Any, category: Any) -> float:
    """
    Placeholder for future AI/NLP semantic description analysis.

    The current implementation intentionally does not perform semantic
    category matching. It only returns the requested prototype default.

    Args:
        description: User-provided description.
        category: Selected civic issue category.

    Returns:
        Prototype semantic consistency score from 0-100.
    """
    if not is_non_empty(description) or not is_non_empty(category):
        return 0.0

    return 70.0


def calculate_description_score(
    description: Any,
    category: Any,
) -> Dict[str, Any]:
    """
    Combine basic description quality with future semantic analysis.

    The basic checks are fully functional. Semantic category matching remains
    a placeholder.

    Args:
        description: User-provided description.
        category: Selected civic issue category.

    Returns:
        Description scoring details.
    """
    quality_score = basic_description_quality(description)

    semantic_score = analyze_description(description, category)

    # Both aspects contribute equally for the prototype.
    final_score = clamp_score((quality_score + semantic_score) / 2)

    return {
        "score": final_score,
        "basic_quality_score": quality_score,
        "semantic_analysis_score": semantic_score,
    }


# ============================================================================
# PHOTO VALIDATION
# ============================================================================

def validate_photo_path(photo_path: Any) -> Dict[str, Any]:
    """
    Perform basic local validation of a photo path.

    This function does NOT inspect the actual image content. It checks:
        - whether a path was supplied
        - whether it has an image extension
        - whether the referenced file exists
        - whether it is a regular file

    Args:
        photo_path: Path to the uploaded image.

    Returns:
        Structured photo validation information.
    """
    if not isinstance(photo_path, str) or not photo_path.strip():
        return {
            "provided": False,
            "path_valid": False,
            "file_exists": False,
            "is_image_extension": False,
            "error": "photo_path is missing",
        }

    path = Path(photo_path.strip())

    is_image_extension = path.suffix.lower() in VALID_IMAGE_EXTENSIONS

    try:
        exists = path.exists()
        is_file = path.is_file()
    except (OSError, ValueError):
        exists = False
        is_file = False

    if not is_image_extension:
        error = "photo_path does not have a supported image extension"
    elif not exists:
        error = "photo file does not exist"
    elif not is_file:
        error = "photo_path does not point to a regular file"
    else:
        error = None

    return {
        "provided": True,
        "path_valid": is_image_extension and exists and is_file,
        "file_exists": exists,
        "is_image_extension": is_image_extension,
        "error": error,
    }


# TODO: FUTURE AI IMAGE ANALYSIS
# Replace this function with a computer-vision model that checks:
# - whether the uploaded image is valid
# - image quality
# - whether the image matches the reported civic issue
# - whether the image is relevant to the selected category
def analyze_image(photo_path: Any, category: Any) -> float:
    """
    Placeholder for future AI image analysis.

    Actual image-content verification is intentionally not implemented.

    Args:
        photo_path: Path to the uploaded image.
        category: Selected civic issue category.

    Returns:
        Prototype AI image score from 0-100.
    """
    if not is_non_empty(photo_path) or not is_non_empty(category):
        return 0.0

    return 70.0


def calculate_photo_score(
    photo_path: Any,
    category: Any,
) -> Dict[str, Any]:
    """
    Calculate the photo validity score.

    Basic file/path validation is fully implemented. Actual visual analysis
    remains a future AI placeholder.

    Args:
        photo_path: Uploaded photo path.
        category: Selected category.

    Returns:
        Photo scoring details.
    """
    path_result = validate_photo_path(photo_path)
    ai_score = analyze_image(photo_path, category)

    if not path_result["provided"]:
        basic_score = 0.0
    elif not path_result["path_valid"]:
        basic_score = 20.0
    else:
        basic_score = 100.0

    # Actual visual relevance/quality is intentionally represented by the
    # placeholder function.
    final_score = clamp_score((basic_score + ai_score) / 2)

    return {
        "score": final_score,
        "basic_file_score": basic_score,
        "image_analysis_score": ai_score,
        "file_validation": path_result,
    }


# ============================================================================
# GPS / LOCATION VALIDATION
# ============================================================================

def basic_coordinate_validation(
    latitude: Any,
    longitude: Any,
) -> Dict[str, Any]:
    """
    Perform basic numerical GPS validation.

    This checks only whether coordinates are numeric and inside the globally
    valid latitude/longitude ranges.

    Args:
        latitude: Latitude.
        longitude: Longitude.

    Returns:
        Structured coordinate validation result.
    """
    errors: List[str] = []

    if latitude is None:
        errors.append("latitude is missing")
    elif not is_numeric(latitude):
        errors.append("latitude must be numeric")
    elif not -90 <= float(latitude) <= 90:
        errors.append("latitude must be between -90 and 90")

    if longitude is None:
        errors.append("longitude is missing")
    elif not is_numeric(longitude):
        errors.append("longitude must be numeric")
    elif not -180 <= float(longitude) <= 180:
        errors.append("longitude must be between -180 and 180")

    return {
        "valid": not errors,
        "errors": errors,
    }


# TODO: FUTURE GPS/LOCATION VALIDATION
# Replace this logic with proper geospatial validation that checks:
# - whether coordinates are inside the supported city/region
# - whether the coordinates are realistic
# - whether the location is suspicious
# - whether the user is repeatedly submitting reports from abnormal locations
def validate_location(latitude: Any, longitude: Any) -> float:
    """
    Placeholder for future GPS/geospatial validation.

    Current implementation performs only basic coordinate range validation.

    Args:
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.

    Returns:
        Location score from 0-100.
    """
    result = basic_coordinate_validation(latitude, longitude)

    if not result["valid"]:
        return 0.0

    # Requested prototype default for numerically valid coordinates.
    return 70.0


def calculate_location_score(
    latitude: Any,
    longitude: Any,
) -> Dict[str, Any]:
    """
    Calculate the location validity score.

    Args:
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.

    Returns:
        Location scoring details.
    """
    basic_result = basic_coordinate_validation(latitude, longitude)
    gps_analysis_score = validate_location(latitude, longitude)

    if not basic_result["valid"]:
        basic_score = 0.0
    else:
        basic_score = 100.0

    final_score = clamp_score((basic_score + gps_analysis_score) / 2)

    return {
        "score": final_score,
        "basic_coordinate_score": basic_score,
        "gps_analysis_score": gps_analysis_score,
        "coordinate_validation": basic_result,
    }


# ============================================================================
# USER RELIABILITY
# ============================================================================

def calculate_user_reliability(previous_reports: Any) -> float:
    """
    Calculate prototype user reliability.

    Rules:
        0 previous reports   -> 60
        1-5                   -> 75
        6-20                  -> 85
        21+                   -> 95

    This is only a prototype. It should not permanently penalize users.
    In a production system, reliability should ideally consider actual report
    outcomes, verification history, false reports, and other fair signals.

    Args:
        previous_reports: Number of previous reports submitted by the user.

    Returns:
        User reliability score from 0-100.
    """
    count = safe_non_negative_integer(previous_reports)

    if count == 0:
        return 60.0

    if count <= 5:
        return 75.0

    if count <= 20:
        return 85.0

    return 95.0


# ============================================================================
# DUPLICATE EVIDENCE
# ============================================================================

def calculate_duplicate_evidence(previous_reports: Any) -> float:
    """
    Calculate evidence from previous reports of the same issue.

    Rules:
        0 previous reports  -> 60
        1-2                 -> 75
        3-5                 -> 90
        6+                  -> 100

    Important:
        A duplicate report is NOT automatically invalid.

        If multiple citizens independently report the same civic issue, that
        can increase confidence that the issue really exists. Therefore this
        factor is called "duplicate evidence" rather than "duplicate penalty".

        A production system should use actual similarity, location, and
        timestamp information to distinguish independent reports from users
        repeatedly submitting the exact same report.

    Args:
        previous_reports: Number of previous reports for the issue.

    Returns:
        Duplicate-evidence score from 0-100.
    """
    count = safe_non_negative_integer(previous_reports)

    if count == 0:
        return 60.0

    if count <= 2:
        return 75.0

    if count <= 5:
        return 90.0

    return 100.0


# ============================================================================
# SPAM / FREQUENCY
# ============================================================================

def calculate_spam_frequency(previous_reports: Any) -> float:
    """
    Calculate a simple spam/frequency score.

    Rules:
        0-10 previous reports   -> 100
        11-30                   -> 80
        31-100                  -> 60
        101+                    -> 30

    This is only a frequency signal. It must not automatically classify a user
    as malicious or reject their report.

    Args:
        previous_reports: Number of previous reports by the user.

    Returns:
        Spam/frequency score from 0-100.
    """
    count = safe_non_negative_integer(previous_reports)

    if count <= 10:
        return 100.0

    if count <= 30:
        return 80.0

    if count <= 100:
        return 60.0

    return 30.0


# ============================================================================
# BASIC REPORT VALIDATION
# ============================================================================

def validate_report_input(report: Any) -> List[str]:
    """
    Validate the required report fields.

    Required:
        - description
        - category
        - photo_path
        - latitude
        - longitude

    Optional:
        - timestamp
        - user_id
        - number_of_previous_reports
        - user_previous_reports

    Args:
        report: Report dictionary.

    Returns:
        List of validation errors. An empty list means the required structure
        is valid.
    """
    errors: List[str] = []

    if not isinstance(report, dict):
        return ["report must be a dictionary"]

    required_fields = (
        "description",
        "category",
        "photo_path",
        "latitude",
        "longitude",
    )

    for field in required_fields:
        if not is_non_empty(report.get(field)):
            errors.append(f"missing required field: {field}")

    # Basic coordinate validation.
    coordinate_result = basic_coordinate_validation(
        report.get("latitude"),
        report.get("longitude"),
    )

    errors.extend(coordinate_result["errors"])

    # Category validation.
    category_result = validate_category(report.get("category"))

    if not category_result["valid"] and category_result["error"]:
        errors.append(category_result["error"])

    # Description type/length validation.
    description = report.get("description")

    if is_non_empty(description) and not isinstance(description, str):
        errors.append("description must be a string")

    if isinstance(description, str) and len(description.strip()) > MAX_DESCRIPTION_LENGTH:
        errors.append(
            f"description exceeds maximum length of {MAX_DESCRIPTION_LENGTH}"
        )

    # Optional timestamp validation.
    if "timestamp" in report:
        timestamp_result = validate_timestamp(report.get("timestamp"))

        if not timestamp_result["valid"] and timestamp_result["error"]:
            errors.append(timestamp_result["error"])

    # Optional numeric count validation.
    for field in (
        "number_of_previous_reports",
        "user_previous_reports",
    ):
        if field in report and report[field] is not None:
            if not is_numeric(report[field]):
                errors.append(f"{field} must be numeric")
            elif float(report[field]) < 0:
                errors.append(f"{field} cannot be negative")

    return errors


# ============================================================================
# WEIGHTED SCORE
# ============================================================================

def calculate_weighted_score(scores: Dict[str, float]) -> float:
    """
    Calculate the final weighted validity score.

    Args:
        scores: Mapping of factor names to 0-100 scores.

    Returns:
        Weighted score from 0-100.
    """
    total = 0.0

    for factor, weight in SCORING_WEIGHTS.items():
        factor_score = clamp_score(scores.get(factor, 0.0))
        total += factor_score * weight

    return clamp_score(total)


def determine_status(score: float) -> str:
    """
    Convert a validity score into a report status.

    Rules:
        80-100 -> VALID
        60-79  -> REVIEW
        0-59   -> SUSPICIOUS

    Args:
        score: Final validity score.

    Returns:
        Status string.
    """
    score = clamp_score(score)

    if score >= VALID_THRESHOLD:
        return "VALID"

    if score >= REVIEW_THRESHOLD:
        return "REVIEW"

    return "SUSPICIOUS"


# ============================================================================
# MAIN VALIDATION FUNCTION
# ============================================================================

def calculate_validity(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a civic issue report and calculate its validity score.

    The six weighted factors are:

        Photo validity / quality                  20%
        Description/category consistency          20%
        Location validity                         20%
        User reliability                          15%
        Duplicate evidence                        15%
        Spam/frequency check                      10%

    The function never intentionally crashes because of missing or malformed
    report fields. Instead, it returns structured validation information.

    Actual AI image verification, semantic description matching, and
    geospatial verification are deliberately not implemented.

    Args:
        report: Civic issue report dictionary.

    Returns:
        Dictionary containing:
            validity_score
            status
            breakdown
            validation_errors
    """
    validation_errors = validate_report_input(report)

    if not isinstance(report, dict):
        return {
            "validity_score": 0.0,
            "status": "SUSPICIOUS",
            "breakdown": {},
            "validation_errors": validation_errors,
        }

    # ------------------------------------------------------------------------
    # 1. PHOTO VALIDITY / QUALITY - 20%
    # ------------------------------------------------------------------------

    photo_result = calculate_photo_score(
        report.get("photo_path"),
        report.get("category"),
    )

    # ------------------------------------------------------------------------
    # 2. DESCRIPTION / CATEGORY CONSISTENCY - 20%
    # ------------------------------------------------------------------------

    description_result = calculate_description_score(
        report.get("description"),
        report.get("category"),
    )

    # ------------------------------------------------------------------------
    # 3. LOCATION VALIDITY - 20%
    # ------------------------------------------------------------------------

    location_result = calculate_location_score(
        report.get("latitude"),
        report.get("longitude"),
    )

    # ------------------------------------------------------------------------
    # 4. USER RELIABILITY - 15%
    # ------------------------------------------------------------------------

    user_reliability_score = calculate_user_reliability(
        report.get("user_previous_reports"),
    )

    # ------------------------------------------------------------------------
    # 5. DUPLICATE EVIDENCE - 15%
    # ------------------------------------------------------------------------

    duplicate_score = calculate_duplicate_evidence(
        report.get("number_of_previous_reports"),
    )

    # ------------------------------------------------------------------------
    # 6. SPAM / FREQUENCY - 10%
    # ------------------------------------------------------------------------

    spam_frequency_score = calculate_spam_frequency(
        report.get("user_previous_reports"),
    )

    # Store the six raw factor scores.
    factor_scores: Dict[str, float] = {
        "photo_validity": photo_result["score"],
        "description_category_consistency": description_result["score"],
        "location_validity": location_result["score"],
        "user_reliability": user_reliability_score,
        "duplicate_evidence": duplicate_score,
        "spam_frequency": spam_frequency_score,
    }

    # Calculate the normal weighted score.
    final_score = calculate_weighted_score(factor_scores)

    # If required fields are invalid, cap the report below VALID. This means
    # malformed reports are sent for review rather than being accepted.
    if validation_errors:
        final_score = min(final_score, REVIEW_THRESHOLD - 0.01)

    final_score = round(clamp_score(final_score), 2)

    # Calculate each factor's contribution to the final score.
    weighted_contributions = {
        factor: round(
            clamp_score(score) * SCORING_WEIGHTS[factor],
            2,
        )
        for factor, score in factor_scores.items()
    }

    return {
        "validity_score": final_score,
        "status": determine_status(final_score),
        "breakdown": {
            "photo_validity": {
                "score": round(photo_result["score"], 2),
                "weight": PHOTO_WEIGHT,
                "weighted_contribution": weighted_contributions[
                    "photo_validity"
                ],
                "details": {
                    "basic_file_score": round(
                        photo_result["basic_file_score"],
                        2,
                    ),
                    "image_analysis_score": round(
                        photo_result["image_analysis_score"],
                        2,
                    ),
                    "file_validation": photo_result["file_validation"],
                },
            },
            "description_category_consistency": {
                "score": round(description_result["score"], 2),
                "weight": DESCRIPTION_WEIGHT,
                "weighted_contribution": weighted_contributions[
                    "description_category_consistency"
                ],
                "details": {
                    "basic_description_quality": round(
                        description_result["basic_quality_score"],
                        2,
                    ),
                    "future_semantic_analysis": round(
                        description_result["semantic_analysis_score"],
                        2,
                    ),
                },
            },
            "location_validity": {
                "score": round(location_result["score"], 2),
                "weight": LOCATION_WEIGHT,
                "weighted_contribution": weighted_contributions[
                    "location_validity"
                ],
                "details": {
                    "basic_coordinate_score": round(
                        location_result["basic_coordinate_score"],
                        2,
                    ),
                    "future_gps_analysis": round(
                        location_result["gps_analysis_score"],
                        2,
                    ),
                    "coordinate_validation": location_result[
                        "coordinate_validation"
                    ],
                },
            },
            "user_reliability": {
                "score": round(user_reliability_score, 2),
                "weight": USER_RELIABILITY_WEIGHT,
                "weighted_contribution": weighted_contributions[
                    "user_reliability"
                ],
            },
            "duplicate_evidence": {
                "score": round(duplicate_score, 2),
                "weight": DUPLICATE_WEIGHT,
                "weighted_contribution": weighted_contributions[
                    "duplicate_evidence"
                ],
            },
            "spam_frequency": {
                "score": round(spam_frequency_score, 2),
                "weight": SPAM_FREQUENCY_WEIGHT,
                "weighted_contribution": weighted_contributions[
                    "spam_frequency"
                ],
            },
        },
        "validation_errors": validation_errors,
    }


# ============================================================================
# SAMPLE TESTS
# ============================================================================

if __name__ == "__main__":
    """
    Run three local examples.

    Note:
        The sample photo paths may not exist on the machine running this file.
        The validator intentionally detects that situation without crashing.
        To test successful local photo-path validation, replace the sample
        paths with actual image files.
    """

    sample_reports = [
        {
            "name": "1. Highly valid pothole report",
            "report": {
                "user_id": 101,
                "description": (
                    "Large pothole on the road near the school. "
                    "It is causing vehicles to slow down and move around it."
                ),
                "category": "pothole",
                "photo_path": "uploads/pothole1.jpg",
                "latitude": 13.0827,
                "longitude": 80.2707,
                "timestamp": "2026-08-27T10:30:00",
                "number_of_previous_reports": 4,
                "user_previous_reports": 5,
            },
        },
        {
            "name": "2. Report requiring review",
            "report": {
                "user_id": 202,
                "description": "There is an issue on the road near the school.",
                "category": "pothole",
                "photo_path": "uploads/road_issue.jpg",
                "latitude": 13.0827,
                "longitude": 80.2707,
                "timestamp": "2026-08-27T11:00:00",
                "number_of_previous_reports": 0,
                "user_previous_reports": 25,
            },
        },
        {
            "name": "3. Suspicious / spam-like report",
            "report": {
                "user_id": 303,
                "description": "!!!",
                "category": "pothole",
                "photo_path": "",
                "latitude": 13.0827,
                "longitude": 80.2707,
                "timestamp": "2026-08-27T11:30:00",
                "number_of_previous_reports": 0,
                "user_previous_reports": 150,
            },
        },
    ]

    print("=" * 80)
    print("CIVIC ISSUE VALIDITY VALIDATOR")
    print("=" * 80)

    for sample in sample_reports:
        print(f"\n{'-' * 80}")
        print(sample["name"])
        print("-" * 80)

        result = calculate_validity(sample["report"])

        print(f"Validity Score : {result['validity_score']:.2f}/100")
        print(f"Status         : {result['status']}")

        print("\nFactor Breakdown:")

        for factor, details in result["breakdown"].items():
            print(
                f"  {factor}"
                f"\n    Score        : {details['score']:.2f}/100"
                f"\n    Weight       : {details['weight']:.0%}"
                f"\n    Contribution : {details['weighted_contribution']:.2f}"
            )

        print("\nValidation Errors:")

        if result["validation_errors"]:
            for error in result["validation_errors"]:
                print(f"  - {error}")
        else:
            print("  None")

    print(f"\n{'=' * 80}")

