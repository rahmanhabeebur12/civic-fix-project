"""
tests/test_citizen_status_source_of_truth.py

Backend-side guard for the "citizen tracking shows a status staff never
actually set" bug: /citizen/reports/{id} (Track Report) and
/citizen/my-reports (My Reports) must always return exactly the
persisted Issue.status — the same value at every single lifecycle step,
never a status ahead of what staff have actually done.

The actual root cause of the reported bug was a frontend-only timeline
rendering bug (see frontend/src/constants/citizenStatus.ts) — this test
exists to make sure the backend side of the contract these citizen pages
depend on can never silently regress either.

Run with:
    cd backend && venv/bin/python -m unittest tests.test_citizen_status_source_of_truth -v
"""
import io
import os
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-status-truth-")
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


def _seed_staff(username="statustester", password="statustesterpass1"):
    db = SessionLocal()
    try:
        if not db.query(StaffUser).filter(StaffUser.username == username).first():
            db.add(StaffUser(username=username, password_hash=hash_password(password), full_name="Status Tester", role="admin"))
            db.commit()
    finally:
        db.close()


def _staff_headers():
    resp = client.post("/auth/login", json={"username": "statustester", "password": "statustesterpass1"})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def make_jpeg_bytes(color=(90, 160, 240)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), color).save(buf, format="JPEG")
    return buf.getvalue()


def submit_report(mobile: str, description: str):
    data = {
        "client_report_id": str(uuid.uuid4()),
        "description": description,
        "latitude": "13.04", "longitude": "80.19", "accuracy": "8",
        "language": "en", "name": "Status Truth Tester", "mobile": mobile, "was_offline": "false",
    }
    files = {"image": ("photo.jpg", make_jpeg_bytes(), "image/jpeg")}
    return client.post("/citizen/reports", data=data, files=files)


def _current_backend_status(issue_id: int) -> str:
    db = SessionLocal()
    try:
        return db.query(Issue).get(issue_id).status
    finally:
        db.close()


class StatusMatchesBackendAtEveryStepTests(unittest.TestCase):
    """Drives one report through the REAL lifecycle exactly the way a
    staff member would, and after every single transition checks that
    both citizen-facing endpoints report the exact same status the
    database actually holds — never a status ahead of it."""

    @classmethod
    def setUpClass(cls):
        _seed_departments()
        _seed_staff()

    def _assert_citizen_endpoints_match_backend(self, complaint_id: str, mobile: str, issue_id: int):
        backend_status = _current_backend_status(issue_id)

        track_resp = client.get(f"/citizen/reports/{complaint_id}")
        self.assertEqual(track_resp.status_code, 200, track_resp.text)
        self.assertEqual(track_resp.json()["status"], backend_status,
                          f"Track Report status must equal the persisted backend status ({backend_status})")

        my_reports_resp = client.get(f"/citizen/my-reports?mobile={mobile}")
        self.assertEqual(my_reports_resp.status_code, 200, my_reports_resp.text)
        matching = next((r for r in my_reports_resp.json() if r["complaint_id"] == complaint_id), None)
        self.assertIsNotNone(matching, "report must appear in My Reports")
        self.assertEqual(matching["status"], backend_status,
                          f"My Reports status must equal the persisted backend status ({backend_status})")
        return backend_status

    def test_full_lifecycle_status_matches_at_every_step(self):
        mobile = "9400000001"
        r = submit_report(mobile, "Full lifecycle test: broken drainage cover blocking the footpath")
        self.assertEqual(r.status_code, 200, r.text)
        complaint_id = r.json()["complaint_id"]

        db = SessionLocal()
        issue = db.query(Issue).filter(Issue.complaint_id == complaint_id).first()
        issue_id = issue.id
        db.close()

        # 1) Immediately after submission — SUBMITTED or MANUAL_REVIEW,
        # whichever validator.py's real, unmodified decision produced.
        # Never "accepted" or "in progress" at this point either way.
        status_now = self._assert_citizen_endpoints_match_backend(complaint_id, mobile, issue_id)
        self.assertIn(status_now, ("SUBMITTED", "MANUAL_REVIEW", "ASSIGNED"))
        self.assertNotIn(status_now, ("ACCEPTED", "IN_PROGRESS", "AWAITING_CITIZEN_VERIFICATION", "RESOLVED"))

        headers = _staff_headers()
        if status_now == "MANUAL_REVIEW":
            approve = client.post(f"/staff/issues/{issue_id}/review-decision", json={"decision": "APPROVED"}, headers=headers)
            self.assertEqual(approve.status_code, 200, approve.text)
            status_now = self._assert_citizen_endpoints_match_backend(complaint_id, mobile, issue_id)
            self.assertEqual(status_now, "ASSIGNED")

        # 2) Before staff accepts: must NOT show ACCEPTED or IN_PROGRESS.
        pre_accept_status = self._assert_citizen_endpoints_match_backend(complaint_id, mobile, issue_id)
        self.assertNotIn(pre_accept_status, ("ACCEPTED", "IN_PROGRESS"))

        # 3) Staff accepts.
        accept_resp = client.post(f"/staff/issues/{issue_id}/accept", headers=headers)
        self.assertEqual(accept_resp.status_code, 200, accept_resp.text)
        self._assert_citizen_endpoints_match_backend(complaint_id, mobile, issue_id)
        self.assertEqual(_current_backend_status(issue_id), "ACCEPTED")

        # 4) Staff starts work.
        start_resp = client.post(f"/staff/issues/{issue_id}/start-work", headers=headers)
        self.assertEqual(start_resp.status_code, 200, start_resp.text)
        self._assert_citizen_endpoints_match_backend(complaint_id, mobile, issue_id)
        self.assertEqual(_current_backend_status(issue_id), "IN_PROGRESS")

        # 5) Staff resolves -> AWAITING_CITIZEN_VERIFICATION.
        resolve_resp = client.post(
            f"/staff/issues/{issue_id}/resolve", data={"note": "Fixed."},
            files={"image": ("after.jpg", make_jpeg_bytes((10, 200, 10)), "image/jpeg")}, headers=headers,
        )
        self.assertEqual(resolve_resp.status_code, 200, resolve_resp.text)
        self._assert_citizen_endpoints_match_backend(complaint_id, mobile, issue_id)
        self.assertEqual(_current_backend_status(issue_id), "AWAITING_CITIZEN_VERIFICATION")

        # 6) Citizen rejects the resolution -> REOPENED.
        reject_resp = client.post(f"/issues/{complaint_id}/confirm-resolution", json={"confirmed": False})
        self.assertEqual(reject_resp.status_code, 200, reject_resp.text)
        self._assert_citizen_endpoints_match_backend(complaint_id, mobile, issue_id)
        self.assertEqual(_current_backend_status(issue_id), "REOPENED")

        # 7) Staff works it again and citizen confirms -> RESOLVED.
        client.post(f"/staff/issues/{issue_id}/start-work", headers=headers)
        client.post(
            f"/staff/issues/{issue_id}/resolve", data={"note": "Fixed for real this time."},
            files={"image": ("after2.jpg", make_jpeg_bytes((5, 5, 5)), "image/jpeg")}, headers=headers,
        )
        confirm_resp = client.post(f"/issues/{complaint_id}/confirm-resolution", json={"confirmed": True})
        self.assertEqual(confirm_resp.status_code, 200, confirm_resp.text)
        self._assert_citizen_endpoints_match_backend(complaint_id, mobile, issue_id)
        self.assertEqual(_current_backend_status(issue_id), "RESOLVED")

    def test_manual_review_status_is_reported_as_is_not_masked(self):
        # A report that lands in MANUAL_REVIEW (e.g. low validity score)
        # must be reported as exactly that — never silently shown as a
        # later stage.
        mobile = "9400000002"
        r = submit_report(mobile, "x")  # very thin description -> more likely to need review
        self.assertEqual(r.status_code, 200, r.text)
        complaint_id = r.json()["complaint_id"]
        track_resp = client.get(f"/citizen/reports/{complaint_id}")
        self.assertEqual(track_resp.status_code, 200)
        self.assertNotIn(track_resp.json()["status"], ("ACCEPTED", "IN_PROGRESS", "RESOLVED"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
