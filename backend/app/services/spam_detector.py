"""
Supplemental authenticity signals.

The authoritative validity score/status now comes exclusively from
app/services/core/validator.calculate_validity(). This module no longer
computes a competing trust score — it only surfaces a small number of
extra signals that validator.py's six factors don't cover (exact image
reuse, abusive language), returned as plain flags for staff transparency.
They never influence validity_score/validity_status.
"""
import hashlib
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.models.issue import IssueReport

ABUSIVE_WORDS = {"idiot", "stupid", "nonsense", "fake", "useless", "damn"}

HIGH_FREQUENCY_WINDOW_HOURS = 1
HIGH_FREQUENCY_THRESHOLD = 5


def hash_image_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_supplemental_flags(
    db: Session,
    *,
    description: str,
    user_id: int | None,
    image_hash: str | None,
) -> List[str]:
    """Returns extra, non-scoring authenticity flags for staff visibility.
    These supplement — but never replace or weight into — validator.py's
    validity_score."""
    flags: List[str] = []

    desc = (description or "").strip().lower()
    if any(w in desc.split() for w in ABUSIVE_WORDS):
        flags.append("Description contains abusive or inappropriate language")

    if image_hash:
        reuse_query = db.query(IssueReport).filter(IssueReport.image_hash == image_hash)
        if user_id:
            reuse_count = reuse_query.filter(IssueReport.user_id == user_id).count()
        else:
            reuse_count = reuse_query.count()
        if reuse_count > 0:
            flags.append(f"This exact image was already used in {reuse_count} prior report(s)")

    if user_id:
        window_start = datetime.utcnow() - timedelta(hours=HIGH_FREQUENCY_WINDOW_HOURS)
        recent_count = (
            db.query(IssueReport)
            .filter(IssueReport.user_id == user_id)
            .filter(IssueReport.submitted_at >= window_start)
            .count()
        )
        if recent_count >= HIGH_FREQUENCY_THRESHOLD:
            flags.append(f"Unusually high submission frequency ({recent_count} reports in the last hour)")

    return flags
