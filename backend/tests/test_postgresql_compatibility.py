"""
tests/test_postgresql_compatibility.py

Verifies the app's DB-layer code path is PostgreSQL-compatible WITHOUT
requiring a live PostgreSQL server in this environment (none is
available here) — it checks engine construction (SQLAlchemy only
actually connects on first use, so create_engine() itself never touches
the network) and that no model uses a SQLite-only column type.

Live PostgreSQL connectivity itself was NOT exercised end-to-end in this
sandbox — see the completion report for what that means for a real
deployment.

Run with:
    cd backend && venv/bin/python -m unittest tests.test_postgresql_compatibility -v
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-pg-")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DIR, "uploads")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DIR, 'test.db')}"

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text  # noqa: E402

from app.database import Base, build_engine_kwargs  # noqa: E402
from app.main import app  # noqa: E402  (imports every model via routers)


class EngineKwargsTests(unittest.TestCase):
    def test_sqlite_gets_check_same_thread_false(self):
        kwargs = build_engine_kwargs("sqlite:///./civicfix.db")
        self.assertEqual(kwargs["connect_args"], {"check_same_thread": False})
        self.assertFalse(kwargs["pool_pre_ping"])

    def test_postgresql_gets_no_sqlite_only_args(self):
        kwargs = build_engine_kwargs("postgresql+psycopg://user:pass@host:5432/civicfix")
        self.assertEqual(kwargs["connect_args"], {})
        self.assertTrue(kwargs["pool_pre_ping"])

    def test_postgresql_engine_constructs_without_connecting(self):
        # create_engine() is lazy — it never opens a connection until a
        # query actually runs, so this proves the URL/driver wiring is
        # valid without needing a live PostgreSQL server.
        engine = create_engine(
            "postgresql+psycopg://user:pass@localhost:5432/civicfix_test",
            **build_engine_kwargs("postgresql+psycopg://user:pass@localhost:5432/civicfix_test"),
        )
        self.assertEqual(engine.url.get_backend_name(), "postgresql")
        self.assertEqual(engine.url.get_driver_name(), "psycopg")


class ModelColumnPortabilityTests(unittest.TestCase):
    """Every column type used across the models is one of SQLAlchemy's
    portable generic types (String/Text/Integer/Float/Boolean/DateTime),
    which map cleanly onto PostgreSQL equivalents. JSON-shaped data (e.g.
    priority_breakdown) is deliberately stored as Text via json.dumps/
    json.loads rather than a SQLite-only JSON column, so it needs no
    special handling on PostgreSQL either."""

    PORTABLE_TYPES = (String, Text, Integer, Float, Boolean, DateTime)

    def test_all_columns_use_portable_types(self):
        offenders = []
        for table in Base.metadata.tables.values():
            for column in table.columns:
                if not isinstance(column.type, self.PORTABLE_TYPES):
                    offenders.append(f"{table.name}.{column.name} ({type(column.type).__name__})")
        self.assertEqual(offenders, [], f"non-portable column types found: {offenders}")

    def test_tables_exist_for_every_expected_model(self):
        expected = {
            "issues", "issue_reports", "status_history", "points_of_interest",
            "users", "departments", "staff_users", "resolutions", "notifications",
        }
        self.assertTrue(expected.issubset(set(Base.metadata.tables.keys())))


if __name__ == "__main__":
    unittest.main(verbosity=2)
