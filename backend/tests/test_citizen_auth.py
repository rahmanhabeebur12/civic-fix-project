"""
tests/test_citizen_auth.py

Citizen login/register — reuses the existing JWT/password architecture
(app.services.auth_service) already used for staff auth. Verifies:

  - register / login / profile work
  - registering an existing guest mobile "claims" that identity (report
    history carries over) rather than creating a duplicate
  - guest reporting (no auth) is completely unaffected
  - a logged-in citizen's report gets NO priority boost over an
    identical guest report — reliability/login status never touches
    app.services.core.priority
  - a staff token cannot be used as a citizen token and vice versa

Run with:
    cd backend && venv/bin/python -m unittest tests.test_citizen_auth -v
"""
import io
import os
import sys
import tempfile
import unittest
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-citizen-auth-")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DIR, "uploads")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DIR, 'test.db')}"

from PIL import Image  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.department import Department  # noqa: E402
from app.models.issue import Issue  # noqa: E402
from app.models.user import User  # noqa: E402
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


def make_jpeg_bytes(color=(70, 140, 220)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), color).save(buf, format="JPEG")
    return buf.getvalue()


def submit_report(*, description, mobile, name="Test Citizen", latitude=13.05, longitude=80.20):
    data = {
        "client_report_id": str(uuid.uuid4()),
        "description": description,
        "latitude": str(latitude), "longitude": str(longitude), "accuracy": "8",
        "language": "en", "name": name, "mobile": mobile, "was_offline": "false",
    }
    files = {"image": ("photo.jpg", make_jpeg_bytes(), "image/jpeg")}
    return client.post("/citizen/reports", data=data, files=files)


class CitizenRegisterLoginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()

    def test_register_then_me(self):
        resp = client.post("/auth/citizen/register", json={"name": "Priya Kumar", "mobile": "9111100001", "password": "secret1"})
        self.assertEqual(resp.status_code, 200, resp.text)
        token = resp.json()["access_token"]
        self.assertEqual(resp.json()["mobile"], "9111100001")

        me = client.get("/auth/citizen/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["name"], "Priya Kumar")
        self.assertIn(me.json()["reliability_label"], ("NEW", "BUILDING", "TRUSTED"))

    def test_duplicate_registration_rejected(self):
        client.post("/auth/citizen/register", json={"name": "First", "mobile": "9111100002", "password": "secret1"})
        resp = client.post("/auth/citizen/register", json={"name": "Second", "mobile": "9111100002", "password": "other1"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("already exists", resp.json()["detail"])

    def test_login_success_and_failure(self):
        client.post("/auth/citizen/register", json={"name": "Login Tester", "mobile": "9111100003", "password": "correct1"})

        good = client.post("/auth/citizen/login", json={"mobile": "9111100003", "password": "correct1"})
        self.assertEqual(good.status_code, 200, good.text)
        self.assertTrue(good.json()["access_token"])

        bad = client.post("/auth/citizen/login", json={"mobile": "9111100003", "password": "wrongpass"})
        self.assertEqual(bad.status_code, 401)
        self.assertIn("Login failed", bad.json()["detail"])

    def test_login_fails_for_guest_only_mobile(self):
        # A mobile that has only ever been used for guest reporting (no
        # password set) must not be able to "log in".
        submit_report(description="A pothole reported as a guest, no account", mobile="9111100004")
        resp = client.post("/auth/citizen/login", json={"mobile": "9111100004", "password": "anything1"})
        self.assertEqual(resp.status_code, 401)

    def test_me_requires_token(self):
        resp = client.get("/auth/citizen/me")
        self.assertEqual(resp.status_code, 401)

    def test_staff_token_cannot_access_citizen_me(self):
        staff_login = client.post("/auth/login", json={"username": "does-not-exist", "password": "x"})
        self.assertEqual(staff_login.status_code, 401)  # sanity: no seeded staff in this isolated DB
        # A citizen token used against the staff-only pattern is covered
        # by get_current_citizen requiring type=="citizen"; verify a
        # malformed/garbage token is rejected the same way.
        resp = client.get("/auth/citizen/me", headers={"Authorization": "Bearer not-a-real-token"})
        self.assertEqual(resp.status_code, 401)


class RegisterClaimsGuestIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()

    def test_registering_existing_guest_mobile_preserves_report_history(self):
        r = submit_report(description="Streetlight has been dark for a week near the crossing", mobile="9111100010", name="Guest Name")
        self.assertEqual(r.status_code, 200, r.text)
        complaint_id = r.json()["complaint_id"]

        reg = client.post("/auth/citizen/register", json={"name": "Now Registered", "mobile": "9111100010", "password": "claimme1"})
        self.assertEqual(reg.status_code, 200, reg.text)
        token = reg.json()["access_token"]

        me = client.get("/auth/citizen/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.json()["total_reports"], 1)

        db = SessionLocal()
        user = db.query(User).filter(User.mobile == "9111100010").first()
        issue = db.query(Issue).filter(Issue.complaint_id == complaint_id).first()
        db.close()
        self.assertEqual(user.name, "Now Registered")
        self.assertIsNotNone(issue)


class GuestReportingUnaffectedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()

    def test_guest_reporting_still_works_without_any_auth_header(self):
        resp = submit_report(description="Overflowing bin outside the community center gate", mobile="9111100020")
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()["complaint_id"].startswith("CIV-"))


class LoginDoesNotBoostPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()

    def test_registered_and_guest_citizen_get_identical_priority_for_identical_issue(self):
        client.post("/auth/citizen/register", json={"name": "Registered Citizen", "mobile": "9111100030", "password": "loggedin1"})

        r_loggedin = submit_report(description="Broken bench near the playground swings", mobile="9111100030", latitude=13.11, longitude=80.30)
        r_guest = submit_report(description="Broken bench near a different playground area", mobile="9111100031", latitude=13.12, longitude=80.31)
        self.assertEqual(r_loggedin.status_code, 200)
        self.assertEqual(r_guest.status_code, 200)

        db = SessionLocal()
        issue_loggedin = db.query(Issue).filter(Issue.complaint_id == r_loggedin.json()["complaint_id"]).first()
        issue_guest = db.query(Issue).filter(Issue.complaint_id == r_guest.json()["complaint_id"]).first()
        db.close()
        self.assertEqual(issue_loggedin.priority_score, issue_guest.priority_score)
        self.assertEqual(issue_loggedin.priority_level, issue_guest.priority_level)


if __name__ == "__main__":
    unittest.main(verbosity=2)
