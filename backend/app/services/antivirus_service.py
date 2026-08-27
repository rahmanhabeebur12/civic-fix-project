"""
antivirus_service.py

Optional antivirus scanning extension point for uploaded file bytes.

ANTIVIRUS_ENABLED=false (the default) keeps the hackathon/local build
fully functional with zero AV dependencies installed — image_sanitizer
simply skips this step entirely. When ANTIVIRUS_ENABLED=true, bytes are
scanned via a local ClamAV daemon (through the optional `clamd` package)
before they are ever decoded as an image.

This module never fabricates a "clean" result. If scanning was requested
but the scanner package isn't installed, or the daemon can't be reached,
that counts as a scan failure — not a pass.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger("civicfix.antivirus")


@dataclass
class ScanResult:
    clean: bool
    reason: str


def scan_bytes(data: bytes) -> ScanResult:
    if not settings.ANTIVIRUS_ENABLED:
        return ScanResult(clean=True, reason="antivirus disabled")

    try:
        import clamd
    except ImportError:
        logger.warning(
            "antivirus scan failure: ANTIVIRUS_ENABLED=true but the optional "
            "'clamd' package is not installed"
        )
        return ScanResult(clean=False, reason="scanner unavailable")

    try:
        client = clamd.ClamdUnixSocket()
        result = client.instream(io.BytesIO(data))
        status = result.get("stream", (None, None))[0]
    except Exception as e:
        logger.warning("antivirus scan failure: %s", type(e).__name__)
        return ScanResult(clean=False, reason="scanner error")

    if status == "OK":
        return ScanResult(clean=True, reason="clean")

    logger.warning("antivirus scan failure: threat detected")
    return ScanResult(clean=False, reason="threat detected")


def log_antivirus_status() -> None:
    if settings.ANTIVIRUS_ENABLED:
        logger.info("antivirus scanning: ENABLED (expects a local ClamAV daemon via 'clamd')")
    else:
        logger.info("antivirus scanning: disabled (ANTIVIRUS_ENABLED=false) — extension point only")
