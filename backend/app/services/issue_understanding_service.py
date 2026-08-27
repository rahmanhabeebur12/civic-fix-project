"""
issue_understanding_service.py

Single provider-independent "AI understands the report" layer.

Produces a structured description of a citizen report — category
(normalized into CivicFix's existing taxonomy), severity (1-5),
impact_level (1-5), location_type, confidence, and which evidence it was
derived from (source) — but it NEVER decides validity, duplicate status,
or the final priority score. Those remain the exclusive responsibility of
the canonical, unmodified app/services/core/ modules (validator.py,
duplicate.py, priority.py).

Two independent provider switches:

    AI_PROVIDER=mock | groq     (text understanding)
    VLM_PROVIDER=none | groq    (image understanding)

Both default to the side that needs no external credentials, so the
report pipeline never breaks because a provider is unavailable,
misconfigured, slow, or returns something malformed — any failure at any
stage falls back to the existing deterministic rule-based path. AI output
is never fabricated: a failed/unavailable call returns None and the
caller falls back honestly, it never invents a "successful" result.

Only the already-sanitized image (the path app.services.image_sanitizer
wrote to disk) is ever read here — the raw upload is held only in memory
by the sanitizer and is never persisted or passed to this service.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from typing import Literal, Optional

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy.orm import Session

from app.config import settings
from app.services import priority_engine
from app.services.location_service import LocationInfo, describe_location
from app.services.taxonomy import ISSUE_TYPES, classify_keywords

logger = logging.getLogger("civicfix.issue_understanding")

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"

VALID_LOCATION_TYPES = {
    "normal_area", "residential_area", "market", "busy_road",
    "public_transport", "school", "hospital", "critical_infrastructure",
}

SYSTEM_PROMPT = (
    "You are a civic-issue triage assistant for a municipal reporting app. "
    "Analyze the citizen's report and respond with STRICT JSON only, no "
    "markdown fences, no extra text, matching exactly this shape:\n"
    '{"category": "<short free-text civic issue category, e.g. pothole, '
    'garbage, streetlight, water leak, drainage, sewage>", '
    '"severity": <integer 1-5>, "impact_level": <integer 1-5>, '
    '"location_type": "<one of: normal_area, residential_area, market, '
    'busy_road, public_transport, school, hospital, critical_infrastructure>", '
    '"confidence": <float 0.0-1.0>, "reasoning": "<one short sentence>"}\n\n'
    "severity: 1=minor, 2=low, 3=moderate, 4=serious, 5=critical/public-safety-risk.\n"
    "impact_level: 1=minimal, 2=limited, 3=moderate, 4=major, 5=severe/public-wide.\n"
    "Base location_type only on what the text/image actually shows — do not "
    "guess GPS-only details you cannot see. Respond with the JSON object only."
)


# ============================================================================
# Structured, schema-validated AI/VLM output contract
# ============================================================================

class AIUnderstandingOutput(BaseModel):
    """The exact contract every provider response must satisfy. Anything
    that fails validation is treated as a provider failure — it triggers
    the deterministic fallback, never a silently-coerced guess."""

    category: str
    severity: int = Field(ge=1, le=5)
    impact_level: int = Field(ge=1, le=5)
    location_type: str = "normal_area"
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""

    @field_validator("category")
    @classmethod
    def _category_not_empty(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("category must be a non-empty string")
        return v.strip()

    @field_validator("location_type")
    @classmethod
    def _normalize_location_type(cls, v: str) -> str:
        # Soft-normalize rather than hard-reject: an unrecognized
        # location_type shouldn't discard an otherwise-valid severity/
        # impact/confidence assessment. This value is informational only
        # (see note in classify_report) — the deterministic GPS/POI lookup
        # remains authoritative for what actually feeds priority.py.
        if not isinstance(v, str) or v.strip() not in VALID_LOCATION_TYPES:
            return "normal_area"
        return v.strip()


# ============================================================================
# Public result shape (unchanged from the previous ai_classifier.py, so the
# rest of the pipeline — report_pipeline.py — needs no further changes)
# ============================================================================

@dataclass
class ClassificationResult:
    issue_type: str
    category: str
    confidence: float
    suggested_department: str
    safety_risk: str
    reasoning_summary: str
    severity: int  # 1-5, feeds priority.calculate_priority()
    severity_label: str  # LOW/MEDIUM/HIGH/CRITICAL, for display/SLA
    severity_reason: str
    impact_level: int  # 1-5, feeds priority.calculate_priority()
    location_type: str  # normalized value, feeds priority.calculate_priority()
    location_context: str  # human-readable display string
    source: Literal["TEXT", "IMAGE", "TEXT_AND_IMAGE", "FALLBACK"]


# ============================================================================
# Category normalization — reuses the existing keyword taxonomy matcher,
# never a second competing classifier.
# ============================================================================

def _normalize_category(ai_category: str, description: str) -> str:
    """Maps a free-text AI category guess onto one of CivicFix's existing
    issue_type keys, using the SAME deterministic keyword matcher already
    used for plain-text classification. Falls back to "Other" honestly
    when nothing matches — never invents a taxonomy entry."""
    combined_text = f"{ai_category or ''} {description or ''}".strip()
    return classify_keywords(combined_text) or "Other"


def _safety_risk_for(severity: int) -> str:
    if severity >= 5:
        return "High"
    if severity >= 4:
        return "Medium"
    return "Low"


# ============================================================================
# Groq (text + vision) provider — the only concrete provider implemented.
# Both AI_PROVIDER=groq and VLM_PROVIDER=groq talk to the same Groq chat
# completions endpoint, just with a text-only vs. a vision-capable model.
# Swapping in a different provider later means adding another _call_*
# function and one line in classify_report() — nothing else changes.
# ============================================================================

def _parse_ai_response(raw_content: str) -> Optional[AIUnderstandingOutput]:
    try:
        data = json.loads(raw_content)
        return AIUnderstandingOutput.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        logger.warning("issue understanding: malformed AI/VLM response, falling back (%s)", type(e).__name__)
        return None


def _call_groq_text(description: str) -> Optional[AIUnderstandingOutput]:
    if not settings.GROQ_API_KEY:
        return None
    try:
        with httpx.Client(timeout=settings.GROQ_TIMEOUT_SECONDS) as http_client:
            response = http_client.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json={
                    "model": settings.GROQ_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Citizen report description: {description}"},
                    ],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        logger.warning("issue understanding: Groq text call failed, falling back (%s)", type(e).__name__)
        return None
    return _parse_ai_response(content)


def _read_sanitized_image_bytes(image_path: str) -> Optional[bytes]:
    """Reads ONLY the already-sanitized file that image_sanitizer.py wrote
    under UPLOAD_DIR. There is no other image path in the system for a
    citizen report by this point — the raw upload was held in memory only
    and was never itself written to disk."""
    full_path = os.path.join(settings.UPLOAD_DIR, image_path)
    try:
        with open(full_path, "rb") as f:
            return f.read()
    except OSError as e:
        logger.warning("issue understanding: could not read sanitized image, falling back (%s)", e)
        return None


def _call_groq_vision(description: Optional[str], image_path: str) -> Optional[AIUnderstandingOutput]:
    if not settings.GROQ_API_KEY:
        return None

    image_bytes = _read_sanitized_image_bytes(image_path)
    if image_bytes is None:
        return None

    ext = os.path.splitext(image_path)[1].lstrip(".").lower() or "webp"
    mime = "image/jpeg" if ext == "jpg" else f"image/{ext}"
    data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"

    text_hint = (
        f"Citizen-provided description: {description}" if (description or "").strip()
        else "No text description was provided — assess the photo alone."
    )

    try:
        with httpx.Client(timeout=settings.GROQ_TIMEOUT_SECONDS) as http_client:
            response = http_client.post(
                GROQ_CHAT_URL,
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
                json={
                    "model": settings.GROQ_VLM_MODEL,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": text_hint},
                                {"type": "image_url", "image_url": {"url": data_url}},
                            ],
                        },
                    ],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
        logger.warning("issue understanding: Groq vision call failed, falling back (%s)", type(e).__name__)
        return None
    return _parse_ai_response(content)


# ============================================================================
# Deterministic fallback — identical to the previous mock classifier.
# Always used when no provider is configured, and automatically used
# whenever a configured provider fails or returns something invalid.
# ============================================================================

def _build_result_fallback(description: str, location: LocationInfo) -> ClassificationResult:
    matched = classify_keywords(description)

    if not matched:
        severity_result = priority_engine.infer_severity("Other", description, location.location_context)
        impact_level = priority_engine.infer_impact_level("Other", severity_result.severity)
        if not (description or "").strip():
            reasoning = "No description was provided and no image-understanding model is configured. Needs manual review."
        else:
            reasoning = "Could not confidently match the description to a known civic issue type. Needs manual review."
        return ClassificationResult(
            issue_type="Other",
            category="Other",
            confidence=0.3,
            suggested_department="General Civic Support",
            safety_risk="Low",
            reasoning_summary=reasoning,
            severity=severity_result.severity,
            severity_label=severity_result.label,
            severity_reason=severity_result.reason,
            impact_level=impact_level,
            location_type=location.location_type,
            location_context=location.location_context,
            source="FALLBACK",
        )

    cfg = ISSUE_TYPES[matched]
    confidence = 0.75

    severity_result = priority_engine.infer_severity(matched, description, location.location_context)
    impact_level = priority_engine.infer_impact_level(matched, severity_result.severity)

    return ClassificationResult(
        issue_type=matched,
        category=cfg["category"],
        confidence=confidence,
        suggested_department=cfg["department"],
        safety_risk=_safety_risk_for(severity_result.severity),
        reasoning_summary=f"Description matched keywords associated with '{matched}'.",
        severity=severity_result.severity,
        severity_label=severity_result.label,
        severity_reason=severity_result.reason,
        impact_level=impact_level,
        location_type=location.location_type,
        location_context=location.location_context,
        source="FALLBACK",
    )


def _build_result_from_ai(
    ai: AIUnderstandingOutput, description: str, location: LocationInfo, source: str,
) -> ClassificationResult:
    issue_type = _normalize_category(ai.category, description)
    cfg = ISSUE_TYPES.get(issue_type, ISSUE_TYPES["Other"])
    severity_label = priority_engine.LEVEL_TO_LABEL.get(ai.severity, "MEDIUM")

    evidence = source.replace("_", " ").lower()
    reason_bits = [f"AI-assessed severity {ai.severity}/5 from {evidence} evidence."]
    if ai.reasoning:
        reason_bits.append(ai.reasoning)

    return ClassificationResult(
        issue_type=issue_type,
        category=cfg["category"],
        confidence=ai.confidence,
        suggested_department=cfg["department"],
        safety_risk=_safety_risk_for(ai.severity),
        reasoning_summary=ai.reasoning or f"AI classified this report as related to '{issue_type}'.",
        severity=ai.severity,
        severity_label=severity_label,
        severity_reason=" ".join(reason_bits),
        impact_level=ai.impact_level,
        # location_type/location_context stay authoritative from the
        # deterministic GPS/POI lookup (describe_location) — an AI/VLM
        # guess must never be allowed to directly move priority.py's
        # location score. ai.location_type is validated (see
        # AIUnderstandingOutput) but intentionally unused here.
        location_type=location.location_type,
        location_context=location.location_context,
        source=source,
    )


# ============================================================================
# Public entry point
# ============================================================================

def classify_report(db: Session, description: str, image_path: str, latitude: float, longitude: float) -> ClassificationResult:
    has_text = bool((description or "").strip())
    has_image = bool((image_path or "").strip())

    # Deterministic, GPS/POI-based — computed once, always available as
    # the fallback location signal regardless of which path below runs.
    location = describe_location(db, latitude, longitude)

    ai_output: Optional[AIUnderstandingOutput] = None
    source: str = "FALLBACK"

    # Prefer a combined vision call when a photo exists and a VLM is
    # configured — it can incorporate the text too in the same call,
    # which is both more accurate and cheaper than two separate calls.
    if has_image and settings.VLM_PROVIDER == "groq":
        ai_output = _call_groq_vision(description if has_text else None, image_path)
        if ai_output is not None:
            source = "TEXT_AND_IMAGE" if has_text else "IMAGE"

    # No VLM configured/available, or no image at all: fall back to
    # text-only Groq when there's text to analyze.
    if ai_output is None and has_text and settings.AI_PROVIDER == "groq":
        ai_output = _call_groq_text(description)
        if ai_output is not None:
            source = "TEXT"

    if ai_output is not None:
        return _build_result_from_ai(ai_output, description, location, source)

    # No provider configured, or every configured provider failed/returned
    # something invalid — the deterministic rule-based path never fails.
    return _build_result_fallback(description, location)
