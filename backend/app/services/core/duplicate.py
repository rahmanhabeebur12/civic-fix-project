"""
duplicate.py

Duplicate detection module for a crowdsourced civic issue reporting system.

This module determines whether two civic issue reports are likely to describe
the same physical problem.

It intentionally does NOT:
- validate whether a report is genuine
- calculate issue priority
- use a database
- use Flask
- use external APIs
- use machine-learning libraries

Python version: 3.10+
Standard library only.
"""

from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from typing import Any, Mapping


# ============================================================================
# CONFIGURATION
# ============================================================================

# Overall duplicate-score weights.
LOCATION_WEIGHT = 0.40
CATEGORY_WEIGHT = 0.25
DESCRIPTION_WEIGHT = 0.25
PHOTO_WEIGHT = 0.10


# ---------------------------------------------------------------------------
# Location distance thresholds in meters.
# These are intentionally kept as constants so they can be changed easily.
# ---------------------------------------------------------------------------

LOCATION_THRESHOLD_10_METERS = 10.0
LOCATION_THRESHOLD_25_METERS = 25.0
LOCATION_THRESHOLD_50_METERS = 50.0
LOCATION_THRESHOLD_100_METERS = 100.0
LOCATION_THRESHOLD_200_METERS = 200.0


# ---------------------------------------------------------------------------
# Location similarity scores.
# ---------------------------------------------------------------------------

LOCATION_SCORE_WITHIN_10_METERS = 100.0
LOCATION_SCORE_WITHIN_25_METERS = 90.0
LOCATION_SCORE_WITHIN_50_METERS = 75.0
LOCATION_SCORE_WITHIN_100_METERS = 50.0
LOCATION_SCORE_WITHIN_200_METERS = 25.0
LOCATION_SCORE_OVER_200_METERS = 0.0


# ---------------------------------------------------------------------------
# Duplicate confidence thresholds.
# ---------------------------------------------------------------------------

HIGH_CONFIDENCE_THRESHOLD = 80.0
POSSIBLE_DUPLICATE_THRESHOLD = 60.0


# Default minimum score for duplicate searches.
DEFAULT_MIN_DUPLICATE_SCORE = POSSIBLE_DUPLICATE_THRESHOLD


# ---------------------------------------------------------------------------
# Description similarity configuration.
# ---------------------------------------------------------------------------

# Jaccard similarity contributes most of the description score.
DESCRIPTION_JACCARD_WEIGHT = 0.70

# SequenceMatcher provides a small amount of ordering/string similarity.
DESCRIPTION_SEQUENCE_WEIGHT = 0.30


# Common English words that carry little information for civic issue
# descriptions. This is deliberately lightweight rather than a full NLP
# stop-word system.
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "near",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "with",
}


# ============================================================================
# VALIDATION HELPERS
# ============================================================================

def _is_valid_coordinate(value: Any, minimum: float, maximum: float) -> bool:
    """
    Return True if value can safely represent a numeric coordinate.

    Boolean values are rejected because bool is a subclass of int in Python
    but is not a meaningful geographic coordinate.
    """
    if isinstance(value, bool):
        return False

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return False

    return math.isfinite(numeric_value) and minimum <= numeric_value <= maximum


def _safe_float(value: Any) -> float | None:
    """
    Convert a value to a finite float.

    Return None if conversion fails or the result is not finite.
    """
    if isinstance(value, bool):
        return None

    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(numeric_value):
        return None

    return numeric_value


def _safe_report_value(report: Mapping[str, Any] | Any, key: str) -> Any:
    """
    Safely retrieve a value from a report-like object.

    A malformed report returns None instead of raising an exception.
    """
    if not isinstance(report, Mapping):
        return None

    try:
        return report.get(key)
    except (AttributeError, TypeError):
        return None


# ============================================================================
# GEOGRAPHIC SIMILARITY
# ============================================================================

def calculate_distance_meters(
    latitude1: Any,
    longitude1: Any,
    latitude2: Any,
    longitude2: Any,
) -> float:
    """
    Calculate the approximate distance between two geographic coordinates.

    The Haversine formula is used to calculate the great-circle distance
    between the coordinates.

    Parameters
    ----------
    latitude1, longitude1:
        Latitude and longitude of the first point.
    latitude2, longitude2:
        Latitude and longitude of the second point.

    Returns
    -------
    float
        Distance in meters.

        If any coordinate is missing or invalid, returns 0.0 safely.
        Returning zero here allows the caller to avoid crashing, while
        calculate_location_similarity can still treat malformed coordinates
        conservatively.

    Notes
    -----
    Valid latitude range: -90 to 90 degrees.
    Valid longitude range: -180 to 180 degrees.
    """
    if not _is_valid_coordinate(latitude1, -90.0, 90.0):
        return 0.0

    if not _is_valid_coordinate(longitude1, -180.0, 180.0):
        return 0.0

    if not _is_valid_coordinate(latitude2, -90.0, 90.0):
        return 0.0

    if not _is_valid_coordinate(longitude2, -180.0, 180.0):
        return 0.0

    lat1 = math.radians(float(latitude1))
    lon1 = math.radians(float(longitude1))
    lat2 = math.radians(float(latitude2))
    lon2 = math.radians(float(longitude2))

    delta_latitude = lat2 - lat1
    delta_longitude = lon2 - lon1

    # Haversine formula.
    haversine_a = (
        math.sin(delta_latitude / 2.0) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_longitude / 2.0) ** 2
    )

    # Floating-point rounding can theoretically make this very slightly
    # greater than 1. Clamp it to keep asin/sqrt calculations safe.
    haversine_a = min(1.0, max(0.0, haversine_a))

    central_angle = 2.0 * math.asin(math.sqrt(haversine_a))

    # Approximate mean radius of Earth in meters.
    earth_radius_meters = 6_371_000.0

    return earth_radius_meters * central_angle


def calculate_location_similarity(distance_meters: Any) -> float:
    """
    Convert geographic distance into a location similarity score from 0 to 100.

    Scoring:
        0-10 m       -> 100
        10-25 m      -> 90
        25-50 m      -> 75
        50-100 m     -> 50
        100-200 m    -> 25
        >200 m       -> 0

    Invalid distances safely return 0.
    """
    distance = _safe_float(distance_meters)

    if distance is None or distance < 0.0:
        return 0.0

    if distance <= LOCATION_THRESHOLD_10_METERS:
        return LOCATION_SCORE_WITHIN_10_METERS

    if distance <= LOCATION_THRESHOLD_25_METERS:
        return LOCATION_SCORE_WITHIN_25_METERS

    if distance <= LOCATION_THRESHOLD_50_METERS:
        return LOCATION_SCORE_WITHIN_50_METERS

    if distance <= LOCATION_THRESHOLD_100_METERS:
        return LOCATION_SCORE_WITHIN_100_METERS

    if distance <= LOCATION_THRESHOLD_200_METERS:
        return LOCATION_SCORE_WITHIN_200_METERS

    return LOCATION_SCORE_OVER_200_METERS


# ============================================================================
# CATEGORY SIMILARITY
# ============================================================================

def calculate_category_similarity(
    category1: Any,
    category2: Any,
) -> float:
    """
    Compare two civic issue categories.

    Categories are compared case-insensitively after removing surrounding
    whitespace.

    Returns
    -------
    float
        100.0 for matching categories and 0.0 otherwise.
    """
    if not isinstance(category1, str) or not isinstance(category2, str):
        return 0.0

    normalized_category1 = category1.strip().casefold()
    normalized_category2 = category2.strip().casefold()

    if not normalized_category1 or not normalized_category2:
        return 0.0

    return 100.0 if normalized_category1 == normalized_category2 else 0.0


# ============================================================================
# DESCRIPTION SIMILARITY
# ============================================================================

def _tokenize_description(description: Any) -> list[str]:
    """
    Normalize and tokenize a description.

    Processing includes:
    - conversion to lowercase
    - punctuation removal
    - whitespace normalization
    - stop-word removal

    Returns an empty list for invalid or empty descriptions.
    """
    if not isinstance(description, str):
        return []

    normalized_text = description.casefold()

    # Replace punctuation and other non-word characters with spaces.
    normalized_text = re.sub(r"[^\w\s]", " ", normalized_text)

    # Split on any sequence of whitespace characters.
    raw_tokens = normalized_text.split()

    tokens = [
        token
        for token in raw_tokens
        if token and token not in STOP_WORDS
    ]

    return tokens


def calculate_description_similarity(
    description1: Any,
    description2: Any,
) -> float:
    """
    Calculate lightweight description similarity from 0 to 100.

    The algorithm uses two standard-library techniques:

    1. Jaccard similarity between the unique meaningful words.
    2. SequenceMatcher similarity between normalized descriptions.

    Jaccard similarity is weighted more heavily because matching important
    words is useful for civic reports. SequenceMatcher provides some additional
    sensitivity to similar wording and word ordering.

    No external NLP or machine-learning library is required.

    Empty or invalid descriptions return 0.0.
    """
    tokens1 = _tokenize_description(description1)
    tokens2 = _tokenize_description(description2)

    if not tokens1 or not tokens2:
        return 0.0

    token_set1 = set(tokens1)
    token_set2 = set(tokens2)

    intersection_size = len(token_set1.intersection(token_set2))
    union_size = len(token_set1.union(token_set2))

    if union_size == 0:
        jaccard_similarity = 0.0
    else:
        jaccard_similarity = intersection_size / union_size

    # Use meaningful normalized tokens for the sequence comparison.
    normalized1 = " ".join(tokens1)
    normalized2 = " ".join(tokens2)

    sequence_similarity = SequenceMatcher(
        None,
        normalized1,
        normalized2,
    ).ratio()

    combined_similarity = (
        jaccard_similarity * DESCRIPTION_JACCARD_WEIGHT
        + sequence_similarity * DESCRIPTION_SEQUENCE_WEIGHT
    )

    return max(0.0, min(100.0, combined_similarity * 100.0))


# ============================================================================
# PHOTO SIMILARITY
# ============================================================================

def calculate_photo_similarity(
    photo_path1: Any,
    photo_path2: Any,
) -> float:
    """
    Return the current placeholder photo similarity score.

    Photo comparison is intentionally not implemented yet.
    """
    # TODO: FUTURE AI IMAGE SIMILARITY
    # Replace this placeholder with a computer-vision/image-embedding
    # system that compares two uploaded images and returns a similarity
    # score from 0 to 100.
    #
    # Possible future approaches:
    # - perceptual hashing
    # - image embeddings
    # - CLIP/image similarity
    # - computer-vision feature matching

    return 50.0


# ============================================================================
# DUPLICATE SCORE
# ============================================================================

def _round_score(score: float) -> float | int:
    """
    Round a score for cleaner API output.

    Whole-number scores are returned as integers; otherwise one decimal
    place is retained.
    """
    rounded = round(score, 1)

    if rounded.is_integer():
        return int(rounded)

    return rounded


def calculate_duplicate_score(
    new_report: Mapping[str, Any] | Any,
    existing_report: Mapping[str, Any] | Any,
) -> dict[str, Any]:
    """
    Calculate the duplicate score between two civic reports.

    Formula:

        duplicate_score =
            location_similarity * 0.40
          + category_similarity * 0.25
          + description_similarity * 0.25
          + photo_similarity * 0.10

    Returns
    -------
    dict
        Contains the final duplicate score, duplicate flag, confidence,
        individual factor scores, and geographic distance.
    """
    new_latitude = _safe_report_value(new_report, "latitude")
    new_longitude = _safe_report_value(new_report, "longitude")

    existing_latitude = _safe_report_value(existing_report, "latitude")
    existing_longitude = _safe_report_value(existing_report, "longitude")

    # Calculate distance.
    distance_meters = calculate_distance_meters(
        new_latitude,
        new_longitude,
        existing_latitude,
        existing_longitude,
    )

    # Missing/invalid coordinates should not accidentally receive a perfect
    # location score merely because calculate_distance_meters safely returned
    # 0.0.
    coordinates_valid = (
        _is_valid_coordinate(new_latitude, -90.0, 90.0)
        and _is_valid_coordinate(new_longitude, -180.0, 180.0)
        and _is_valid_coordinate(existing_latitude, -90.0, 90.0)
        and _is_valid_coordinate(existing_longitude, -180.0, 180.0)
    )

    if coordinates_valid:
        location_similarity = calculate_location_similarity(distance_meters)
    else:
        location_similarity = 0.0

    category_similarity = calculate_category_similarity(
        _safe_report_value(new_report, "category"),
        _safe_report_value(existing_report, "category"),
    )

    description_similarity = calculate_description_similarity(
        _safe_report_value(new_report, "description"),
        _safe_report_value(existing_report, "description"),
    )

    photo_similarity = calculate_photo_similarity(
        _safe_report_value(new_report, "photo_path"),
        _safe_report_value(existing_report, "photo_path"),
    )

    duplicate_score = (
        location_similarity * LOCATION_WEIGHT
        + category_similarity * CATEGORY_WEIGHT
        + description_similarity * DESCRIPTION_WEIGHT
        + photo_similarity * PHOTO_WEIGHT
    )

    # Keep the final score safely within the required range.
    duplicate_score = max(0.0, min(100.0, duplicate_score))

    confidence = get_duplicate_confidence(duplicate_score)

    return {
        "duplicate_score": _round_score(duplicate_score),
        "is_duplicate": confidence == "HIGH",
        "confidence": confidence,
        "breakdown": {
            "location": _round_score(location_similarity),
            "category": _round_score(category_similarity),
            "description": _round_score(description_similarity),
            "photo": _round_score(photo_similarity),
        },
        "distance_meters": round(distance_meters, 1),
    }


# ============================================================================
# CONFIDENCE
# ============================================================================

def get_duplicate_confidence(score: Any) -> str:
    """
    Convert a duplicate score into a confidence category.

    Returns:
        "HIGH"     -> score >= 80
        "POSSIBLE" -> score >= 60 and below 80
        "NONE"     -> score below 60

    Invalid scores return "NONE".
    """
    numeric_score = _safe_float(score)

    if numeric_score is None:
        return "NONE"

    numeric_score = max(0.0, min(100.0, numeric_score))

    if numeric_score >= HIGH_CONFIDENCE_THRESHOLD:
        return "HIGH"

    if numeric_score >= POSSIBLE_DUPLICATE_THRESHOLD:
        return "POSSIBLE"

    return "NONE"


# ============================================================================
# FIND DUPLICATES
# ============================================================================

def find_duplicates(
    new_report: Mapping[str, Any] | Any,
    existing_reports: Any,
    min_score: float = DEFAULT_MIN_DUPLICATE_SCORE,
) -> list[dict[str, Any]]:
    """
    Find existing reports that may be duplicates of a new report.

    Parameters
    ----------
    new_report:
        The newly submitted civic issue report.
    existing_reports:
        Iterable containing existing report dictionaries.
    min_score:
        Minimum duplicate score required for a result to be returned.

    Returns
    -------
    list[dict]
        Matching reports sorted from highest duplicate score to lowest.

    Malformed reports are skipped safely.
    """
    minimum_score = _safe_float(min_score)

    if minimum_score is None:
        minimum_score = DEFAULT_MIN_DUPLICATE_SCORE

    minimum_score = max(0.0, min(100.0, minimum_score))

    if not isinstance(existing_reports, (list, tuple)):
        return []

    new_report_id = _safe_report_value(new_report, "id")

    matches: list[dict[str, Any]] = []

    for existing_report in existing_reports:
        if not isinstance(existing_report, Mapping):
            continue

        existing_report_id = _safe_report_value(existing_report, "id")

        # Ignore comparison with itself when IDs match.
        if (
            new_report_id is not None
            and existing_report_id is not None
            and new_report_id == existing_report_id
        ):
            continue

        try:
            score_result = calculate_duplicate_score(
                new_report,
                existing_report,
            )
        except Exception:
            # Defensive protection for future changes or unusual input
            # objects. One malformed record should not stop the whole search.
            continue

        numeric_score = _safe_float(
            score_result.get("duplicate_score")
        )

        if numeric_score is None:
            continue

        if numeric_score >= minimum_score:
            matches.append(
                {
                    "existing_report_id": existing_report_id,
                    "duplicate_score": score_result["duplicate_score"],
                    "confidence": score_result["confidence"],
                    "distance_meters": score_result["distance_meters"],
                    "breakdown": score_result["breakdown"],
                }
            )

    matches.sort(
        key=lambda result: float(result["duplicate_score"]),
        reverse=True,
    )

    return matches


# ============================================================================
# BEST MATCH
# ============================================================================

def find_best_duplicate(
    new_report: Mapping[str, Any] | Any,
    existing_reports: Any,
) -> dict[str, Any] | None:
    """
    Return the highest-scoring possible duplicate.

    A report must reach DEFAULT_MIN_DUPLICATE_SCORE to be considered.

    Returns None when no existing report reaches the minimum threshold.
    """
    duplicates = find_duplicates(
        new_report,
        existing_reports,
        min_score=DEFAULT_MIN_DUPLICATE_SCORE,
    )

    if not duplicates:
        return None

    return duplicates[0]


# ============================================================================
# MERGE / LINK RECOMMENDATION
# ============================================================================

def get_duplicate_recommendation(
    new_report: Mapping[str, Any] | Any,
    existing_reports: Any,
) -> dict[str, Any]:
    """
    Recommend whether to create a new issue, review a possible duplicate,
    or link the report to an existing issue.

    Rules:
        HIGH     -> LINK_TO_EXISTING
        POSSIBLE -> REVIEW
        NONE     -> CREATE_NEW

    Possible duplicates are intentionally NOT merged automatically.
    """
    best_match = find_best_duplicate(
        new_report,
        existing_reports,
    )

    if best_match is None:
        return {
            "action": "CREATE_NEW",
            "matched_report_id": None,
            "duplicate_score": 0,
            "confidence": "NONE",
        }

    confidence = best_match["confidence"]

    if confidence == "HIGH":
        return {
            "action": "LINK_TO_EXISTING",
            "matched_report_id": best_match["existing_report_id"],
            "duplicate_score": best_match["duplicate_score"],
            "confidence": confidence,
        }

    if confidence == "POSSIBLE":
        return {
            "action": "REVIEW",
            "matched_report_id": best_match["existing_report_id"],
            "duplicate_score": best_match["duplicate_score"],
            "confidence": confidence,
        }

    return {
        "action": "CREATE_NEW",
        "matched_report_id": None,
        "duplicate_score": best_match["duplicate_score"],
        "confidence": "NONE",
    }


# ============================================================================
# FUTURE DATABASE INTEGRATION
# ============================================================================
#
# FUTURE DATABASE INTEGRATION:
# existing_reports will eventually come from the database.
#
# For example, a Flask route could later:
#
#   1. Receive a new report.
#   2. Query nearby/existing reports from the database.
#   3. Pass those reports to find_duplicates().
#   4. Use get_duplicate_recommendation() to decide whether the report
#      should be linked, reviewed, or created as a new issue.
#
# No database logic is implemented in this module.


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    """
    Basic standalone tests.

    These tests intentionally use ordinary dictionaries so the module can
    later be integrated with Flask/database models without changing the
    duplicate-detection functions.
    """

    # ------------------------------------------------------------------------
    # Existing reports used by the test cases.
    # ------------------------------------------------------------------------

    existing_reports = [
        {
            "id": 101,
            "user_id": 10,
            "category": "pothole",
            "description": "Large hole in road near school",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "photo_path": "uploads/pothole101.jpg",
            "created_at": "2026-08-27T09:00:00",
        },
        {
            "id": 102,
            "user_id": 11,
            "category": "pothole",
            "description": "Damaged road with a deep pothole",
            "latitude": 13.0835,
            "longitude": 80.2715,
            "photo_path": "uploads/pothole102.jpg",
            "created_at": "2026-08-27T09:30:00",
        },
        {
            "id": 103,
            "user_id": 12,
            "category": "streetlight",
            "description": "Street light is not working near school",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "photo_path": "uploads/light103.jpg",
            "created_at": "2026-08-27T09:45:00",
        },
        {
            "id": 104,
            "user_id": 13,
            "category": "pothole",
            "description": "Large pothole on another road",
            "latitude": 13.1000,
            "longitude": 80.3000,
            "photo_path": "uploads/pothole104.jpg",
            "created_at": "2026-08-27T08:30:00",
        },
    ]

    # ------------------------------------------------------------------------
    # TEST 1:
    # Same category, very close location, highly similar description.
    # Expected: HIGH duplicate probability.
    # ------------------------------------------------------------------------

    test_1 = {
        "id": 120,
        "user_id": 25,
        "category": "Pothole",
        "description": "Large pothole near the school",
        "latitude": 13.0828,
        "longitude": 80.2708,
        "photo_path": "uploads/pothole120.jpg",
        "created_at": "2026-08-27T10:30:00",
    }

    # ------------------------------------------------------------------------
    # TEST 2:
    # Same category, moderately close location, somewhat similar description.
    # Expected: POSSIBLE duplicate.
    #
    # The exact result depends on the configured thresholds and text
    # similarity. The test demonstrates the intended workflow.
    # ------------------------------------------------------------------------

    test_2 = {
        "id": 121,
        "user_id": 26,
        "category": "pothole",
        "description": "Road has a damaged section with a hole",
        "latitude": 13.0838,
        "longitude": 80.2718,
        "photo_path": "uploads/pothole121.jpg",
        "created_at": "2026-08-27T10:40:00",
    }

    # ------------------------------------------------------------------------
    # TEST 3:
    # Different category but same location.
    # Expected: NOT duplicate because category similarity is zero.
    # ------------------------------------------------------------------------

    test_3 = {
        "id": 122,
        "user_id": 27,
        "category": "streetlight",
        "description": "Street light problem near the school",
        "latitude": 13.0828,
        "longitude": 80.2708,
        "photo_path": "uploads/light122.jpg",
        "created_at": "2026-08-27T10:50:00",
    }

    # ------------------------------------------------------------------------
    # TEST 4:
    # Same category but very far away.
    # Expected: NOT duplicate.
    # ------------------------------------------------------------------------

    test_4 = {
        "id": 123,
        "user_id": 28,
        "category": "pothole",
        "description": "Large pothole on the road",
        "latitude": 13.1500,
        "longitude": 80.3500,
        "photo_path": "uploads/pothole123.jpg",
        "created_at": "2026-08-27T11:00:00",
    }

    # ------------------------------------------------------------------------
    # TEST 5:
    # Missing/invalid data.
    # Expected: No crash.
    # ------------------------------------------------------------------------

    test_5 = {
        "id": 124,
        "user_id": 29,
        "category": None,
        "description": None,
        "latitude": "not-a-number",
        "longitude": None,
        "photo_path": None,
        "created_at": None,
    }

    tests = [
        ("TEST 1 - HIGH duplicate probability", test_1),
        ("TEST 2 - POSSIBLE duplicate", test_2),
        ("TEST 3 - Different category", test_3),
        ("TEST 4 - Very far away", test_4),
        ("TEST 5 - Missing/invalid data", test_5),
    ]

    print("=" * 72)
    print("CIVIC ISSUE DUPLICATE DETECTION TESTS")
    print("=" * 72)

    for test_name, test_report in tests:
        print(f"\n{test_name}")
        print("-" * 72)

        try:
            best_match = find_best_duplicate(
                test_report,
                existing_reports,
            )

            recommendation = get_duplicate_recommendation(
                test_report,
                existing_reports,
            )

            if best_match is None:
                print("Best match: None")
            else:
                print(f"Best match report ID: {best_match['existing_report_id']}")
                print(f"Duplicate score: {best_match['duplicate_score']}")
                print(f"Confidence: {best_match['confidence']}")
                print(f"Distance: {best_match['distance_meters']} meters")
                print(f"Breakdown: {best_match['breakdown']}")

            print(f"Recommendation: {recommendation}")

        except Exception as error:
            # The test suite itself should not terminate because of malformed
            # test input.
            print(f"Unexpected test error: {error}")

    print("\n" + "=" * 72)
    print("DIRECT FUNCTION TEST")
    print("=" * 72)

    distance = calculate_distance_meters(
        13.0827,
        80.2707,
        13.0828,
        80.2708,
    )

    print(f"Example Haversine distance: {distance:.2f} meters")

    print(
        "Example description similarity:",
        calculate_description_similarity(
            "large pothole near school",
            "huge pothole near the school",
        ),
    )

    print(
        "Example category similarity:",
        calculate_category_similarity(
            "Pothole",
            "pothole",
        ),
    )

    print("\nAll standalone tests completed.")