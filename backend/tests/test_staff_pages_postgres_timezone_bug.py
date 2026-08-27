"""
tests/test_staff_pages_postgres_timezone_bug.py

Root-cause regression test for: on the deployed Render (PostgreSQL)
backend, the staff Dashboard, Issues, and Review Queue pages never
finished loading (stuck spinner / silently-empty lists), while the same
code worked fine locally against SQLite.

Root cause: Issue.created_at is declared DateTime(timezone=True).
SQLite ignores that flag and always returns a naive datetime, but
PostgreSQL returns a real timezone-aware one. app.routers.issues.
is_overdue() did `datetime.utcnow() - issue.created_at`, mixing a naive
"now" with (on PostgreSQL only) an aware `created_at` -- Python raises
"TypeError: can't subtract offset-naive and offset-aware datetimes".
is_overdue() is called for every row by _to_summary(), which backs
GET /staff/issues (Issues page, Review Queue, and the Dashboard's
priority list) and by /dashboard/summary's overdue count -- so on
PostgreSQL, as soon as any issue existed, every one of those endpoints
returned an uncaught 500 instead of data.

This test reproduces the exact failure condition without needing a live
PostgreSQL server. Two layers, because SQLite is more lenient than
PostgreSQL here and that leniency is itself part of why this bug wasn't
caught before deployment:

  - IsOverdueTimezoneCompatibilityTests calls is_overdue() directly with
    an in-memory object whose created_at is timezone-aware (exactly what
    PostgreSQL hands back for a DateTime(timezone=True) column). This
    genuinely reproduces the TypeError on unpatched code -- verified by
    temporarily reverting the fix and re-running this file.
  - StaffPagesSurviveTimezoneAwareCreatedAtTests exercises the real HTTP
    endpoints end-to-end. On this project's SQLite test database, a
    tz-aware datetime written to the DB round-trips back as naive (SQLite
    has no real timestamptz type), so these do NOT reproduce the crash by
    themselves -- they exist as defense-in-depth / a schema-shape check,
    and still assert 200 + correct field types either way.

Run with:
    cd backend && venv/bin/python -m unittest tests.test_staff_pages_postgres_timezone_bug -v
"""
import io
import os
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-tz-bug-")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DIR, "uploads")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DIR, 'test.db')}"

from PIL import Image  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.department import Department  # noqa: E402
from app.models.issue import Issue  # noqa: E402
from app.models.staff import StaffUser  # noqa: E402
from app.routers.issues import is_overdue  # noqa: E402
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


def _seed_staff(username="tztester", password="tztesterpass1"):
    db = SessionLocal()
    try:
        if not db.query(StaffUser).filter(StaffUser.username == username).first():
            db.add(StaffUser(username=username, password_hash=hash_password(password), full_name="TZ Tester", role="admin"))
            db.commit()
    finally:
        db.close()


def _staff_headers():
    resp = client.post("/auth/login", json={"username": "tztester", "password": "tztesterpass1"})
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
        "language": "en", "name": "TZ Bug Tester", "mobile": mobile, "was_offline": "false",
    }
    files = {"image": ("photo.jpg", make_jpeg_bytes(), "image/jpeg")}
    return client.post("/citizen/reports", data=data, files=files)


def _force_timezone_aware_created_at(issue_id: int, hours_ago: float = 5) -> None:
    """Simulates exactly what PostgreSQL hands back for a
    DateTime(timezone=True) column -- a real tz-aware datetime -- on top
    of a SQLite test database, which would otherwise silently stay
    naive and hide this bug."""
    db = SessionLocal()
    try:
        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        issue.created_at = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        db.commit()
    finally:
        db.close()


class IsOverdueTimezoneCompatibilityTests(unittest.TestCase):
    """Unit-level coverage of the exact function that crashed."""

    class _FakeIssue:
        def __init__(self, status, severity, created_at):
            self.status = status
            self.severity = severity
            self.created_at = created_at

    def test_is_overdue_accepts_a_timezone_aware_created_at_without_raising(self):
        # This is exactly what PostgreSQL returns for DateTime(timezone=True).
        aware = datetime.now(timezone.utc) - timedelta(hours=100)
        issue = self._FakeIssue(status="SUBMITTED", severity="CRITICAL", created_at=aware)
        result = is_overdue(issue)  # must not raise TypeError
        self.assertTrue(result, "a CRITICAL issue 100h old is well past its 4h SLA")

    def test_is_overdue_accepts_a_naive_created_at_without_raising(self):
        # This is what SQLite returns -- must keep working too.
        naive = datetime.utcnow() - timedelta(hours=100)
        issue = self._FakeIssue(status="SUBMITTED", severity="CRITICAL", created_at=naive)
        result = is_overdue(issue)
        self.assertTrue(result)

    def test_is_overdue_false_for_a_recent_timezone_aware_issue(self):
        aware = datetime.now(timezone.utc) - timedelta(minutes=5)
        issue = self._FakeIssue(status="SUBMITTED", severity="CRITICAL", created_at=aware)
        self.assertFalse(is_overdue(issue))

    def test_is_overdue_false_for_past_issue_statuses_regardless_of_tzinfo(self):
        aware = datetime.now(timezone.utc) - timedelta(hours=1000)
        issue = self._FakeIssue(status="RESOLVED", severity="CRITICAL", created_at=aware)
        self.assertFalse(is_overdue(issue))


class StaffPagesSurviveTimezoneAwareCreatedAtTests(unittest.TestCase):
    """End-to-end: the exact endpoints backing the Dashboard, Issues, and
    Review Queue pages must return 200 (not 500) even when created_at is
    timezone-aware, exactly as PostgreSQL would hand it back."""

    @classmethod
    def setUpClass(cls):
        _seed_departments()
        _seed_staff()

    def setUp(self):
        self.headers = _staff_headers()

    def _make_aware_issue(self, mobile: str, description: str) -> int:
        r = submit_report(mobile, description)
        self.assertEqual(r.status_code, 200, r.text)
        db = SessionLocal()
        try:
            issue = db.query(Issue).filter(Issue.complaint_id == r.json()["complaint_id"]).first()
            issue_id = issue.id
        finally:
            db.close()
        _force_timezone_aware_created_at(issue_id, hours_ago=10)
        return issue_id

    def test_staff_issues_list_survives_a_timezone_aware_created_at(self):
        # Backs the Issues page and the Dashboard's priority issue list.
        self._make_aware_issue("9600000001", "Pothole with a timezone-aware created_at, simulating PostgreSQL")
        resp = client.get("/staff/issues?active_only=true&data_scope=live", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertGreaterEqual(len(body), 1)
        self.assertIn("is_overdue", body[0])
        self.assertIsInstance(body[0]["is_overdue"], bool)

    def test_review_queue_survives_a_timezone_aware_created_at(self):
        self._make_aware_issue("9600000002", "x")  # thin description -> likely MANUAL_REVIEW
        resp = client.get("/staff/issues?status=MANUAL_REVIEW", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_dashboard_summary_survives_a_timezone_aware_created_at(self):
        self._make_aware_issue("9600000003", "Streetlight out near the crossing, timezone-aware created_at case")
        resp = client.get("/dashboard/summary?data_scope=live", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("overdue_issues", body)
        self.assertIsInstance(body["overdue_issues"], int)

    def test_dashboard_map_survives_a_timezone_aware_created_at(self):
        self._make_aware_issue("9600000004", "Overflowing drain, timezone-aware created_at case")
        resp = client.get("/dashboard/map?data_scope=live", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)

    def test_overdue_flag_is_actually_correct_for_a_timezone_aware_old_critical_issue(self):
        # Not just "doesn't crash" -- the computed value must still be right.
        issue_id = self._make_aware_issue("9600000005", "Live wire hanging dangerously low near the bus stop")
        db = SessionLocal()
        try:
            issue = db.query(Issue).filter(Issue.id == issue_id).first()
            issue.severity = "CRITICAL"  # 4h SLA
            db.commit()
        finally:
            db.close()
        _force_timezone_aware_created_at(issue_id, hours_ago=48)  # well past 4h SLA

        resp = client.get(f"/staff/issues/{issue_id}", headers=self.headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["is_overdue"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
