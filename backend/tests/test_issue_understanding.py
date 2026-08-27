"""
tests/test_issue_understanding.py

Tests for app.services.issue_understanding_service — the single
provider-independent "AI understands the report" layer. Uses an isolated
SQLite DB + upload directory (never touches the real dev database), and
mocks httpx.Client.post to simulate Groq/VLM responses without any
network access.

Run with:
    cd backend && venv/bin/python -m unittest tests.test_issue_understanding -v
"""
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-understanding-")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DIR, "uploads")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DIR, 'test.db')}"

import httpx  # noqa: E402
from PIL import Image  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
import app.main  # noqa: E402,F401  (side effect: registers all models + creates tables)
from app.services import issue_understanding_service as svc  # noqa: E402


class FakeResponse:
    """Minimal stand-in for httpx.Response, enough for our call sites."""

    def __init__(self, json_data=None, status_code=200, raise_exc=None):
        self._json = json_data
        self.status_code = status_code
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self):
        return self._json


def groq_ok(content_dict: dict) -> FakeResponse:
    return FakeResponse({"choices": [{"message": {"content": json.dumps(content_dict)}}]})


def make_sanitized_jpeg(rel_path: str) -> bytes:
    """Writes a real JPEG under UPLOAD_DIR, mimicking what
    image_sanitizer.py would have already produced, and returns its
    exact bytes for later comparison."""
    full_path = os.path.join(settings.UPLOAD_DIR, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    Image.new("RGB", (64, 48), (10, 120, 200)).save(full_path, format="JPEG")
    with open(full_path, "rb") as f:
        return f.read()


class IssueUnderstandingTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()
        # Reset provider switches before every test; each test opts in
        # explicitly via patch.object.
        self._ai_provider_patch = patch.object(settings, "AI_PROVIDER", "mock")
        self._vlm_provider_patch = patch.object(settings, "VLM_PROVIDER", "none")
        self._ai_provider_patch.start()
        self._vlm_provider_patch.start()

    def tearDown(self):
        self.db.close()
        self._ai_provider_patch.stop()
        self._vlm_provider_patch.stop()

    # -- 1. text-only, AI disabled ------------------------------------------

    def test_text_only_ai_disabled_uses_deterministic_fallback(self):
        result = svc.classify_report(self.db, "Large garbage pile near the market", "", 13.08, 80.27)
        self.assertEqual(result.source, "FALLBACK")
        self.assertEqual(result.issue_type, "Garbage Accumulation")

    # -- 2. text-only, Groq mocked successful --------------------------------

    def test_text_only_groq_mocked_success_is_accepted(self):
        with patch.object(settings, "AI_PROVIDER", "groq"), patch.object(settings, "GROQ_API_KEY", "fake-key"):
            with patch("httpx.Client.post", return_value=groq_ok({
                "category": "pothole", "severity": 4, "impact_level": 3,
                "location_type": "busy_road", "confidence": 0.88, "reasoning": "Visible large pothole.",
            })):
                result = svc.classify_report(self.db, "Huge pothole on the main road", "", 13.08, 80.27)
        self.assertEqual(result.source, "TEXT")
        self.assertEqual(result.issue_type, "Pothole")
        self.assertEqual(result.severity, 4)
        self.assertEqual(result.impact_level, 3)
        self.assertAlmostEqual(result.confidence, 0.88)

    # -- 3. malformed Groq response -------------------------------------------

    def test_malformed_groq_response_falls_back(self):
        with patch.object(settings, "AI_PROVIDER", "groq"), patch.object(settings, "GROQ_API_KEY", "fake-key"):
            with patch("httpx.Client.post", return_value=FakeResponse({"choices": [{"message": {"content": "not json at all"}}]})):
                result = svc.classify_report(self.db, "Water leaking from a broken pipe", "", 13.08, 80.27)
        self.assertEqual(result.source, "FALLBACK")
        self.assertEqual(result.issue_type, "Water Leakage")

    # -- 4. Groq timeout/error --------------------------------------------------

    def test_groq_timeout_falls_back(self):
        with patch.object(settings, "AI_PROVIDER", "groq"), patch.object(settings, "GROQ_API_KEY", "fake-key"):
            with patch("httpx.Client.post", side_effect=httpx.TimeoutException("timed out")):
                result = svc.classify_report(self.db, "Streetlight not working outside our house", "", 13.08, 80.27)
        self.assertEqual(result.source, "FALLBACK")
        self.assertEqual(result.issue_type, "Broken Streetlight")

    def test_groq_http_error_falls_back(self):
        with patch.object(settings, "AI_PROVIDER", "groq"), patch.object(settings, "GROQ_API_KEY", "fake-key"):
            with patch("httpx.Client.post", return_value=FakeResponse(status_code=500)):
                result = svc.classify_report(self.db, "Sewage overflow near the residential block", "", 13.08, 80.27)
        self.assertEqual(result.source, "FALLBACK")

    # -- 5. photo-only, VLM mocked successful --------------------------------

    def test_photo_only_vlm_mocked_success_is_accepted(self):
        make_sanitized_jpeg("reports/photo_only.jpg")
        with patch.object(settings, "VLM_PROVIDER", "groq"), patch.object(settings, "GROQ_API_KEY", "fake-key"):
            with patch("httpx.Client.post", return_value=groq_ok({
                "category": "garbage", "severity": 3, "impact_level": 3,
                "location_type": "market", "confidence": 0.81, "reasoning": "Visible waste pile.",
            })):
                result = svc.classify_report(self.db, "", "reports/photo_only.jpg", 13.08, 80.27)
        self.assertEqual(result.source, "IMAGE")
        self.assertEqual(result.issue_type, "Garbage Accumulation")
        self.assertAlmostEqual(result.confidence, 0.81)

    # -- 6. photo-only, VLM unavailable ---------------------------------------

    def test_photo_only_without_vlm_is_still_accepted_as_other(self):
        make_sanitized_jpeg("reports/no_vlm.jpg")
        # VLM_PROVIDER=none (setUp default) — no AI at all is configured.
        result = svc.classify_report(self.db, "", "reports/no_vlm.jpg", 13.08, 80.27)
        self.assertEqual(result.source, "FALLBACK")
        self.assertEqual(result.issue_type, "Other")
        self.assertLess(result.confidence, 0.5)

    def test_photo_only_vlm_failure_falls_back_safely(self):
        make_sanitized_jpeg("reports/vlm_fail.jpg")
        with patch.object(settings, "VLM_PROVIDER", "groq"), patch.object(settings, "GROQ_API_KEY", "fake-key"):
            with patch("httpx.Client.post", side_effect=httpx.ConnectError("connection refused")):
                result = svc.classify_report(self.db, "", "reports/vlm_fail.jpg", 13.08, 80.27)
        self.assertEqual(result.source, "FALLBACK")
        self.assertEqual(result.issue_type, "Other")

    # -- 7. text + photo combines available evidence -------------------------

    def test_text_and_photo_combines_evidence_via_single_vlm_call(self):
        make_sanitized_jpeg("reports/combined.jpg")
        with patch.object(settings, "AI_PROVIDER", "groq"), patch.object(settings, "VLM_PROVIDER", "groq"), \
             patch.object(settings, "GROQ_API_KEY", "fake-key"):
            with patch("httpx.Client.post", return_value=groq_ok({
                "category": "drainage", "severity": 5, "impact_level": 4,
                "location_type": "busy_road", "confidence": 0.93, "reasoning": "Overflowing drain visible, blocking traffic.",
            })) as mock_post:
                result = svc.classify_report(self.db, "Drain overflowing badly after the rain", "reports/combined.jpg", 13.08, 80.27)
        self.assertEqual(result.source, "TEXT_AND_IMAGE")
        self.assertEqual(result.issue_type, "Overflowing Drain")
        self.assertEqual(result.severity, 5)
        # Only ONE call should have been made (the combined vision call),
        # not a separate text call too.
        self.assertEqual(mock_post.call_count, 1)

    # -- 8. invalid AI output is caught by schema/normalization ---------------

    def test_invalid_severity_out_of_range_falls_back(self):
        with patch.object(settings, "AI_PROVIDER", "groq"), patch.object(settings, "GROQ_API_KEY", "fake-key"):
            with patch("httpx.Client.post", return_value=groq_ok({
                "category": "pothole", "severity": 99, "impact_level": 3,
                "location_type": "busy_road", "confidence": 0.9,
            })):
                result = svc.classify_report(self.db, "Pothole causing damage to vehicles", "", 13.08, 80.27)
        self.assertEqual(result.source, "FALLBACK")

    def test_invalid_confidence_out_of_range_falls_back(self):
        with patch.object(settings, "AI_PROVIDER", "groq"), patch.object(settings, "GROQ_API_KEY", "fake-key"):
            with patch("httpx.Client.post", return_value=groq_ok({
                "category": "pothole", "severity": 3, "impact_level": 3,
                "location_type": "busy_road", "confidence": 4.2,
            })):
                result = svc.classify_report(self.db, "Pothole on the road", "", 13.08, 80.27)
        self.assertEqual(result.source, "FALLBACK")

    def test_unrecognized_location_type_is_normalized_not_rejected(self):
        # location_type is soft-normalized (not a hard-fail) since it is
        # informational only — the deterministic GPS/POI lookup always
        # remains authoritative for what feeds priority.py.
        with patch.object(settings, "AI_PROVIDER", "groq"), patch.object(settings, "GROQ_API_KEY", "fake-key"):
            with patch("httpx.Client.post", return_value=groq_ok({
                "category": "pothole", "severity": 3, "impact_level": 3,
                "location_type": "some_made_up_place", "confidence": 0.7,
            })):
                result = svc.classify_report(self.db, "Pothole on the road", "", 13.08, 80.27)
        self.assertEqual(result.source, "TEXT")
        # Authoritative location_type still comes from describe_location(),
        # never from the AI's (normalized-but-unused) guess.
        self.assertIn(result.location_type, svc.VALID_LOCATION_TYPES)

    # -- 9. raw unsanitized upload is never sent to AI/VLM --------------------

    def test_only_the_sanitized_file_bytes_are_ever_sent_to_vlm(self):
        sanitized_bytes = make_sanitized_jpeg("reports/exact_bytes.jpg")
        captured = {}

        def fake_post(self_client, url, headers=None, json=None):
            captured["json"] = json
            return groq_ok({
                "category": "pothole", "severity": 2, "impact_level": 2,
                "location_type": "normal_area", "confidence": 0.6,
            })

        with patch.object(settings, "VLM_PROVIDER", "groq"), patch.object(settings, "GROQ_API_KEY", "fake-key"):
            with patch("httpx.Client.post", new=fake_post):
                svc.classify_report(self.db, "", "reports/exact_bytes.jpg", 13.08, 80.27)

        import base64
        content_parts = captured["json"]["messages"][1]["content"]
        image_part = next(p for p in content_parts if p["type"] == "image_url")
        data_url = image_part["image_url"]["url"]
        self.assertTrue(data_url.startswith("data:image/jpeg;base64,"))
        sent_b64 = data_url.split(",", 1)[1]
        sent_bytes = base64.b64decode(sent_b64)
        # The bytes sent must be EXACTLY the sanitized file's bytes — this
        # service has no other image source available to it at all.
        self.assertEqual(sent_bytes, sanitized_bytes)

    def test_missing_sanitized_file_falls_back_without_crashing(self):
        # No file exists at this path — must fail safe, not raise.
        with patch.object(settings, "VLM_PROVIDER", "groq"), patch.object(settings, "GROQ_API_KEY", "fake-key"):
            result = svc.classify_report(self.db, "", "reports/does_not_exist.jpg", 13.08, 80.27)
        self.assertEqual(result.source, "FALLBACK")
        self.assertEqual(result.issue_type, "Other")


if __name__ == "__main__":
    unittest.main(verbosity=2)
