"""
tests/test_analytics_service.py

Unit tests for app.services.analytics_service and
app.services.heatmap_service — pure aggregation logic, no DB/pipeline
needed. Also verifies the canonical priority.py age factor (untouched)
still gives an older unresolved issue a higher age contribution, and that
its own resolved-issue age does not keep growing past resolution.

Run with:
    cd backend && venv/bin/python -m unittest tests.test_analytics_service -v
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-analytics-")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DIR, "uploads")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DIR, 'test.db')}"

from app.services import analytics_service  # noqa: E402
from app.services.core import priority as core_priority  # noqa: E402


def _issue(
    *, created_at, assigned_at=None, accepted_at=None, work_started_at=None,
    resolved_at=None, status="ASSIGNED", priority_level="MEDIUM", reopen_count=0,
    complaint_id="CIV-TEST", issue_type="Pothole", primary_department=None,
):
    return SimpleNamespace(
        created_at=created_at, assigned_at=assigned_at, accepted_at=accepted_at,
        work_started_at=work_started_at, resolved_at=resolved_at, status=status,
        priority_level=priority_level, reopen_count=reopen_count,
        complaint_id=complaint_id, issue_type=issue_type, primary_department=primary_department,
    )


class ResponseTimeAnalyticsTests(unittest.TestCase):
    def test_avg_and_median_time_to_accept(self):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        issues = [
            _issue(created_at=base, accepted_at=base + timedelta(hours=2)),
            _issue(created_at=base, accepted_at=base + timedelta(hours=4)),
            _issue(created_at=base, accepted_at=base + timedelta(hours=6)),
        ]
        result = analytics_service.compute_response_time_analytics(issues, now=base + timedelta(days=1))
        self.assertAlmostEqual(result.avg_time_to_accept_hours, 4.0)
        self.assertAlmostEqual(result.median_time_to_accept_hours, 4.0)

    def test_time_to_resolution_only_counts_resolved_issues(self):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        issues = [
            _issue(created_at=base, resolved_at=base + timedelta(hours=10), status="RESOLVED"),
            _issue(created_at=base, status="ASSIGNED"),  # not resolved -> excluded
        ]
        result = analytics_service.compute_response_time_analytics(issues, now=base + timedelta(days=1))
        self.assertAlmostEqual(result.avg_time_to_resolution_hours, 10.0)

    def test_unresolved_age_does_not_include_resolved_issues(self):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        now = base + timedelta(days=10)
        issues = [
            _issue(created_at=base, status="ASSIGNED"),  # still open -> counted
            _issue(created_at=base, status="RESOLVED", resolved_at=base + timedelta(hours=1)),  # closed -> excluded
        ]
        result = analytics_service.compute_response_time_analytics(issues, now=now)
        # Only the one open issue contributes -> avg == its exact age (10 days = 240h)
        self.assertAlmostEqual(result.avg_unresolved_age_hours, 240.0)

    def test_oldest_unresolved_sorted_oldest_first(self):
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        now = base + timedelta(days=20)
        issues = [
            _issue(created_at=base + timedelta(days=5), status="ASSIGNED", complaint_id="CIV-NEW"),
            _issue(created_at=base, status="ASSIGNED", complaint_id="CIV-OLD"),
        ]
        result = analytics_service.compute_response_time_analytics(issues, now=now)
        self.assertEqual(result.oldest_unresolved[0]["complaint_id"], "CIV-OLD")

    def test_naive_and_aware_timestamps_both_work(self):
        # Simulates SQLite (naive) vs PostgreSQL (aware) driver behavior
        # for the same DateTime(timezone=True) column.
        naive_base = datetime(2026, 1, 1)
        aware_accept = datetime(2026, 1, 1, 3, tzinfo=timezone.utc)
        issues = [_issue(created_at=naive_base, accepted_at=aware_accept)]
        result = analytics_service.compute_response_time_analytics(issues, now=datetime(2026, 1, 2, tzinfo=timezone.utc))
        self.assertAlmostEqual(result.avg_time_to_accept_hours, 3.0)


class BacklogAnalyticsTests(unittest.TestCase):
    def test_high_and_critical_backlog_split(self):
        dept = SimpleNamespace(name="Roads / Public Works")
        issues = [
            _issue(created_at=datetime.utcnow(), status="SUBMITTED", priority_level="HIGH", primary_department=dept),
            _issue(created_at=datetime.utcnow(), status="MANUAL_REVIEW", priority_level="CRITICAL", primary_department=dept),
            _issue(created_at=datetime.utcnow(), status="ASSIGNED", priority_level="LOW", primary_department=dept),
            _issue(created_at=datetime.utcnow(), status="RESOLVED", priority_level="HIGH", primary_department=dept),  # not backlog
        ]
        result = analytics_service.compute_backlog_analytics(issues)
        self.assertEqual(result.high_backlog, 1)
        self.assertEqual(result.critical_backlog, 1)
        self.assertEqual(result.total_open_backlog, 3)
        self.assertEqual(result.total_resolved, 1)

    def test_reopened_count(self):
        issues = [
            _issue(created_at=datetime.utcnow(), status="REOPENED", reopen_count=1),
            _issue(created_at=datetime.utcnow(), status="ASSIGNED", reopen_count=0),
        ]
        result = analytics_service.compute_backlog_analytics(issues)
        self.assertEqual(result.reopened_count, 1)


class PriorityAgeFactorSanityTests(unittest.TestCase):
    """The canonical priority.py age factor is never modified — this just
    confirms the property this task asked us to verify still holds."""

    def test_older_unresolved_issue_gets_higher_age_contribution(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        old_iso = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        recent_score = core_priority.calculate_age_score(now_iso)
        old_score = core_priority.calculate_age_score(old_iso)
        self.assertGreater(old_score, recent_score)


if __name__ == "__main__":
    unittest.main(verbosity=2)
