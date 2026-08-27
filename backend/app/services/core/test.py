"""
test.py

Test suite for the crowdsourced civic issue reporting system prototype.

This file tests the following modules WITHOUT modifying them:

    - validator.py  (calculate_validity)
    - priority.py   (calculate_priority, get_priority_level)
    - duplicate.py  (distance / similarity / duplicate-score / search helpers)

It also runs an integration test that chains the three modules together in a
realistic workflow:

    REPORT -> VALIDITY -> DUPLICATE CHECK -> PRIORITY -> FINAL DECISION

Run with:

    python test.py

Python 3.10+, standard library only (unittest).
"""

from __future__ import annotations

import unittest
from typing import Any, Dict

import validator
import priority
import duplicate


# ============================================================================
# SHARED STATUS / LEVEL VOCABULARIES
# ============================================================================

VALIDATOR_STATUSES = {"VALID", "REVIEW", "SUSPICIOUS"}
PRIORITY_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
DUPLICATE_CONFIDENCES = {"HIGH", "POSSIBLE", "NONE"}


# ============================================================================
# TEST DATA HELPERS
# ============================================================================

def make_valid_report(**overrides: Any) -> Dict[str, Any]:
    """Build a realistic, well-formed civic issue report for reuse in tests."""
    report = {
        "user_id": 101,
        "description": "Large pothole on the road near the school",
        "category": "pothole",
        "photo_path": "test_pothole.jpg",
        "latitude": 13.0827,
        "longitude": 80.2707,
        "timestamp": "2026-08-27T10:30:00",
        "number_of_previous_reports": 4,
        "user_previous_reports": 5,
    }
    report.update(overrides)
    return report


def make_valid_issue(**overrides: Any) -> Dict[str, Any]:
    """Build a realistic, well-formed civic issue for the priority module."""
    issue = {
        "severity": 1,
        "number_of_reporters": 1,
        "location_type": "normal_area",
        "created_at": "2026-08-27T10:00:00",
        "impact_level": 1,
    }
    issue.update(overrides)
    return issue


# ============================================================================
# VALIDATOR TESTS
# ============================================================================

class TestValidator(unittest.TestCase):
    """Tests for validator.calculate_validity()."""

    def test_valid_report_returns_structured_result(self) -> None:
        """A well-formed report should not crash and should return a full result."""
        report = make_valid_report()

        result = validator.calculate_validity(report)

        self.assertIsInstance(result, dict)
        self.assertIn("validity_score", result)
        self.assertIn("status", result)
        self.assertIn("breakdown", result)

        score = result["validity_score"]
        self.assertIsInstance(score, (int, float))
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

        self.assertIn(result["status"], VALIDATOR_STATUSES)
        self.assertIsInstance(result["breakdown"], dict)
        self.assertGreater(len(result["breakdown"]), 0)

    def test_missing_required_fields_does_not_crash(self) -> None:
        """Missing description, photo, and latitude should be handled safely."""
        report = make_valid_report()
        del report["description"]
        del report["photo_path"]
        del report["latitude"]

        result = validator.calculate_validity(report)

        self.assertIsInstance(result, dict)
        score = result["validity_score"]
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)

        # Missing required fields should not be able to reach a full "VALID"
        # status, and should produce recorded validation errors.
        self.assertNotEqual(result["status"], "VALID")
        self.assertTrue(len(result["validation_errors"]) > 0)

    def test_invalid_gps_handled_safely(self) -> None:
        """Wildly out-of-range coordinates must not crash the validator."""
        report = make_valid_report(latitude=200, longitude=500)

        result = validator.calculate_validity(report)

        self.assertIsInstance(result, dict)
        score = result["validity_score"]
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)
        self.assertIn(result["status"], VALIDATOR_STATUSES)
        self.assertTrue(len(result["validation_errors"]) > 0)

    def test_suspicious_spam_like_report_scores_lower(self) -> None:
        """A spam-like report should score lower than a clean, valid report."""
        clean_report = make_valid_report()
        spammy_report = make_valid_report(
            description="!!!",
            photo_path="",
            number_of_previous_reports=0,
            user_previous_reports=250,
        )

        clean_result = validator.calculate_validity(clean_report)
        spammy_result = validator.calculate_validity(spammy_report)

        self.assertIsInstance(spammy_result, dict)
        self.assertIn(spammy_result["status"], VALIDATOR_STATUSES)
        self.assertLess(
            spammy_result["validity_score"],
            clean_result["validity_score"],
        )
        self.assertNotEqual(spammy_result["status"], "VALID")

    def test_duplicate_evidence_does_not_force_invalid_result(self) -> None:
        """Multiple prior reports of the same issue must not force an invalid result."""
        report = make_valid_report(number_of_previous_reports=6, user_previous_reports=8)

        result = validator.calculate_validity(report)

        self.assertIsInstance(result, dict)
        self.assertIn("validity_score", result)
        self.assertIn("status", result)
        self.assertIn(result["status"], VALIDATOR_STATUSES)
        self.assertGreaterEqual(result["validity_score"], 0)
        self.assertLessEqual(result["validity_score"], 100)


# ============================================================================
# PRIORITY TESTS
# ============================================================================

class TestPriority(unittest.TestCase):
    """Tests for priority.calculate_priority() and priority.get_priority_level()."""

    def test_low_priority_structure(self) -> None:
        """A minor issue should return a fully structured, in-range result."""
        issue = make_valid_issue(
            severity=1,
            number_of_reporters=1,
            location_type="normal_area",
            created_at="2026-08-27T10:00:00",
            impact_level=1,
        )

        result = priority.calculate_priority(issue)

        self.assertIsInstance(result, dict)
        self.assertIn("priority_score", result)
        self.assertIn("priority_level", result)
        self.assertIn("breakdown", result)

        self.assertGreaterEqual(result["priority_score"], 0)
        self.assertLessEqual(result["priority_score"], 100)
        self.assertIn(result["priority_level"], PRIORITY_LEVELS)
        self.assertIsInstance(result["breakdown"], dict)

    def test_high_priority_scores_above_low_priority(self) -> None:
        """A serious, well-reported issue should outrank a minor one."""
        low_issue = make_valid_issue(
            severity=1,
            number_of_reporters=1,
            location_type="normal_area",
            created_at="2026-08-27T10:00:00",
            impact_level=1,
        )
        high_issue = make_valid_issue(
            severity=4,
            number_of_reporters=8,
            location_type="busy_road",
            created_at="2026-08-26T10:00:00",
            impact_level=4,
        )

        low_result = priority.calculate_priority(low_issue)
        high_result = priority.calculate_priority(high_issue)

        self.assertGreater(
            high_result["priority_score"],
            low_result["priority_score"],
        )

    def test_critical_emergency_override(self) -> None:
        """Severity 5 at a sensitive location must trigger the emergency floor."""
        emergency_issue = make_valid_issue(
            severity=5,
            number_of_reporters=8,
            location_type="school",
            created_at="2026-08-25T10:00:00",
            impact_level=5,
        )

        result = priority.calculate_priority(emergency_issue)

        self.assertGreaterEqual(result["priority_score"], 90)
        self.assertEqual(result["priority_level"], "CRITICAL")

    def test_invalid_priority_input_does_not_crash(self) -> None:
        """Missing/invalid severity, reporters, impact, location and timestamp are safe."""
        malformed_issue = {
            "severity": "not-a-number",
            "number_of_reporters": -5,
            "location_type": None,
            "created_at": "not-a-timestamp",
            "impact_level": None,
        }

        result = priority.calculate_priority(malformed_issue)

        self.assertIsInstance(result, dict)
        self.assertGreaterEqual(result["priority_score"], 0)
        self.assertLessEqual(result["priority_score"], 100)
        self.assertIn(result["priority_level"], PRIORITY_LEVELS)

        # Also confirm a completely empty issue does not crash.
        empty_result = priority.calculate_priority({})
        self.assertIsInstance(empty_result, dict)
        self.assertIn(empty_result["priority_level"], PRIORITY_LEVELS)

    def test_priority_level_boundaries(self) -> None:
        """get_priority_level() must map scores to the documented bands."""
        expected = {
            49: "LOW",
            50: "MEDIUM",
            74: "MEDIUM",
            75: "HIGH",
            89: "HIGH",
            90: "CRITICAL",
            100: "CRITICAL",
        }

        for score, expected_level in expected.items():
            with self.subTest(score=score):
                self.assertEqual(
                    priority.get_priority_level(score),
                    expected_level,
                )


# ============================================================================
# DUPLICATE TESTS
# ============================================================================

class TestDuplicate(unittest.TestCase):
    """Tests for duplicate.py's distance, similarity, and search helpers."""

    def setUp(self) -> None:
        # Deliberately near-identical wording/location so this pair reliably
        # reaches HIGH duplicate confidence across all four scoring factors.
        self.strong_duplicate_new = {
            "id": 120,
            "category": "pothole",
            "description": "Large pothole blocking the road near the main school gate",
            "latitude": 13.0828,
            "longitude": 80.2708,
            "photo_path": "pothole120.jpg",
        }
        self.strong_duplicate_existing = {
            "id": 101,
            "category": "pothole",
            "description": "Large pothole blocking road near the main school gate",
            "latitude": 13.0827,
            "longitude": 80.2707,
            "photo_path": "pothole101.jpg",
        }

    def test_strong_duplicate_is_flagged_high_confidence(self) -> None:
        """Nearly identical location, category, and description should score high."""
        result = duplicate.calculate_duplicate_score(
            self.strong_duplicate_new,
            self.strong_duplicate_existing,
        )

        self.assertIn("distance_meters", result)
        self.assertGreaterEqual(result["distance_meters"], 0)

        self.assertIn("duplicate_score", result)
        self.assertGreaterEqual(result["duplicate_score"], 0)
        self.assertLessEqual(result["duplicate_score"], 100)

        self.assertIn("breakdown", result)
        self.assertIn(result["confidence"], DUPLICATE_CONFIDENCES)
        self.assertEqual(result["confidence"], "HIGH")

    def test_different_category_is_not_high_confidence(self) -> None:
        """Same location but different category should not be a high-confidence duplicate."""
        new_report = dict(self.strong_duplicate_new, category="pothole")
        existing_report = dict(self.strong_duplicate_existing, category="streetlight")

        result = duplicate.calculate_duplicate_score(new_report, existing_report)

        self.assertNotEqual(result["confidence"], "HIGH")

    def test_far_away_issue_is_not_high_confidence(self) -> None:
        """Same category/description but far apart should not be a high-confidence duplicate."""
        far_existing = dict(
            self.strong_duplicate_existing,
            latitude=13.2000,
            longitude=80.5000,
        )

        result = duplicate.calculate_duplicate_score(
            self.strong_duplicate_new,
            far_existing,
        )

        self.assertNotEqual(result["confidence"], "HIGH")

    def test_similar_descriptions_have_positive_similarity(self) -> None:
        """Descriptions describing the same event should score above zero similarity."""
        similarity = duplicate.calculate_description_similarity(
            "Large pothole near school",
            "Huge hole in road outside the school",
        )

        self.assertGreater(similarity, 0)
        self.assertLessEqual(similarity, 100)

    def test_invalid_data_does_not_crash(self) -> None:
        """Missing/invalid coordinates and descriptions must be handled safely."""
        broken_new = {
            "id": 999,
            "category": None,
            "description": None,
            "latitude": "not-a-number",
            "longitude": None,
            "photo_path": None,
        }
        broken_existing = {
            "id": 998,
            "category": None,
            "description": None,
            "latitude": None,
            "longitude": "invalid",
            "photo_path": None,
        }

        result = duplicate.calculate_duplicate_score(broken_new, broken_existing)

        self.assertIsInstance(result, dict)
        self.assertGreaterEqual(result["duplicate_score"], 0)
        self.assertLessEqual(result["duplicate_score"], 100)
        self.assertIn(result["confidence"], DUPLICATE_CONFIDENCES)

    def test_find_duplicates_returns_sorted_results_excluding_self(self) -> None:
        """find_duplicates() should return sorted matches and skip the report's own id."""
        new_report = self.strong_duplicate_new

        possible_duplicate = {
            "id": 121,
            "category": "pothole",
            "description": "Road has a damaged section with a hole",
            "latitude": 13.0838,
            "longitude": 80.2718,
            "photo_path": "pothole121.jpg",
        }
        unrelated_report = {
            "id": 122,
            "category": "streetlight",
            "description": "Street light is not working",
            "latitude": 13.5000,
            "longitude": 80.9000,
            "photo_path": "light122.jpg",
        }
        # Same id as the new report: must never be returned as its own duplicate.
        self_report = dict(new_report)

        existing_reports = [
            self.strong_duplicate_existing,
            possible_duplicate,
            unrelated_report,
            self_report,
        ]

        matches = duplicate.find_duplicates(new_report, existing_reports)

        self.assertIsInstance(matches, list)

        matched_ids = [match["existing_report_id"] for match in matches]
        self.assertNotIn(new_report["id"], matched_ids)

        scores = [float(match["duplicate_score"]) for match in matches]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_find_best_duplicate_returns_strongest_match(self) -> None:
        """find_best_duplicate() should return the single highest-scoring match."""
        new_report = self.strong_duplicate_new

        possible_duplicate = {
            "id": 121,
            "category": "pothole",
            "description": "Road has a damaged section with a hole",
            "latitude": 13.0838,
            "longitude": 80.2718,
            "photo_path": "pothole121.jpg",
        }
        unrelated_report = {
            "id": 122,
            "category": "streetlight",
            "description": "Street light is not working",
            "latitude": 13.5000,
            "longitude": 80.9000,
            "photo_path": "light122.jpg",
        }

        existing_reports = [
            self.strong_duplicate_existing,
            possible_duplicate,
            unrelated_report,
        ]

        best_match = duplicate.find_best_duplicate(new_report, existing_reports)
        all_matches = duplicate.find_duplicates(new_report, existing_reports)

        self.assertIsNotNone(best_match)
        self.assertEqual(
            best_match["existing_report_id"],
            self.strong_duplicate_existing["id"],
        )
        # The best match must be the top of the fully sorted match list.
        self.assertEqual(best_match, all_matches[0])


# ============================================================================
# INTEGRATION TEST
# ============================================================================

class TestIntegration(unittest.TestCase):
    """
    End-to-end workflow test chaining validator -> duplicate -> priority.

    Workflow:

        REPORT
          |
          v
        VALIDITY  (validator.calculate_validity)
          |
          v
        DUPLICATE CHECK  (duplicate.find_best_duplicate)
          |
          v
        PRIORITY  (priority.calculate_priority)
          |
          v
        FINAL DECISION
    """

    def test_full_civic_issue_workflow(self) -> None:
        new_report = {
            "id": 200,
            "user_id": 50,
            "description": (
                "Large pothole near school entrance causing vehicles to slow down"
            ),
            "category": "pothole",
            "photo_path": "pothole200.jpg",
            "latitude": 13.0828,
            "longitude": 80.2708,
            "timestamp": "2026-08-27T10:30:00",
            "number_of_previous_reports": 5,
            "user_previous_reports": 3,
            "severity": 5,
            "location_type": "school",
            "impact_level": 5,
        }

        existing_reports = [
            {
                "id": 101,
                "category": "pothole",
                "description": "Large hole in road near school",
                "latitude": 13.0827,
                "longitude": 80.2707,
                "photo_path": "pothole101.jpg",
            },
            {
                "id": 102,
                "category": "streetlight",
                "description": "Street light is not working",
                "latitude": 13.5000,
                "longitude": 80.9000,
                "photo_path": "light102.jpg",
            },
        ]

        # STEP 1: Validity
        validity_result = validator.calculate_validity(new_report)

        self.assertIsInstance(validity_result, dict)
        self.assertIn(validity_result["status"], VALIDATOR_STATUSES)
        self.assertGreaterEqual(validity_result["validity_score"], 0)
        self.assertLessEqual(validity_result["validity_score"], 100)

        # STEP 2: Duplicate check — only run if the report clears review.
        best_duplicate = None
        if validity_result["status"] in ("VALID", "REVIEW"):
            best_duplicate = duplicate.find_best_duplicate(
                new_report,
                existing_reports,
            )

        # STEP 3: Priority (assumes the caller has already validated the report).
        priority_result = priority.calculate_priority(new_report)

        self.assertIsInstance(priority_result, dict)
        self.assertIn(priority_result["priority_level"], PRIORITY_LEVELS)
        self.assertGreaterEqual(priority_result["priority_score"], 0)
        self.assertLessEqual(priority_result["priority_score"], 100)

        # This report is a severe (severity 5) issue at a school, so the
        # emergency override should guarantee a CRITICAL priority.
        self.assertEqual(priority_result["priority_level"], "CRITICAL")

        # STEP 4: Final decision summary.
        if best_duplicate is not None:
            duplicate_score = best_duplicate["duplicate_score"]
            duplicate_confidence = best_duplicate["confidence"]
            if duplicate_confidence == "HIGH":
                final_recommendation = "LINK_TO_EXISTING"
            elif duplicate_confidence == "POSSIBLE":
                final_recommendation = "REVIEW"
            else:
                final_recommendation = "CREATE_NEW"
        else:
            duplicate_score = 0
            duplicate_confidence = "NONE"
            final_recommendation = "CREATE_NEW"

        self.assertIn(
            final_recommendation,
            {"LINK_TO_EXISTING", "REVIEW", "CREATE_NEW"},
        )

        print("\n" + "=" * 40)
        print("CIVIC ISSUE INTEGRATION TEST")
        print("=" * 40)
        print(f"Validity Score: {validity_result['validity_score']}")
        print(f"Validity Status: {validity_result['status']}")
        print()
        print(f"Duplicate Score: {duplicate_score}")
        print(f"Duplicate Confidence: {duplicate_confidence}")
        print()
        print(f"Priority Score: {priority_result['priority_score']}")
        print(f"Priority Level: {priority_result['priority_level']}")
        print()
        print("Final Recommendation:")
        print(final_recommendation)
        print("=" * 40)

    def test_workflow_handles_empty_report_without_crashing(self) -> None:
        """The full pipeline must fail safely, not crash, on an empty report."""
        empty_report: Dict[str, Any] = {}

        validity_result = validator.calculate_validity(empty_report)
        self.assertIsInstance(validity_result, dict)
        self.assertIn(validity_result["status"], VALIDATOR_STATUSES)

        best_duplicate = duplicate.find_best_duplicate(empty_report, [])
        self.assertIsNone(best_duplicate)

        priority_result = priority.calculate_priority(empty_report)
        self.assertIsInstance(priority_result, dict)
        self.assertIn(priority_result["priority_level"], PRIORITY_LEVELS)


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases(unittest.TestCase):
    """
    Cross-module edge-case tests.

    Goal: confirm every module fails safely (returns structured, in-range
    output) rather than raising an unhandled exception.
    """

    def test_validator_edge_cases(self) -> None:
        edge_reports = [
            {},
            {"description": None, "category": None, "photo_path": None,
             "latitude": None, "longitude": None},
            {"description": 12345, "category": "pothole", "photo_path": "x.jpg",
             "latitude": "not-a-number", "longitude": "not-a-number"},
            make_valid_report(description=""),
            make_valid_report(category="unknown_category"),
            make_valid_report(number_of_previous_reports=-5),
            make_valid_report(timestamp="not-a-timestamp"),
        ]

        for report in edge_reports:
            with self.subTest(report=report):
                result = validator.calculate_validity(report)
                self.assertIsInstance(result, dict)
                self.assertIn(result["status"], VALIDATOR_STATUSES)
                self.assertGreaterEqual(result["validity_score"], 0)
                self.assertLessEqual(result["validity_score"], 100)

    def test_priority_edge_cases(self) -> None:
        edge_issues = [
            {},
            {"severity": None, "number_of_reporters": None,
             "location_type": None, "created_at": None, "impact_level": None},
            {"severity": -1, "number_of_reporters": -10,
             "location_type": "unknown_place", "created_at": "invalid",
             "impact_level": 99},
            make_valid_issue(location_type="unknown_location_type"),
        ]

        for issue in edge_issues:
            with self.subTest(issue=issue):
                result = priority.calculate_priority(issue)
                self.assertIsInstance(result, dict)
                self.assertIn(result["priority_level"], PRIORITY_LEVELS)
                self.assertGreaterEqual(result["priority_score"], 0)
                self.assertLessEqual(result["priority_score"], 100)

    def test_duplicate_edge_cases(self) -> None:
        edge_pairs = [
            ({}, {}),
            ({"latitude": 200, "longitude": 500, "category": "", "description": ""},
             {"latitude": None, "longitude": None, "category": None, "description": None}),
            ({"latitude": 13.08, "longitude": 80.27, "category": "pothole",
              "description": ""}, {"latitude": 13.08, "longitude": 80.27,
              "category": "pothole", "description": None}),
        ]

        for new_report, existing_report in edge_pairs:
            with self.subTest(new_report=new_report, existing_report=existing_report):
                result = duplicate.calculate_duplicate_score(new_report, existing_report)
                self.assertIsInstance(result, dict)
                self.assertGreaterEqual(result["duplicate_score"], 0)
                self.assertLessEqual(result["duplicate_score"], 100)
                self.assertIn(result["confidence"], DUPLICATE_CONFIDENCES)

        # find_duplicates / find_best_duplicate with malformed input.
        self.assertEqual(duplicate.find_duplicates({}, "not-a-list"), [])
        self.assertIsNone(duplicate.find_best_duplicate({}, []))


# ============================================================================
# TEST RUNNER
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING CIVIC ISSUE REPORTING SYSTEM TEST SUITE")
    print("=" * 70)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestValidator))
    suite.addTests(loader.loadTestsFromTestCase(TestPriority))
    suite.addTests(loader.loadTestsFromTestCase(TestDuplicate))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    suite.addTests(loader.loadTestsFromTestCase(TestEdgeCases))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests run : {result.testsRun}")
    print(f"Failures  : {len(result.failures)}")
    print(f"Errors    : {len(result.errors)}")
    print(f"Passed    : {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Overall   : {'PASSED' if result.wasSuccessful() else 'FAILED'}")
    print("=" * 70)
