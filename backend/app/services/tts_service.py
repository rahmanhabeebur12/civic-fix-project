"""
tts_service.py

Backend-only ElevenLabs text-to-speech proxy for voice guidance.

ELEVENLABS_API_KEY lives only in the backend process environment — it is
never sent to, logged by, or readable from the frontend. The frontend
calls POST /accessibility/tts with plain text and gets audio bytes back
(or a clear "unavailable" response it falls back from); it never talks to
ElevenLabs directly.

TTS_PROVIDER=browser (the default) means this service is never called at
all — the frontend uses window.speechSynthesis instead, which needs no
backend and works fully offline where supported.

Cost/rate control: a small in-process cache keyed by (voice, model, text)
avoids re-requesting audio for a sentence already generated this process
lifetime, and a per-key lock collapses duplicate concurrent requests for
the same sentence into a single upstream call. This is a lightweight,
session-scale cache — not persisted, not a correctness guarantee.
"""
from __future__ import annotations

import hashlib
import logging
import threading
from dataclasses import dataclass

import httpx

from app.config import settings

logger = logging.getLogger("civicfix.tts")

ELEVENLABS_TTS_URL_TEMPLATE = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
MAX_CACHE_ENTRIES = 200

_cache_lock = threading.Lock()
_audio_cache: dict[str, bytes] = {}
_key_locks: dict[str, threading.Lock] = {}


@dataclass
class TTSResult:
    audio_bytes: bytes | None
    content_type: str
    available: bool  # False => caller (the API route) should signal "fall back to browser TTS"


def is_configured() -> bool:
    return bool(settings.TTS_PROVIDER == "elevenlabs" and settings.ELEVENLABS_API_KEY and settings.ELEVENLABS_VOICE_ID)


def _cache_key(text: str) -> str:
    raw = f"{settings.ELEVENLABS_VOICE_ID}|{settings.ELEVENLABS_MODEL_ID}|{text.strip()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _get_key_lock(key: str) -> threading.Lock:
    with _cache_lock:
        lock = _key_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _key_locks[key] = lock
        return lock


def _store_in_cache(key: str, audio_bytes: bytes) -> None:
    with _cache_lock:
        if len(_audio_cache) >= MAX_CACHE_ENTRIES:
            _audio_cache.clear()  # simplest safe bound for a session-scale cache
        _audio_cache[key] = audio_bytes


def synthesize_speech(text: str) -> TTSResult:
    text = (text or "").strip()
    if not text:
        return TTSResult(audio_bytes=None, content_type="", available=False)

    if not is_configured():
        return TTSResult(audio_bytes=None, content_type="", available=False)

    key = _cache_key(text)

    with _cache_lock:
        cached = _audio_cache.get(key)
    if cached is not None:
        return TTSResult(audio_bytes=cached, content_type="audio/mpeg", available=True)

    # Collapse duplicate concurrent requests for the identical sentence
    # (e.g. two tabs, or a double-tap) into a single upstream call.
    with _get_key_lock(key):
        with _cache_lock:
            cached = _audio_cache.get(key)
        if cached is not None:
            return TTSResult(audio_bytes=cached, content_type="audio/mpeg", available=True)

        try:
            with httpx.Client(timeout=settings.ELEVENLABS_TIMEOUT_SECONDS) as http_client:
                response = http_client.post(
                    ELEVENLABS_TTS_URL_TEMPLATE.format(voice_id=settings.ELEVENLABS_VOICE_ID),
                    headers={
                        "xi-api-key": settings.ELEVENLABS_API_KEY,
                        "Accept": "audio/mpeg",
                        "Content-Type": "application/json",
                    },
                    json={"text": text, "model_id": settings.ELEVENLABS_MODEL_ID},
                )
                response.raise_for_status()
                audio_bytes = response.content
        except httpx.HTTPError as e:
            # Never log the API key, the request body, or the response
            # body — only the failure category, for operational visibility.
            logger.warning("tts: ElevenLabs request failed, caller will fall back to browser TTS (%s)", type(e).__name__)
            return TTSResult(audio_bytes=None, content_type="", available=False)

        if not audio_bytes:
            logger.warning("tts: ElevenLabs returned an empty response, falling back")
            return TTSResult(audio_bytes=None, content_type="", available=False)

        _store_in_cache(key, audio_bytes)

    return TTSResult(audio_bytes=audio_bytes, content_type="audio/mpeg", available=True)
