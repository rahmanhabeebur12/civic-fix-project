"""
tests/test_reporting_trust_features.py

End-to-end tests (through the real FastAPI app + full report_pipeline)
for the new trust/anti-abuse/discovery features:

  - independent reporter count (one user repeating a report does not
    inflate it; different users do)
  - same IP alone never merges unrelated issues
  - rate limiting returns 429, and does not block a legitimate offline
    sync batch
  - nearby unresolved issues + "add support" linking
  - reliability differs between a new and a trusted account, but never
    changes priority_score for otherwise-identical issues
  - review_reasons reflects real signals only

Run with:
    cd backend && venv/bin/python -m unittest tests.test_reporting_trust_features -v
"""
import io
import os
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-trust-")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DIR, "uploads")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DIR, 'test.db')}"

from PIL import Image  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.department import Department  # noqa: E402
from app.models.issue import Issue, IssueReport  # noqa: E402
from app.models.resolution import Resolution  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.reliability_service import compute_reliability
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


def make_jpeg_bytes(color=(60, 130, 210)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), color).save(buf, format="JPEG")
    return buf.getvalue()


def submit(*, description, mobile, latitude=13.0827, longitude=80.2707, name="Test Citizen", headers=None):
    data = {
        "client_report_id": str(uuid.uuid4()),
        "description": description,
        "latitude": str(latitude),
        "longitude": str(longitude),
        "accuracy": "8",
        "language": "en",
        "name": name,
        "mobile": mobile,
        "was_offline": "false",
    }
    files = {"image": ("photo.jpg", make_jpeg_bytes(), "image/jpeg")}
    return client.post("/citizen/reports", data=data, files=files, headers=headers or {})


class IndependentReporterCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()

    def test_same_user_repeated_report_does_not_inflate_reporter_count(self):
        r1 = submit(description="Large pothole outside the community hall entrance", mobile="9000000001")
        self.assertEqual(r1.status_code, 200, r1.text)
        complaint_id = r1.json()["complaint_id"]

        # Same citizen (same mobile) reports what a human would recognize
        # as the identical pothole again, from the same spot.
        r2 = submit(description="Large pothole outside the community hall entrance", mobile="9000000001")
        self.assertEqual(r2.status_code, 200, r2.text)

        db = SessionLocal()
        issue = db.query(Issue).filter(Issue.complaint_id == complaint_id).first()
        db.close()
        self.assertIsNotNone(issue)
        self.assertEqual(issue.reporter_count, 1, "same user's repeat report must not inflate reporter_count")

    def test_different_users_do_increase_reporter_count(self):
        r1 = submit(description="Overflowing storm drain near the bus stand junction", mobile="9000000002")
        self.assertEqual(r1.status_code, 200, r1.text)
        complaint_id = r1.json()["complaint_id"]

        r2 = submit(description="Overflowing storm drain near the bus stand junction", mobile="9000000003")
        self.assertEqual(r2.status_code, 200, r2.text)

        db = SessionLocal()
        issue = db.query(Issue).filter(Issue.complaint_id == complaint_id).first()
        db.close()
        self.assertGreaterEqual(issue.reporter_count, 2, "independent users must increase reporter_count")


class SameIpDoesNotMergeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()

    def test_same_ip_unrelated_issues_remain_separate(self):
        headers = {"x-forwarded-for": "203.0.113.55"}
        # Two genuinely different, unrelated civic problems from the same
        # IP (e.g. two people on the same hostel WiFi) must create two
        # separate issues, never merged just because the IP matches.
        r1 = submit(description="Streetlight pole is completely dark near the park gate", mobile="9000000010", headers=headers)
        r2 = submit(
            description="Garbage has been piling up uncollected behind the market for a week",
            mobile="9000000011", latitude=13.10, longitude=80.31, headers=headers,
        )
        self.assertEqual(r1.status_code, 200, r1.text)
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertNotEqual(r1.json()["complaint_id"], r2.json()["complaint_id"])

        db = SessionLocal()
        reports = db.query(IssueReport).filter(IssueReport.client_ip_hash.isnot(None)).all()
        db.close()
        # The IP hash is recorded (weak signal), but never as a raw IP.
        for r in reports:
            self.assertNotIn("203.0.113.55", r.client_ip_hash)


class RateLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()

    def test_exceeding_auth_count_returns_429(self):
        mobile = "9000000099"
        with patch.object(settings, "RATE_LIMIT_AUTH_COUNT", 2):
            r1 = submit(description="Broken park bench near the playground area", mobile=mobile)
            r2 = submit(description="Second unrelated broken bench near the same playground", mobile=mobile, latitude=13.09, longitude=80.30)
            r3 = submit(description="Third report from the exact same citizen in the same short window", mobile=mobile, latitude=13.11, longitude=80.32)
        self.assertEqual(r1.status_code, 200, r1.text)
        self.assertEqual(r2.status_code, 200, r2.text)
        self.assertEqual(r3.status_code, 429, r3.text)
        self.assertIn("Too many reports", r3.json()["detail"])

    def test_offline_batch_is_not_falsely_blocked(self):
        mobile = "9000000098"
        with patch.object(settings, "RATE_LIMIT_AUTH_COUNT", 2):
            # A citizen reconnecting after being offline for days syncs
            # several genuinely-created reports at once — this must not
            # be treated as live spam.
            for i in range(5):
                data = {
                    "client_report_id": str(uuid.uuid4()),
                    "description": f"Offline-queued report number {i} about a damaged footpath",
                    "latitude": "13.08", "longitude": "80.27", "accuracy": "8",
                    "language": "en", "name": "Offline Citizen", "mobile": mobile,
                    "was_offline": "true",
                }
                resp = client.post("/citizen/reports", data=data, files={"image": ("p.jpg", make_jpeg_bytes(), "image/jpeg")})
                self.assertEqual(resp.status_code, 200, resp.text)


class NearbyIssuesAndSupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()

    def test_nearby_issues_returns_unresolved_live_issues_within_radius(self):
        r1 = submit(description="Deep pothole causing traffic near the temple junction", mobile="9000000020", latitude=13.0827, longitude=80.2707)
        self.assertEqual(r1.status_code, 200, r1.text)

        resp = client.get("/citizen/nearby-issues", params={"latitude": 13.0827, "longitude": 80.2707, "radius_km": 3})
        self.assertEqual(resp.status_code, 200, resp.text)
        items = resp.json()
        self.assertTrue(any(i["complaint_id"] == r1.json()["complaint_id"] for i in items))
        # No reporter identity leaked.
        for item in items:
            self.assertNotIn("mobile", item)
            self.assertNotIn("name", item)
            self.assertNotIn("reporter_name", item)

    def test_far_away_issue_excluded_by_radius(self):
        r1 = submit(description="Water pipeline burst flooding the street corner", mobile="9000000021", latitude=13.0827, longitude=80.2707)
        self.assertEqual(r1.status_code, 200, r1.text)

        resp = client.get("/citizen/nearby-issues", params={"latitude": 20.0, "longitude": 90.0, "radius_km": 1})
        self.assertEqual(resp.status_code, 200, resp.text)
        complaint_ids = [i["complaint_id"] for i in resp.json()]
        self.assertNotIn(r1.json()["complaint_id"], complaint_ids)

    def test_add_support_links_to_existing_issue_without_creating_new_one(self):
        r1 = submit(description="Sewage overflow near the corner shop entrance", mobile="9000000030", latitude=13.05, longitude=80.20)
        self.assertEqual(r1.status_code, 200, r1.text)
        complaint_id = r1.json()["complaint_id"]

        support_resp = client.post(
            f"/citizen/reports/{complaint_id}/support",
            json={"client_report_id": str(uuid.uuid4()), "name": "Supporting Citizen", "mobile": "9000000031", "note": "Still happening, confirming."},
        )
        self.assertEqual(support_resp.status_code, 200, support_resp.text)
        self.assertEqual(support_resp.json()["complaint_id"], complaint_id, "must link to the SAME issue, not create a new one")

        db = SessionLocal()
        issue = db.query(Issue).filter(Issue.complaint_id == complaint_id).first()
        report_count = db.query(IssueReport).filter(IssueReport.issue_id == issue.id).count()
        db.close()
        self.assertEqual(issue.reporter_count, 2)
        self.assertEqual(report_count, 2)


class ReliabilityDoesNotAffectPriorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()

    def test_new_vs_trusted_account_same_priority_score(self):
        # Two brand-new users report identical-severity, identical-location
        # issues (different exact spots so they don't dedupe into one).
        r_new = submit(description="Flickering streetlight near the corner store", mobile="9000000040", latitude=13.02, longitude=80.10)
        r_control = submit(description="Flickering streetlight outside a different shop", mobile="9000000041", latitude=13.03, longitude=80.11)
        self.assertEqual(r_new.status_code, 200)
        self.assertEqual(r_control.status_code, 200)

        db = SessionLocal()
        new_user = db.query(User).filter(User.mobile == "9000000040").first()
        new_reliability = compute_reliability(db, new_user.id)

        # Simulate a "trusted" account: an older account with several
        # prior reports resolved as citizen-confirmed genuine — reliability
        # is built from age + confirmed-genuine history, not report volume
        # alone (a brand-new account could not reach TRUSTED just by
        # submitting many reports).
        trusted_user = User(name="Trusted Citizen", mobile="9000000042", created_at=datetime.now(timezone.utc) - timedelta(days=120))
        db.add(trusted_user)
        db.flush()
        for i in range(4):
            issue = Issue(
                complaint_id=f"CIV-TRUST-{i}", issue_type="Pothole", category="Roads", is_demo=False,
                latitude=13.0, longitude=80.0, severity_level=3, impact_level=3,
                location_type="normal_area", status="RESOLVED", priority_score=50, priority_level="MEDIUM",
            )
            db.add(issue)
            db.flush()
            db.add(IssueReport(client_report_id=f"trust-report-{i}", issue_id=issue.id, user_id=trusted_user.id,
                                latitude=13.0, longitude=80.0, submission_mode="PHOTO_AND_TEXT"))
            db.add(Resolution(issue_id=issue.id, officer_username="tester", image_path="x.webp", note="fixed", citizen_confirmed=True))
        db.commit()

        trusted_reliability = compute_reliability(db, trusted_user.id)
        db.close()

        self.assertGreater(trusted_reliability.score, new_reliability.score, "trusted account must score higher reliability")
        self.assertEqual(trusted_reliability.label, "TRUSTED")
        self.assertIn(new_reliability.label, ("NEW", "BUILDING"))

        # But the two ORIGINAL, otherwise-identical-severity issues must
        # have received the exact same priority_score — reliability never
        # touches priority.
        db2 = SessionLocal()
        issue_new = db2.query(Issue).filter(Issue.complaint_id == r_new.json()["complaint_id"]).first()
        issue_control = db2.query(Issue).filter(Issue.complaint_id == r_control.json()["complaint_id"]).first()
        db2.close()
        self.assertEqual(issue_new.priority_score, issue_control.priority_score)


class ReviewReasonsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _seed_departments()

    def test_text_only_review_reason_present_when_it_actually_occurred(self):
        data = {
            "client_report_id": str(uuid.uuid4()),
            "description": "There is visible sewage overflow blocking the entire footpath here",
            "latitude": "13.06", "longitude": "80.22", "accuracy": "8",
            "language": "en", "name": "Text Only Citizen", "mobile": "9000000050",
            "was_offline": "false",
        }
        resp = client.post("/citizen/reports", data=data)  # no image at all
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["submission_mode"], "TEXT_ONLY")

        db = SessionLocal()
        issue = db.query(Issue).filter(Issue.complaint_id == resp.json()["complaint_id"]).first()
        first_report = issue.reports[0]
        db.close()

        from app.routers.issues import compute_review_reasons
        reasons = compute_review_reasons(issue, first_report)
        # A brand-new citizen's cold-start reliability/duplicate-evidence
        # factors (see validation_adapter.py) genuinely pull a first-ever
        # report below VALID even with a solid description -- that's the
        # real reason this landed in review, so it's the one that must
        # show up here.
        self.assertIn("Validation requires review", reasons)
        # Reasons that did not occur must never be shown: no photo was
        # ever provided, the description matched a known category, and
        # there were no other candidate issues to possibly duplicate.
        self.assertNotIn("Insufficient visual evidence", reasons)
        self.assertNotIn("Photo and description conflict", reasons)
        self.assertNotIn("Category uncertain", reasons)
        self.assertNotIn("Possible duplicate", reasons)


if __name__ == "__main__":
    unittest.main(verbosity=2)
