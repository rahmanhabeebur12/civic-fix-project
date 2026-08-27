"""
tests/test_duplicate_candidate_filtering.py

Verifies the DB-level candidate pre-filtering in
app.services.duplicate_detector.load_candidate_issues (time window +
geographic bounding box) narrows the candidate set BEFORE the canonical
app.services.core.duplicate engine ever runs — without touching that
engine's scoring formula or thresholds at all.

Run with:
    cd backend && venv/bin/python -m unittest tests.test_duplicate_candidate_filtering -v
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-dupfilter-")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DIR, "uploads")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DIR, 'test.db')}"

from app.config import settings  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402  (ensures tables are created)
from app.models.issue import Issue  # noqa: E402
from app.services.duplicate_detector import load_candidate_issues  # noqa: E402


def _make_issue(db, **overrides):
    defaults = dict(
        complaint_id=f"CIV-DUPFILTER-{overrides.get('complaint_id', 'X')}",
        issue_type="Pothole", category="Roads", is_demo=False,
        latitude=13.0827, longitude=80.2707, status="ASSIGNED",
        severity_level=3, impact_level=3, location_type="normal_area",
        priority_score=50, priority_level="MEDIUM",
    )
    defaults.update(overrides)
    issue = Issue(**defaults)
    db.add(issue)
    db.commit()
    return issue


class DuplicateCandidateFilteringTests(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_old_issue_excluded_by_lookback_window(self):
        old = _make_issue(
            self.db, complaint_id="OLD",
            created_at=datetime.utcnow() - timedelta(days=settings.DUPLICATE_CANDIDATE_LOOKBACK_DAYS + 10),
        )
        candidates = load_candidate_issues(self.db, category="Roads", latitude=13.0827, longitude=80.2707)
        self.assertNotIn(old.id, [c["id"] for c in candidates])

    def test_recent_issue_included(self):
        recent = _make_issue(self.db, complaint_id="RECENT")
        candidates = load_candidate_issues(self.db, category="Roads", latitude=13.0827, longitude=80.2707)
        self.assertIn(recent.id, [c["id"] for c in candidates])

    def test_far_away_issue_excluded_by_bounding_box(self):
        far = _make_issue(self.db, complaint_id="FAR", latitude=40.0, longitude=-74.0)  # New York
        candidates = load_candidate_issues(self.db, category="Roads", latitude=13.0827, longitude=80.2707)
        self.assertNotIn(far.id, [c["id"] for c in candidates])

    def test_nearby_issue_included_within_bounding_box(self):
        nearby = _make_issue(self.db, complaint_id="NEARBY", latitude=13.0830, longitude=80.2710)
        candidates = load_candidate_issues(self.db, category="Roads", latitude=13.0827, longitude=80.2707)
        self.assertIn(nearby.id, [c["id"] for c in candidates])

    def test_no_coordinates_skips_geographic_filter_but_keeps_time_filter(self):
        recent = _make_issue(self.db, complaint_id="NOCOORD")
        candidates = load_candidate_issues(self.db, category="Roads")
        self.assertIn(recent.id, [c["id"] for c in candidates])

    def test_configurable_via_settings(self):
        far_ish = _make_issue(self.db, complaint_id="CONFIGTEST", latitude=13.20, longitude=80.40)
        with patch.object(settings, "DUPLICATE_CANDIDATE_MAX_DISTANCE_METERS", 100.0):
            candidates_tight = load_candidate_issues(self.db, category="Roads", latitude=13.0827, longitude=80.2707)
        with patch.object(settings, "DUPLICATE_CANDIDATE_MAX_DISTANCE_METERS", 50_000.0):
            candidates_wide = load_candidate_issues(self.db, category="Roads", latitude=13.0827, longitude=80.2707)
        self.assertNotIn(far_ish.id, [c["id"] for c in candidates_tight])
        self.assertIn(far_ish.id, [c["id"] for c in candidates_wide])


if __name__ == "__main__":
    unittest.main(verbosity=2)
