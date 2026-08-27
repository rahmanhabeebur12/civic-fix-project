"""
tests/test_accessibility_submission.py

End-to-end tests for the accessibility requirement: a photo AND a
description are not both required for a citizen report — either one is
enough. Run against the real FastAPI app through the full
report_pipeline (image sanitizer -> AI understanding -> validation
adapter -> duplicate detection -> priority -> routing -> persistence),
using an isolated SQLite database and upload directory so the real dev
database/uploads are never touched.

Run with:
    cd backend && venv/bin/python -m unittest tests.test_accessibility_submission -v
"""
import io
import json
import os
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Isolated DB + upload dir BEFORE anything imports app.config/app.database
# (both read env vars at import time).
_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-accessibility-")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DIR, "uploads")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DIR, 'test.db')}"

from PIL import Image  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.department import Department  # noqa: E402
from app.models.issue import Issue, IssueReport  # noqa: E402
from app.services.taxonomy import DEPARTMENTS  # noqa: E402

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


def make_jpeg_bytes(color=(50, 120, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), color).save(buf, format="JPEG")
    return buf.getvalue()


class AccessibilitySubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()

    def _submit(self, *, description=None, with_photo=False, mobile, was_offline=False, latitude=13.0827, longitude=80.2707):
        data = {
            "client_report_id": str(uuid.uuid4()),
            "latitude": str(latitude),
            "longitude": str(longitude),
            "accuracy": "8",
            "language": "en",
            "name": "Test Citizen",
            "mobile": mobile,
            "was_offline": "true" if was_offline else "false",
        }
        if description is not None:
            data["description"] = description
        files = {"image": ("photo.jpg", make_jpeg_bytes(), "image/jpeg")} if with_photo else None
        return client.post("/citizen/reports", data=data, files=files)

    def _latest_report(self, complaint_id: str) -> IssueReport:
        db = SessionLocal()
        try:
            issue = db.query(Issue).filter(Issue.complaint_id == complaint_id).first()
            self.assertIsNotNone(issue, "issue was not created")
            report = (
                db.query(IssueReport)
                .filter(IssueReport.issue_id == issue.id)
                .order_by(IssueReport.id.desc())
                .first()
            )
            self.assertIsNotNone(report, "issue report was not created")
            return report
        finally:
            db.close()

    # -- 1. photo + description --------------------------------------------

    def test_photo_and_description_accepted_normally(self):
        resp = self._submit(
            description="Large pothole blocking the road near the market causing traffic problems",
            with_photo=True, mobile="9800000001",
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["submission_mode"], "PHOTO_AND_TEXT")

        report = self._latest_report(body["complaint_id"])
        self.assertFalse(report.accessibility_adjustment)
        self.assertEqual(report.submission_mode, "PHOTO_AND_TEXT")

    # -- 2. photo only --------------------------------------------------------

    def test_photo_only_is_accepted_with_reduced_confidence(self):
        resp = self._submit(description=None, with_photo=True, mobile="9800000002")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["submission_mode"], "PHOTO_ONLY")
        self.assertIn(body["validity_status"], ("VALID", "REVIEW", "SUSPICIOUS"))

        report = self._latest_report(body["complaint_id"])
        self.assertEqual(report.submission_mode, "PHOTO_ONLY")
        self.assertTrue(report.accessibility_adjustment)
        self.assertNotEqual(report.image_path, "", "the photo that WAS provided must be saved")
        self.assertEqual(report.original_description, "", "a missing description must stay empty, never fabricated")
        errors = json.loads(report.validation_errors)
        self.assertIn("Description not provided", errors)
        self.assertIn("Accepted under accessibility mode", errors)
        # Never automatically SUSPICIOUS just for using the accessibility path.
        self.assertNotEqual(report.validity_status, "SUSPICIOUS")

    def test_photo_only_falls_back_to_other_category_without_vlm(self):
        resp = self._submit(description=None, with_photo=True, mobile="9800000008")
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        # No VLM/image-understanding provider is configured (AI_PROVIDER=mock
        # by default) — must not fake a confident classification.
        self.assertEqual(body["issue_type"], "Other")

    # -- 3. description only ---------------------------------------------------

    def test_description_only_is_accepted_with_reduced_confidence(self):
        resp = self._submit(
            description="Water leaking heavily from a broken pipe near the bus stop",
            with_photo=False, mobile="9800000003",
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["submission_mode"], "TEXT_ONLY")

        report = self._latest_report(body["complaint_id"])
        self.assertEqual(report.submission_mode, "TEXT_ONLY")
        self.assertTrue(report.accessibility_adjustment)
        self.assertEqual(report.image_path, "")
        errors = json.loads(report.validation_errors)
        self.assertIn("Photo not provided", errors)
        self.assertIn("Accepted under accessibility mode", errors)
        self.assertNotEqual(report.validity_status, "SUSPICIOUS")

    def test_description_only_uses_text_categorization(self):
        resp = self._submit(
            description="Streetlight not working outside our house for a week",
            with_photo=False, mobile="9800000009",
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["issue_type"], "Broken Streetlight")

    # -- 4. neither -------------------------------------------------------------

    def test_neither_photo_nor_description_is_rejected(self):
        resp = self._submit(description=None, with_photo=False, mobile="9800000004")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("photo or a description", resp.json()["detail"])

    def test_blank_description_with_no_photo_is_rejected(self):
        resp = self._submit(description="   ", with_photo=False, mobile="9800000005")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("photo or a description", resp.json()["detail"])

    def test_rejected_submission_creates_no_issue(self):
        before = SessionLocal()
        try:
            count_before = before.query(Issue).count()
        finally:
            before.close()

        self._submit(description=None, with_photo=False, mobile="9800000010")

        after = SessionLocal()
        try:
            count_after = after.query(Issue).count()
        finally:
            after.close()
        self.assertEqual(count_before, count_after, "a rejected (neither) submission must not create an Issue")

    # -- Offline sync uses the identical pipeline --------------------------

    def test_offline_synced_photo_only_uses_same_pipeline(self):
        resp = self._submit(description=None, with_photo=True, mobile="9800000006", was_offline=True)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["submission_mode"], "PHOTO_ONLY")
        report = self._latest_report(body["complaint_id"])
        self.assertTrue(report.was_offline)
        self.assertIsNotNone(report.synced_at)
        self.assertTrue(report.accessibility_adjustment)

    def test_offline_synced_description_only_uses_same_pipeline(self):
        resp = self._submit(
            description="Streetlight has been broken for a week on our street",
            with_photo=False, mobile="9800000007", was_offline=True,
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertEqual(body["submission_mode"], "TEXT_ONLY")
        report = self._latest_report(body["complaint_id"])
        self.assertTrue(report.was_offline)
        self.assertTrue(report.accessibility_adjustment)

    def test_idempotent_retry_of_photo_only_report_does_not_reprocess(self):
        client_report_id = str(uuid.uuid4())
        data = {
            "client_report_id": client_report_id,
            "latitude": "13.0827", "longitude": "80.2707", "accuracy": "8",
            "language": "en", "name": "Test Citizen", "mobile": "9800000011",
            "was_offline": "false",
        }
        files = {"image": ("photo.jpg", make_jpeg_bytes(), "image/jpeg")}
        first = client.post("/citizen/reports", data=data, files=files)
        self.assertEqual(first.status_code, 200, first.text)

        second = client.post("/citizen/reports", data=data, files=files)
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(first.json()["complaint_id"], second.json()["complaint_id"])
        self.assertIn("already submitted", second.json()["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
