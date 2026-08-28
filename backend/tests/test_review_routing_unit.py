"""
tests/test_review_routing_unit.py

Focused unit tests for app.services.review_routing.evaluate_manual_review()
-- the small orchestration layer that decides MANUAL_REVIEW vs. proceed,
built around the canonical validator.py/duplicate.py outputs plus the AI
understanding layer's confidence/category. These tests exercise the
function directly (no HTTP, no DB) so each trigger can be verified in
isolation, precisely, and fast. End-to-end wiring through the real
pipeline is covered separately in tests/test_manual_review_routing.py.

No import of app.database/app.main is needed here -- evaluate_manual_review
and the validator.py factor function it calls are both pure, DB-free
functions.

Run with:
    cd backend && venv/bin/python -m unittest tests.test_review_routing_unit -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.review_routing import (  # noqa: E402
    REASON_CATEGORY_UNCERTAIN,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_INSUFFICIENT_VISUAL_EVIDENCE,
    REASON_LOW_AI_CONFIDENCE,
    REASON_PHOTO_TEXT_CONFLICT,
    REASON_POSSIBLE_DUPLICATE,
    REASON_VAGUE_DESCRIPTION,
    REASON_VALIDATION_REQUIRES_REVIEW,
    evaluate_manual_review,
)

CLEAR_DESCRIPTION = "Large pothole on the main road near the market is causing traffic to swerve dangerously."


class ClearTextNoImageTests(unittest.TestCase):
    def test_clear_text_no_image_proceeds_normally(self):
        is_review, reasons = evaluate_manual_review(
            validity_status="VALID", ai_confidence=0.9, category="Roads",
            duplicate_action="CREATE_NEW", has_photo=False,
            description=CLEAR_DESCRIPTION, validator_category="pothole",
        )
        self.assertFalse(is_review)
        self.assertEqual(reasons, [])


class ClearImageNoTextTests(unittest.TestCase):
    def test_clear_image_no_text_proceeds_when_confidence_is_sufficient(self):
        is_review, reasons = evaluate_manual_review(
            validity_status="VALID", ai_confidence=0.85, category="Roads",
            duplicate_action="CREATE_NEW", has_photo=True,
            description=None, validator_category="pothole",
        )
        self.assertFalse(is_review)
        self.assertEqual(reasons, [])


class VagueTextNoImageTests(unittest.TestCase):
    def test_vague_text_alone_triggers_review_even_when_everything_else_is_fine(self):
        # Everything else (validity, confidence, category, duplicate) looks
        # fine -- only the description itself is too thin. This must be
        # caught on its own, independent of the overall validator score.
        is_review, reasons = evaluate_manual_review(
            validity_status="VALID", ai_confidence=0.9, category="Roads",
            duplicate_action="CREATE_NEW", has_photo=False,
            description="bad", validator_category="pothole",
        )
        self.assertTrue(is_review)
        self.assertEqual(reasons, [REASON_VAGUE_DESCRIPTION])

    def test_empty_description_treated_as_absent_not_vague(self):
        # PHOTO_ONLY's intentionally-absent description must not be
        # penalized as "vague" -- it wasn't provided at all, by design.
        is_review, reasons = evaluate_manual_review(
            validity_status="VALID", ai_confidence=0.9, category="Roads",
            duplicate_action="CREATE_NEW", has_photo=True,
            description="", validator_category="pothole",
        )
        self.assertNotIn(REASON_VAGUE_DESCRIPTION, reasons)


class WeakImageNoTextTests(unittest.TestCase):
    def test_weak_image_alone_triggers_review(self):
        is_review, reasons = evaluate_manual_review(
            validity_status="VALID", ai_confidence=0.3, category="Roads",
            duplicate_action="CREATE_NEW", has_photo=True,
            description=None, validator_category="pothole",
        )
        self.assertTrue(is_review)
        self.assertEqual(reasons, [REASON_INSUFFICIENT_VISUAL_EVIDENCE])


class LowAiConfidenceTests(unittest.TestCase):
    def test_low_confidence_text_only_triggers_review(self):
        is_review, reasons = evaluate_manual_review(
            validity_status="VALID", ai_confidence=0.35, category="Roads",
            duplicate_action="CREATE_NEW", has_photo=False,
            description=CLEAR_DESCRIPTION, validator_category="pothole",
        )
        self.assertTrue(is_review)
        self.assertEqual(reasons, [REASON_LOW_AI_CONFIDENCE])

    def test_low_confidence_with_both_photo_and_text_is_framed_as_conflict(self):
        is_review, reasons = evaluate_manual_review(
            validity_status="VALID", ai_confidence=0.35, category="Roads",
            duplicate_action="CREATE_NEW", has_photo=True,
            description=CLEAR_DESCRIPTION, validator_category="pothole",
        )
        self.assertTrue(is_review)
        self.assertEqual(reasons, [REASON_PHOTO_TEXT_CONFLICT])


class CategoryUncertainTests(unittest.TestCase):
    def test_other_category_triggers_review(self):
        is_review, reasons = evaluate_manual_review(
            validity_status="VALID", ai_confidence=0.9, category="Other",
            duplicate_action="CREATE_NEW", has_photo=True,
            description=CLEAR_DESCRIPTION, validator_category="other",
        )
        self.assertTrue(is_review)
        self.assertIn(REASON_CATEGORY_UNCERTAIN, reasons)


class PossibleDuplicateTests(unittest.TestCase):
    def test_possible_duplicate_triggers_review(self):
        is_review, reasons = evaluate_manual_review(
            validity_status="VALID", ai_confidence=0.9, category="Roads",
            duplicate_action="REVIEW", has_photo=True,
            description=CLEAR_DESCRIPTION, validator_category="pothole",
        )
        self.assertTrue(is_review)
        self.assertEqual(reasons, [REASON_POSSIBLE_DUPLICATE])

    def test_high_confidence_duplicate_link_does_not_by_itself_trigger_review(self):
        # LINK_TO_EXISTING (high-confidence match) is a different code
        # path entirely in report_pipeline.py (never reaches this
        # function) -- but confirms CREATE_NEW with a non-REVIEW action
        # never triggers the duplicate reason.
        is_review, reasons = evaluate_manual_review(
            validity_status="VALID", ai_confidence=0.9, category="Roads",
            duplicate_action="CREATE_NEW", has_photo=True,
            description=CLEAR_DESCRIPTION, validator_category="pothole",
        )
        self.assertFalse(is_review)
        self.assertNotIn(REASON_POSSIBLE_DUPLICATE, reasons)


class CanonicalValidatorStatusTests(unittest.TestCase):
    def test_review_status_triggers_manual_review(self):
        is_review, reasons = evaluate_manual_review(
            validity_status="REVIEW", ai_confidence=0.9, category="Roads",
            duplicate_action="CREATE_NEW", has_photo=True,
            description=CLEAR_DESCRIPTION, validator_category="pothole",
        )
        self.assertTrue(is_review)
        self.assertIn(REASON_VALIDATION_REQUIRES_REVIEW, reasons)

    def test_suspicious_status_never_returns_a_rejected_style_decision(self):
        # SUSPICIOUS (validator.py's own lowest tier, e.g. a spam/
        # malicious-looking report) still routes to manual review only --
        # this function has no other outcome than (True, reasons) or
        # (False, []). REJECTED only ever happens via an explicit staff
        # decision elsewhere, never automatically here.
        is_review, reasons = evaluate_manual_review(
            validity_status="SUSPICIOUS", ai_confidence=0.9, category="Roads",
            duplicate_action="CREATE_NEW", has_photo=True,
            description=CLEAR_DESCRIPTION, validator_category="pothole",
        )
        self.assertTrue(is_review)
        self.assertIn(REASON_INSUFFICIENT_EVIDENCE, reasons)


class StrongPhotoStrongDescriptionTests(unittest.TestCase):
    def test_strong_photo_and_strong_description_proceeds_normally(self):
        is_review, reasons = evaluate_manual_review(
            validity_status="VALID", ai_confidence=0.92, category="Roads",
            duplicate_action="CREATE_NEW", has_photo=True,
            description=CLEAR_DESCRIPTION, validator_category="pothole",
        )
        self.assertFalse(is_review)
        self.assertEqual(reasons, [])


class ReasonInvariantTests(unittest.TestCase):
    def test_is_manual_review_iff_reasons_non_empty(self):
        # A report is never flagged without a concrete, staff-visible
        # reason, and never has reasons attached without being flagged.
        cases = [
            dict(validity_status="VALID", ai_confidence=0.9, category="Roads", duplicate_action="CREATE_NEW", has_photo=True, description=CLEAR_DESCRIPTION, validator_category="pothole"),
            dict(validity_status="REVIEW", ai_confidence=0.9, category="Roads", duplicate_action="CREATE_NEW", has_photo=True, description=CLEAR_DESCRIPTION, validator_category="pothole"),
            dict(validity_status="VALID", ai_confidence=0.2, category="Other", duplicate_action="REVIEW", has_photo=True, description="x", validator_category="other"),
        ]
        for kwargs in cases:
            is_review, reasons = evaluate_manual_review(**kwargs)
            self.assertEqual(is_review, len(reasons) > 0, kwargs)

    def test_reasons_never_contain_duplicates(self):
        is_review, reasons = evaluate_manual_review(
            validity_status="SUSPICIOUS", ai_confidence=0.1, category="Other",
            duplicate_action="REVIEW", has_photo=True, description="x",
            validator_category="other",
        )
        self.assertEqual(len(reasons), len(set(reasons)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
