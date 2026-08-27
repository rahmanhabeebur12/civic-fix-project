"""
rate_limiter.py

Anti-spam rate limiting for POST /citizen/reports and the "add support"
endpoint. Reuses IssueReport.submitted_at directly — no new table, no
external cache — a sliding window is just "how many reports has this
identity submitted in the last N seconds".

Identity: every citizen report in this app already carries a mobile
number, which resolves to a persistent app.models.user.User row — the
closest thing this app has to an "account". That user_id is therefore the
primary rate-limit key (RATE_LIMIT_AUTH_COUNT), not a raw IP. A hashed
client IP (see hash_client_ip below) is recorded for weak anti-abuse
visibility, but is deliberately NOT used as a sole blocking signal: many
genuine citizens share one IP (hostel/apartment/office/public WiFi,
carrier NAT), so blocking by IP alone would punish innocent users on a
shared network. RATE_LIMIT_ANON_COUNT exists for a defensive fallback
path only (see check_rate_limit) and is intentionally never the primary
enforcement mechanism in this app.

Offline reports are exempt: they are idempotent (deduplicated by
client_report_id in report_pipeline.py) and were, by definition, created
earlier and only delayed in transmission — a batch of them arriving at
once on reconnect is not the same thing as rapid-fire live spam.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.models.issue import IssueReport

RATE_LIMIT_MESSAGE = "Too many reports were submitted in a short time. Please try again shortly."

# How the raw request IP is hashed before it is ever persisted — see
# IssueReport.client_ip_hash. A short prefix keeps it useless for reversal
# while still letting equal IPs collide (which is all the weak signal
# actually needs).
_IP_HASH_LENGTH = 32


def hash_client_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:_IP_HASH_LENGTH]


def check_rate_limit(
    db: Session,
    *,
    user_id: int | None,
    client_ip_hash: str | None,
    was_offline: bool,
) -> None:
    """Raises HTTPException(429) if this identity has submitted too many
    reports in the configured window. No-op for offline-originated reports
    (see module docstring) and when no identity is resolvable at all."""
    if was_offline:
        return

    window_start = datetime.utcnow() - timedelta(seconds=settings.RATE_LIMIT_WINDOW_SECONDS)

    if user_id is not None:
        recent_count = (
            db.query(IssueReport)
            .filter(IssueReport.user_id == user_id)
            .filter(IssueReport.submitted_at >= window_start)
            .count()
        )
        if recent_count >= settings.RATE_LIMIT_AUTH_COUNT:
            raise HTTPException(status_code=429, detail=RATE_LIMIT_MESSAGE)
        return

    # Defensive fallback only — every real submission in this app resolves
    # a user_id via mobile, so this path is not expected to run in
    # practice. It exists so RATE_LIMIT_ANON_COUNT has an effect if that
    # ever changes, without becoming the primary (IP-only) gate.
    if client_ip_hash is not None:
        recent_count = (
            db.query(IssueReport)
            .filter(IssueReport.client_ip_hash == client_ip_hash)
            .filter(IssueReport.user_id.is_(None))
            .filter(IssueReport.submitted_at >= window_start)
            .count()
        )
        if recent_count >= settings.RATE_LIMIT_ANON_COUNT:
            raise HTTPException(status_code=429, detail=RATE_LIMIT_MESSAGE)
