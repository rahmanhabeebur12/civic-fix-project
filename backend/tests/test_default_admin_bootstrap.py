"""
tests/test_default_admin_bootstrap.py

Root-cause regression test for: staff/admin login (admin/admin123) works
locally but fails on a fresh Render PostgreSQL deployment.

A brand-new database only gets its schema from Base.metadata.create_all()
-- it has no rows. Nothing previously ran app.seed's staff-seeding logic
automatically, so the demo admin account never existed on a fresh
database and login correctly returned "invalid credentials" (the account
simply wasn't there). app.main now calls the same idempotent
seed_departments()/seed_staff() functions on startup (see
app.main._ensure_default_staff_accounts), so every fresh database gets
the demo staff accounts, and restarting never creates duplicates or
touches citizen accounts.

This test uses its own fresh, isolated SQLite database per the
established pattern (env vars set before importing app.main), so
importing app.main here is itself "a fresh database on startup".

Run with:
    cd backend && venv/bin/python -m unittest tests.test_default_admin_bootstrap -v
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-admin-bootstrap-")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DIR, "uploads")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DIR, 'test.db')}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app, _ensure_default_staff_accounts  # noqa: E402
from app.models.department import Department  # noqa: E402
from app.models.staff import StaffUser  # noqa: E402

client = TestClient(app)


class DefaultAdminAccountBootstrapTests(unittest.TestCase):
    def test_admin_account_exists_on_a_fresh_database(self):
        db = SessionLocal()
        try:
            admin = db.query(StaffUser).filter(StaffUser.username == "admin").first()
            self.assertIsNotNone(admin, "a fresh database must already have the demo admin staff account")
            self.assertEqual(admin.role, "admin")
        finally:
            db.close()

    def test_admin_login_succeeds_with_the_documented_demo_credentials(self):
        resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(resp.status_code, 200, resp.text)
        body = resp.json()
        self.assertIn("access_token", body)
        self.assertEqual(body["role"], "admin")

    def test_admin_password_is_never_stored_in_plaintext(self):
        db = SessionLocal()
        try:
            admin = db.query(StaffUser).filter(StaffUser.username == "admin").first()
            self.assertNotEqual(admin.password_hash, "admin123")
            self.assertTrue(admin.password_hash.startswith("$"), "password_hash must be a hashed value, not plaintext")
        finally:
            db.close()

    def test_admin_password_hash_is_never_exposed_by_the_api(self):
        resp = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertNotIn("password", resp.text.lower())
        self.assertNotIn("$pbkdf2", resp.text)

        token = resp.json()["access_token"]
        me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me.status_code, 200)
        self.assertNotIn("password", me.text.lower())

    def test_rerunning_the_bootstrap_does_not_create_duplicate_staff_or_departments(self):
        db = SessionLocal()
        try:
            staff_before = db.query(StaffUser).count()
            dept_before = db.query(Department).count()
        finally:
            db.close()

        # Simulates a backend restart against the same (now non-empty)
        # database -- e.g. a Render redeploy.
        _ensure_default_staff_accounts()
        _ensure_default_staff_accounts()

        db = SessionLocal()
        try:
            self.assertEqual(db.query(StaffUser).count(), staff_before,
                              "restarting the backend must not create duplicate staff accounts")
            self.assertEqual(db.query(Department).count(), dept_before,
                              "restarting the backend must not create duplicate departments")
            self.assertEqual(db.query(StaffUser).filter(StaffUser.username == "admin").count(), 1)
        finally:
            db.close()

    def test_bootstrap_does_not_create_any_demo_issues(self):
        # This is a login-account fix, not a "populate production with
        # fake demo data" fix -- the heavier seed_pois/seed_issues demo
        # dataset must stay opt-in (python -m app.seed), never automatic.
        from app.models.issue import Issue
        db = SessionLocal()
        try:
            self.assertEqual(db.query(Issue).count(), 0)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
