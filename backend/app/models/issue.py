from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Issue(Base):
    """One real-world civic problem. May have many IssueReports."""

    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(String(30), unique=True, index=True, nullable=False)

    issue_type = Column(String(80), nullable=False)
    category = Column(String(80), nullable=False, index=True)

    is_demo = Column(Boolean, default=False, nullable=False, index=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(255), default="")

    # --- Severity / impact (feeds app.services.core.priority) --------------
    severity = Column(String(20), default="MEDIUM")  # LOW/MEDIUM/HIGH/CRITICAL display label
    severity_level = Column(Integer, default=3)  # 1-5, the actual priority.py input
    severity_reason = Column(Text, default="")
    impact_level = Column(Integer, default=3)  # 1-5, priority.py input

    location_type = Column(String(40), default="normal_area")  # priority.py input
    location_context = Column(String(255), default="")  # human-readable display string

    # --- Priority (app.services.core.priority is authoritative) ------------
    priority_score = Column(Integer, default=0)
    priority_level = Column(String(20), default="LOW")
    priority_breakdown = Column(Text, default="{}")  # JSON: severity/reporters/location/age/impact
    priority_reasons = Column(Text, default="[]")  # JSON list of human-readable reasons

    primary_department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    supporting_department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)

    ai_confidence = Column(Float, default=0.0)
    ai_reasoning = Column(Text, default="")

    status = Column(String(40), default="SUBMITTED", index=True)

    # --- Validity (app.services.core.validator is authoritative) -----------
    validity_status = Column(String(20), default="VALID", index=True)  # VALID | REVIEW | SUSPICIOUS

    # --- Duplicate analysis (app.services.core.duplicate is authoritative) -
    # Recorded from the founding report's duplicate check — i.e. whether
    # *this* Issue was created fresh, and against what it was compared.
    duplicate_score = Column(Float, default=0.0)
    duplicate_confidence = Column(String(20), default="NONE")  # HIGH | POSSIBLE | NONE
    duplicate_action = Column(String(20), default="CREATE_NEW")  # CREATE_NEW | REVIEW | LINK_TO_EXISTING
    duplicate_breakdown = Column(Text, default="{}")  # JSON: location/category/description/photo
    duplicate_distance_meters = Column(Float, nullable=True)

    reporter_count = Column(Integer, default=1)

    image_path = Column(String(255), default="")  # first citizen photo

    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by = Column(String(120), nullable=True)
    work_started_at = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    reopen_count = Column(Integer, default=0)

    primary_department = relationship("Department", foreign_keys=[primary_department_id])
    supporting_department = relationship("Department", foreign_keys=[supporting_department_id])
    reports = relationship("IssueReport", back_populates="issue", order_by="IssueReport.submitted_at")
    status_history = relationship("StatusHistory", back_populates="issue", order_by="StatusHistory.timestamp")
    resolutions = relationship("Resolution", back_populates="issue", order_by="Resolution.created_at")


class IssueReport(Base):
    """One citizen's report of a civic problem."""

    __tablename__ = "issue_reports"

    id = Column(Integer, primary_key=True, index=True)
    client_report_id = Column(String(64), unique=True, index=True, nullable=False)

    is_demo = Column(Boolean, default=False, nullable=False, index=True)

    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Weak anti-abuse signal ONLY (app.services.rate_limiter) — a truncated
    # hash, never the raw IP. Many genuine citizens share one IP (hostel/
    # apartment/office/public WiFi, carrier NAT), so this is never read by
    # validator.py, duplicate.py, or priority.py, and is never shown as a
    # raw address in the staff UI. See app/services/rate_limiter.py.
    client_ip_hash = Column(String(64), nullable=True, index=True)

    original_description = Column(Text, default="")
    normalized_description = Column(Text, default="")

    image_path = Column(String(255), default="")
    image_hash = Column(String(64), nullable=True, index=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    gps_accuracy = Column(Float, nullable=True)

    language = Column(String(10), default="en")

    # --- Accessibility (app.services.validation_adapter) --------------------
    # PHOTO_AND_TEXT | PHOTO_ONLY | TEXT_ONLY
    submission_mode = Column(String(20), default="PHOTO_AND_TEXT", nullable=False)
    accessibility_adjustment = Column(Boolean, default=False, nullable=False)

    # Analytics only — TYPED | VOICE. Whether the description text was
    # originally produced via speech-to-text. This never affects
    # submission_mode, validation, duplicate detection, or priority: a
    # voice-derived description is evidence-equivalent to a typed one, and
    # the AI/VLM understanding layer never sees or cares about this field.
    description_source = Column(String(20), default="TYPED", nullable=False)

    # --- Validity (app.services.core.validator.calculate_validity output) --
    validity_score = Column(Float, default=100.0)
    validity_status = Column(String(20), default="VALID")  # VALID | REVIEW | SUSPICIOUS
    validity_breakdown = Column(Text, default="{}")  # JSON: the six-factor breakdown
    validation_errors = Column(Text, default="[]")  # JSON list
    supplemental_flags = Column(Text, default="[]")  # JSON list — extra signals, non-scoring
    review_decision = Column(String(20), nullable=True)  # APPROVED | REJECTED

    is_duplicate = Column(Boolean, default=False)

    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    was_offline = Column(Boolean, default=False)
    synced_at = Column(DateTime(timezone=True), nullable=True)

    issue = relationship("Issue", back_populates="reports")
    user = relationship("User")


class StatusHistory(Base):
    __tablename__ = "status_history"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id"), nullable=False)
    status = Column(String(40), nullable=False)
    changed_by = Column(String(120), default="system")
    note = Column(Text, default="")
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    issue = relationship("Issue", back_populates="status_history")


class PointOfInterest(Base):
    __tablename__ = "points_of_interest"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    poi_type = Column(String(40), nullable=False)  # school | hospital | bus_stop | market | ...
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
