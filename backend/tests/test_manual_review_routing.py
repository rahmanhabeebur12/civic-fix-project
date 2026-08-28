"""
tests/test_manual_review_routing.py

End-to-end regression coverage for the manual-review routing layer
(app.services.review_routing, wired into app.services.report_pipeline).
Verifies the ORCHESTRATION is actually wired correctly through the real
HTTP submission path and persisted correctly -- unit-level coverage of
the decision function itself lives in test_review_routing_unit.py.

The canonical validator.py/duplicate.py/priority.py are never mocked or
modified here -- only their SURROUNDING adapter/service functions are
patched, to deterministically control which review-routing trigger
fires for a given scenario, exactly as report_pipeline.py already calls
them (same call signatures, same import paths).

Run with:
    cd backend && venv/bin/python -m unittest tests.test_manual_review_routing -v
"""
import io
import os
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-review-routing-")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DIR, "uploads")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DIR, 'test.db')}"

from PIL import Image  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.department import Department  # noqa: E402
from app.models.issue import Issue  # noqa: E402
from app.models.staff import StaffUser  # noqa: E402
from app.services.auth_service import hash_password  # noqa: E402
from app.services.issue_understanding_service import ClassificationResult  # noqa: E402
from app.services.taxonomy import DEPARTMENTS  # noqa: E402
from app.services.validation_adapter import AdapterResult  # noqa: E402

client = TestClient(app)


def _seed_departments():
    db = SessionLocal()
    try:
        for name, code in DEPARTMENTS:
            if not db.query(Department).filter(Department.name == name).first():
                db.add(Department(name=name, code=code))
        db.commit()
    finally:
        db.close()


def _seed_staff(username="reviewtester", password="reviewtesterpass1"):
    db = SessionLocal()
    try:
        if not db.query(StaffUser).filter(StaffUser.username == username).first():
            db.add(StaffUser(username=username, password_hash=hash_password(password), full_name="Review Tester", role="admin"))
            db.commit()
    finally:
        db.close()


def _staff_headers():
    resp = client.post("/auth/login", json={"username": "reviewtester", "password": "reviewtesterpass1"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def make_jpeg_bytes(color=(60, 140, 220)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), color).save(buf, format="JPEG")
    return buf.getvalue()


def _pothole_classification(confidence=0.9, category="Roads") -> ClassificationResult:
    return ClassificationResult(
        issue_type="Pothole", category=category, confidence=confidence,
        suggested_department="Roads / Public Works", safety_risk="Low",
        reasoning_summary="Test classification.", severity=3, severity_label="MEDIUM",
        severity_reason="Test.", impact_level=3, location_type="normal_area",
        location_context="Test location.", source="FALLBACK",
    )


def _valid_adapter_result(status="VALID", submission_mode="PHOTO_AND_TEXT") -> AdapterResult:
    return AdapterResult(
        validity_score=90.0 if status == "VALID" else (65.0 if status == "REVIEW" else 20.0),
        status=status, breakdown={}, validation_errors=[],
        submission_mode=submission_mode, accessibility_adjustment=False,
    )


def submit_report(*, description=None, mobile, with_photo=True, latitude=13.05, longitude=80.20):
    data = {
        "client_report_id": str(uuid.uuid4()),
        "latitude": str(latitude), "longitude": str(longitude), "accuracy": "8",
        "language": "en", "name": "Review Routing Tester", "mobile": mobile, "was_offline": "false",
    }
    if description is not None:
        data["description"] = description
    files = {"image": ("photo.jpg", make_jpeg_bytes(), "image/jpeg")} if with_photo else None
    return client.post("/citizen/reports", data=data, files=files)


class NoMockingNaturalPathTests(unittest.TestCase):
    """Nothing mocked here -- the real fallback classifier + real
    validator.py, exactly as production runs without a configured AI/VLM
    provider."""

    @classmethod
    def setUpClass(cls):
        _seed_departments()

    def test_strong_photo_and_strong_description_from_a_new_user_proceeds_normally(self):
        r = submit_report(
            description="Large pothole on the main road near the market causing traffic to swerve dangerously.",
            mobile="9700000001", with_photo=True,
        )
        self.assertEqual(r.status_code, 200, r.text)
        db = SessionLocal()
        issue = db.query(Issue).filter(Issue.complaint_id == r.json()["complaint_id"]).first()
        status = issue.status
        db.close()
        self.assertEqual(status, "ASSIGNED", "strong evidence from a first-time citizen must not be sent to review")


class MockedTriggerTests(unittest.TestCase):
    """Each test patches only the specific upstream signal it needs to
    control (report_pipeline.py's own call sites for the AI understanding
    layer, the validity adapter, or the duplicate recommendation) so the
    scenario is deterministic -- validator.py/duplicate.py/priority.py
    themselves are never touched or mocked."""

    @classmethod
    def setUpClass(cls):
        _seed_departments()
        _seed_staff()

    def setUp(self):
        self.headers = _staff_headers()

    def _issue_for(self, complaint_id):
        db = SessionLocal()
        try:
            return db.query(Issue).filter(Issue.complaint_id == complaint_id).first()
        finally:
            db.close()

    def test_low_ai_confidence_sends_report_to_manual_review(self):
        with patch(
            "app.services.report_pipeline.issue_understanding_service.classify_report",
            return_value=_pothole_classification(confidence=0.3),
        ):
            r = submit_report(description="There is a big pothole on the road near my house.", mobile="9700000002")
        self.assertEqual(r.status_code, 200, r.text)
        issue = self._issue_for(r.json()["complaint_id"])
        self.assertEqual(issue.status, "MANUAL_REVIEW")

        detail = client.get(f"/staff/issues/{issue.id}", headers=self.headers).json()
        self.assertIn("Photo and description conflict", detail["review_reasons"])

    def test_possible_duplicate_sends_report_to_manual_review(self):
        with patch(
            "app.services.report_pipeline.core_duplicate.get_duplicate_recommendation",
            return_value={"action": "REVIEW", "matched_report_id": None, "duplicate_score": 55, "confidence": "POSSIBLE"},
        ):
            r = submit_report(description="Streetlight near the bus stop has been flickering for days now.", mobile="9700000003")
        self.assertEqual(r.status_code, 200, r.text)
        issue = self._issue_for(r.json()["complaint_id"])
        self.assertEqual(issue.status, "MANUAL_REVIEW")
        self.assertEqual(issue.duplicate_action, "REVIEW")

        detail = client.get(f"/staff/issues/{issue.id}", headers=self.headers).json()
        self.assertIn("Possible duplicate", detail["review_reasons"])

    def test_canonical_validator_review_status_sends_report_to_manual_review(self):
        with patch(
            "app.services.report_pipeline.calculate_validity_adaptive",
            return_value=_valid_adapter_result(status="REVIEW"),
        ):
            r = submit_report(description="Water is leaking from a broken pipe near the corner shop.", mobile="9700000004")
        self.assertEqual(r.status_code, 200, r.text)
        issue = self._issue_for(r.json()["complaint_id"])
        self.assertEqual(issue.status, "MANUAL_REVIEW")

        detail = client.get(f"/staff/issues/{issue.id}", headers=self.headers).json()
        self.assertIn("Validation requires review", detail["review_reasons"])

    def test_suspicious_validity_never_auto_rejects_only_routes_to_manual_review(self):
        # Preserves existing suspicious/spam handling: SUSPICIOUS still
        # never becomes REJECTED automatically -- only a staff member's
        # explicit review-decision can reject a report.
        with patch(
            "app.services.report_pipeline.calculate_validity_adaptive",
            return_value=_valid_adapter_result(status="SUSPICIOUS"),
        ):
            r = submit_report(description="Suspicious low quality report for testing.", mobile="9700000005")
        self.assertEqual(r.status_code, 200, r.text)
        issue = self._issue_for(r.json()["complaint_id"])
        self.assertEqual(issue.status, "MANUAL_REVIEW")
        self.assertNotEqual(issue.status, "REJECTED")

        detail = client.get(f"/staff/issues/{issue.id}", headers=self.headers).json()
        self.assertIn("Insufficient evidence", detail["review_reasons"])

    def test_category_uncertain_sends_report_to_manual_review(self):
        with patch(
            "app.services.report_pipeline.issue_understanding_service.classify_report",
            return_value=_pothole_classification(confidence=0.9, category="Other"),
        ):
            r = submit_report(description="Something is wrong near the corner but I am not sure what category.", mobile="9700000006")
        self.assertEqual(r.status_code, 200, r.text)
        issue = self._issue_for(r.json()["complaint_id"])
        self.assertEqual(issue.status, "MANUAL_REVIEW")

        detail = client.get(f"/staff/issues/{issue.id}", headers=self.headers).json()
        self.assertIn("Category uncertain", detail["review_reasons"])

    def test_manual_review_reasons_are_never_shown_when_report_proceeds_normally(self):
        with patch(
            "app.services.report_pipeline.issue_understanding_service.classify_report",
            return_value=_pothole_classification(confidence=0.9, category="Roads"),
        ), patch(
            "app.services.report_pipeline.calculate_validity_adaptive",
            return_value=_valid_adapter_result(status="VALID"),
        ), patch(
            "app.services.report_pipeline.core_duplicate.get_duplicate_recommendation",
            return_value={"action": "CREATE_NEW", "matched_report_id": None, "duplicate_score": 0, "confidence": "NONE"},
        ):
            r = submit_report(description="Large pothole causing traffic disruption near the market entrance.", mobile="9700000007")
        self.assertEqual(r.status_code, 200, r.text)
        issue = self._issue_for(r.json()["complaint_id"])
        self.assertEqual(issue.status, "ASSIGNED")

        detail = client.get(f"/staff/issues/{issue.id}", headers=self.headers).json()
        self.assertEqual(detail["review_reasons"], [])

    def test_manual_review_issue_appears_correctly_in_review_queue_with_full_context(self):
        with patch(
            "app.services.report_pipeline.calculate_validity_adaptive",
            return_value=_valid_adapter_result(status="REVIEW"),
        ):
            r = submit_report(description="Garbage has been piling up near the market for a week.", mobile="9700000008")
        complaint_id = r.json()["complaint_id"]

        queue = client.get("/staff/issues?status=MANUAL_REVIEW", headers=self.headers).json()
        matching = next((i for i in queue if i["complaint_id"] == complaint_id), None)
        self.assertIsNotNone(matching, "a manual-review issue must appear in the Review Queue")
        self.assertIn("Validation requires review", matching["review_reasons"])

        detail = client.get(f"/staff/issues/{matching['id']}", headers=self.headers).json()
        # Requirement: staff must be able to see description, image,
        # location, AI category/confidence, validation result, and
        # duplicate result for a review-queue item.
        for field in ("description", "image_url", "latitude", "longitude", "category", "ai_confidence", "validity_status", "duplicate_confidence"):
            self.assertIn(field, detail)

    def test_duplicate_linking_and_reporter_count_are_unaffected_by_review_routing(self):
        # Regression guard: LINK_TO_EXISTING never runs through
        # evaluate_manual_review() at all (it doesn't touch issue.status),
        # so it must behave exactly as before.
        first = submit_report(description="Overflowing garbage bin behind the community hall on Main Street.", mobile="9700000009")
        self.assertEqual(first.status_code, 200, first.text)
        complaint_id = first.json()["complaint_id"]
        issue_before = self._issue_for(complaint_id)

        with patch(
            "app.services.report_pipeline.core_duplicate.get_duplicate_recommendation",
            return_value={"action": "LINK_TO_EXISTING", "matched_report_id": issue_before.id, "duplicate_score": 92, "confidence": "HIGH"},
        ):
            second = submit_report(description="Same overflowing garbage bin behind the community hall, still not cleared.", mobile="9700000010")
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["complaint_id"], complaint_id, "a LINK_TO_EXISTING report must not create a second issue")

        issue_after = self._issue_for(complaint_id)
        self.assertEqual(issue_after.reporter_count, issue_before.reporter_count + 1)
        self.assertEqual(issue_after.status, issue_before.status, "linking a report must never change the existing issue's status")


if __name__ == "__main__":
    unittest.main(verbosity=2)
