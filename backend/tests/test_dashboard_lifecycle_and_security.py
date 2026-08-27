"""
tests/test_dashboard_lifecycle_and_security.py

Covers three fixes in one pass, since they share the same isolated
TestClient/DB setup:

  1. RESOLVED issues disappear from the active dashboard (/dashboard/map,
     /dashboard/summary's open_issues count, /staff/issues?active_only=true)
     but remain in the database and are
     reachable via /staff/issues?status=RESOLVED (Past Issues). A
     citizen-rejected resolution (REOPENED) moves the issue back to the
     active views and out of Past Issues, with no data deleted.
  2. No API response (staff login/me, citizen login/register/me) ever
     serializes password or password_hash.

Run with:
    cd backend && venv/bin/python -m unittest tests.test_dashboard_lifecycle_and_security -v
"""
import io
import os
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-dashboard-")
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


def _seed_staff(username="teststaff", password="teststaffpass1", role="admin"):
    db = SessionLocal()
    try:
        existing = db.query(StaffUser).filter(StaffUser.username == username).first()
        if existing:
            return
        db.add(StaffUser(username=username, password_hash=hash_password(password), full_name="Test Staff", role=role))
        db.commit()
    finally:
        db.close()


def _staff_token(username="teststaff", password="teststaffpass1"):
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def make_jpeg_bytes(color=(80, 150, 230)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), color).save(buf, format="JPEG")
    return buf.getvalue()


def submit_report(*, description, mobile, latitude=13.05, longitude=80.20):
    data = {
        "client_report_id": str(uuid.uuid4()),
        "description": description,
        "latitude": str(latitude), "longitude": str(longitude), "accuracy": "8",
        "language": "en", "name": "Lifecycle Tester", "mobile": mobile, "was_offline": "false",
    }
    files = {"image": ("photo.jpg", make_jpeg_bytes(), "image/jpeg")}
    return client.post("/citizen/reports", data=data, files=files)


def _push_issue_to_resolved(headers, issue_id):
    """Drives an issue through accept -> start-work -> resolve ->
    citizen-confirms-fixed, exactly the same sequence a real officer/
    citizen would use — no shortcuts through internal state."""
    db = SessionLocal()
    status = db.query(Issue).get(issue_id).status
    db.close()
    if status == "MANUAL_REVIEW":
        approve_resp = client.post(f"/staff/issues/{issue_id}/review-decision", json={"decision": "APPROVED"}, headers=headers)
        assert approve_resp.status_code == 200, approve_resp.text

    assert client.post(f"/staff/issues/{issue_id}/accept", headers=headers).status_code == 200
    assert client.post(f"/staff/issues/{issue_id}/start-work", headers=headers).status_code == 200
    resolve_resp = client.post(
        f"/staff/issues/{issue_id}/resolve",
        data={"note": "Fixed the pothole."},
        files={"image": ("after.jpg", make_jpeg_bytes((10, 200, 10)), "image/jpeg")},
        headers=headers,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text

    db = SessionLocal()
    issue = db.query(Issue).get(issue_id)
    complaint_id = issue.complaint_id
    db.close()

    confirm_resp = client.post(f"/issues/{complaint_id}/confirm-resolution", json={"confirmed": True})
    assert confirm_resp.status_code == 200, confirm_resp.text
    return complaint_id


class ResolvedIssueDashboardScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()
        _seed_staff()

    def setUp(self):
        self.headers = {"Authorization": f"Bearer {_staff_token()}"}

    def test_resolved_issue_excluded_from_dashboard_map(self):
        r = submit_report(description="Streetlight has been broken for a week near the crossing", mobile="9200000001")
        self.assertEqual(r.status_code, 200, r.text)
        issue_id = self._issue_id(r.json()["complaint_id"])

        map_before = client.get("/dashboard/map?data_scope=live", headers=self.headers).json()
        self.assertIn(r.json()["complaint_id"], [m["complaint_id"] for m in map_before])

        _push_issue_to_resolved(self.headers, issue_id)

        map_after = client.get("/dashboard/map?data_scope=live", headers=self.headers).json()
        self.assertNotIn(r.json()["complaint_id"], [m["complaint_id"] for m in map_after],
                          "RESOLVED issue must disappear from the active dashboard map")

    def test_resolved_issue_excluded_from_active_only_issue_list(self):
        r = submit_report(description="Overflowing garbage bin behind the community hall", mobile="9200000002")
        issue_id = self._issue_id(r.json()["complaint_id"])
        _push_issue_to_resolved(self.headers, issue_id)

        active = client.get("/staff/issues?active_only=true&data_scope=live", headers=self.headers).json()
        self.assertNotIn(r.json()["complaint_id"], [i["complaint_id"] for i in active])

    def test_resolved_issue_not_deleted_still_reachable_by_status_filter(self):
        r = submit_report(description="Sewage overflow near the corner shop causing a bad smell", mobile="9200000003")
        issue_id = self._issue_id(r.json()["complaint_id"])
        _push_issue_to_resolved(self.headers, issue_id)

        # Still fully present in the database — findable via a direct
        # ID lookup and via the RESOLVED status filter (Past Issues).
        detail = client.get(f"/staff/issues/{issue_id}", headers=self.headers)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["status"], "RESOLVED")

        past = client.get("/staff/issues?status=RESOLVED&data_scope=live", headers=self.headers).json()
        complaint_ids = [i["complaint_id"] for i in past]
        self.assertIn(r.json()["complaint_id"], complaint_ids)
        matching = next(i for i in past if i["complaint_id"] == r.json()["complaint_id"])
        self.assertIsNotNone(matching["resolved_at"], "Past Issues rows must carry resolved_at")

    def test_reopened_issue_returns_to_active_dashboard_and_leaves_past_issues(self):
        # A citizen who rejects resolution evidence (confirmed=False) is
        # this app's "reopen" mechanism (there is no separate "reopen an
        # already-RESOLVED issue" endpoint) — the issue must never sit in
        # Past Issues/off the active dashboard while REOPENED.
        r = submit_report(description="Water pipeline leak flooding the footpath area", mobile="9200000004")
        issue_id = self._issue_id(r.json()["complaint_id"])
        complaint_id = r.json()["complaint_id"]

        db = SessionLocal()
        status = db.query(Issue).get(issue_id).status
        db.close()
        if status == "MANUAL_REVIEW":
            self.assertEqual(client.post(f"/staff/issues/{issue_id}/review-decision", json={"decision": "APPROVED"}, headers=self.headers).status_code, 200)
        self.assertEqual(client.post(f"/staff/issues/{issue_id}/accept", headers=self.headers).status_code, 200)
        self.assertEqual(client.post(f"/staff/issues/{issue_id}/start-work", headers=self.headers).status_code, 200)
        resolve_resp = client.post(
            f"/staff/issues/{issue_id}/resolve",
            data={"note": "Attempted fix."},
            files={"image": ("after.jpg", make_jpeg_bytes((5, 5, 5)), "image/jpeg")},
            headers=self.headers,
        )
        self.assertEqual(resolve_resp.status_code, 200, resolve_resp.text)

        reject_resp = client.post(f"/issues/{complaint_id}/confirm-resolution", json={"confirmed": False, "feedback": "Still broken"})
        self.assertEqual(reject_resp.status_code, 200, reject_resp.text)
        self.assertEqual(reject_resp.json()["status"], "REOPENED")

        active_after_reopen = client.get("/staff/issues?active_only=true&data_scope=live", headers=self.headers).json()
        self.assertIn(complaint_id, [i["complaint_id"] for i in active_after_reopen],
                       "a reopened issue must be on the active dashboard")

        map_after_reopen = client.get("/dashboard/map?data_scope=live", headers=self.headers).json()
        self.assertIn(complaint_id, [m["complaint_id"] for m in map_after_reopen])

        past_after_reopen = client.get("/staff/issues?status=RESOLVED&data_scope=live", headers=self.headers).json()
        self.assertNotIn(complaint_id, [i["complaint_id"] for i in past_after_reopen],
                          "a REOPENED issue is not RESOLVED, so it must not appear in Past Issues")

    def test_resolved_then_worked_again_and_finally_confirmed_ends_up_resolved_not_active(self):
        # Full realistic cycle: reopen (reject) -> officer works it again
        # (start-work directly from REOPENED, then resolve) -> citizen
        # confirms this time -> RESOLVED again -> back out of the active
        # dashboard, back into Past Issues. Nothing is ever deleted.
        r = submit_report(description="Damaged manhole cover near the school gate", mobile="9200000005")
        issue_id = self._issue_id(r.json()["complaint_id"])
        complaint_id = r.json()["complaint_id"]

        db = SessionLocal()
        status = db.query(Issue).get(issue_id).status
        db.close()
        if status == "MANUAL_REVIEW":
            client.post(f"/staff/issues/{issue_id}/review-decision", json={"decision": "APPROVED"}, headers=self.headers)
        client.post(f"/staff/issues/{issue_id}/accept", headers=self.headers)
        client.post(f"/staff/issues/{issue_id}/start-work", headers=self.headers)
        client.post(
            f"/staff/issues/{issue_id}/resolve", data={"note": "First attempt."},
            files={"image": ("a.jpg", make_jpeg_bytes((1, 1, 1)), "image/jpeg")}, headers=self.headers,
        )
        client.post(f"/issues/{complaint_id}/confirm-resolution", json={"confirmed": False})  # -> REOPENED

        # REOPENED -> start-work is allowed directly (no accept needed).
        self.assertEqual(client.post(f"/staff/issues/{issue_id}/start-work", headers=self.headers).status_code, 200)
        resolve_again = client.post(
            f"/staff/issues/{issue_id}/resolve", data={"note": "Second attempt, properly fixed."},
            files={"image": ("b.jpg", make_jpeg_bytes((2, 2, 2)), "image/jpeg")}, headers=self.headers,
        )
        self.assertEqual(resolve_again.status_code, 200, resolve_again.text)
        confirm_again = client.post(f"/issues/{complaint_id}/confirm-resolution", json={"confirmed": True})
        self.assertEqual(confirm_again.status_code, 200, confirm_again.text)
        self.assertEqual(confirm_again.json()["status"], "RESOLVED")

        active_final = client.get("/staff/issues?active_only=true&data_scope=live", headers=self.headers).json()
        self.assertNotIn(complaint_id, [i["complaint_id"] for i in active_final])
        past_final = client.get("/staff/issues?status=RESOLVED&data_scope=live", headers=self.headers).json()
        self.assertIn(complaint_id, [i["complaint_id"] for i in past_final])

    def test_dashboard_summary_open_issues_excludes_resolved(self):
        # /dashboard/summary's open_issues count must use the same
        # active/past status definition as the map and the Issues page
        # (app.routers.issues.PAST_ISSUE_STATUSES) -- not a separate,
        # independently-maintained status list that could drift.
        before = client.get("/dashboard/summary?data_scope=live", headers=self.headers).json()["open_issues"]

        r = submit_report(description="Blocked stormwater drain outside the bus stand", mobile="9200000006")
        issue_id = self._issue_id(r.json()["complaint_id"])

        after_submit = client.get("/dashboard/summary?data_scope=live", headers=self.headers).json()["open_issues"]
        self.assertEqual(after_submit, before + 1, "a freshly submitted issue must count as open")

        _push_issue_to_resolved(self.headers, issue_id)

        after_resolve = client.get("/dashboard/summary?data_scope=live", headers=self.headers).json()["open_issues"]
        self.assertEqual(after_resolve, before, "a RESOLVED issue must no longer count as open")

    def _issue_id(self, complaint_id: str) -> int:
        db = SessionLocal()
        try:
            issue = db.query(Issue).filter(Issue.complaint_id == complaint_id).first()
            self.assertIsNotNone(issue)
            return issue.id
        finally:
            db.close()


class NoCredentialLeakInApiResponsesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()
        _seed_staff(username="secuser", password="secuserpass1")

    def test_staff_login_response_has_no_password_fields(self):
        resp = client.post("/auth/login", json={"username": "secuser", "password": "secuserpass1"})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self._assert_no_password_keys(body)
        self.assertEqual(set(body.keys()), {"access_token", "token_type", "username", "full_name", "role", "department"})

    def test_staff_me_response_has_no_password_fields(self):
        token = _staff_token("secuser", "secuserpass1")
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self._assert_no_password_keys(body)
        self.assertEqual(set(body.keys()), {"username", "full_name", "role", "department"})

    def test_citizen_register_and_me_have_no_password_fields(self):
        reg = client.post("/auth/citizen/register", json={"name": "Sec Citizen", "mobile": "9200000099", "password": "citizenpass1"})
        self.assertEqual(reg.status_code, 200, reg.text)
        self._assert_no_password_keys(reg.json())
        self.assertEqual(set(reg.json().keys()), {"access_token", "token_type", "name", "mobile"})

        token = reg.json()["access_token"]
        me = client.get("/auth/citizen/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.status_code, 200, me.text)
        self._assert_no_password_keys(me.json())

    def test_raw_response_body_never_contains_the_word_hash_of_password(self):
        # Belt-and-braces: scan the raw JSON text, not just top-level keys,
        # in case a nested/renamed field ever leaked a hash-looking value.
        token = _staff_token("secuser", "secuserpass1")
        resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertNotIn("$pbkdf2", resp.text)
        self.assertNotIn("password_hash", resp.text)

    def _assert_no_password_keys(self, body: dict):
        for key in body.keys():
            self.assertNotIn("password", key.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
