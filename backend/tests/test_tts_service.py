"""
tests/test_tts_service.py

Tests for app.services.tts_service (backend-only ElevenLabs proxy) and
the POST /accessibility/tts route. Mocks httpx.Client.post — no network
access, no real ElevenLabs credentials needed.

Run with:
    cd backend && venv/bin/python -m unittest tests.test_tts_service -v
"""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_TEST_DIR = tempfile.mkdtemp(prefix="civicfix-test-tts-")
os.environ["UPLOAD_DIR"] = os.path.join(_TEST_DIR, "uploads")
os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(_TEST_DIR, 'test.db')}"

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services import tts_service  # noqa: E402

client = TestClient(app)


class FakeResponse:
    def __init__(self, content=b"", status_code=200, raise_exc=None):
        self.content = content
        self.status_code = status_code
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise self._raise_exc
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


class TTSServiceTests(unittest.TestCase):
    def setUp(self):
        # Clear the module-level cache between tests so they don't leak
        # into each other via cache hits.
        tts_service._audio_cache.clear()
        tts_service._key_locks.clear()
        self._provider_patch = patch.object(settings, "TTS_PROVIDER", "elevenlabs")
        self._key_patch = patch.object(settings, "ELEVENLABS_API_KEY", "sk_test_super_secret_key")
        self._voice_patch = patch.object(settings, "ELEVENLABS_VOICE_ID", "voice123")
        self._provider_patch.start()
        self._key_patch.start()
        self._voice_patch.start()

    def tearDown(self):
        self._provider_patch.stop()
        self._key_patch.stop()
        self._voice_patch.stop()

    # -- not configured -------------------------------------------------------

    def test_not_configured_returns_unavailable_without_any_call(self):
        with patch.object(settings, "TTS_PROVIDER", "browser"):
            with patch("httpx.Client.post") as mock_post:
                result = tts_service.synthesize_speech("Hello citizen")
        self.assertFalse(result.available)
        self.assertIsNone(result.audio_bytes)
        mock_post.assert_not_called()

    # -- 3. ElevenLabs configured + mocked success -----------------------------

    def test_configured_success_returns_audio(self):
        with patch("httpx.Client.post", return_value=FakeResponse(content=b"\xff\xfbFAKE_MP3_BYTES")):
            result = tts_service.synthesize_speech("Take a photo of the civic issue")
        self.assertTrue(result.available)
        self.assertEqual(result.audio_bytes, b"\xff\xfbFAKE_MP3_BYTES")
        self.assertEqual(result.content_type, "audio/mpeg")

    # -- 4. timeout -> unavailable (frontend falls back to browser) -----------

    def test_timeout_falls_back(self):
        with patch("httpx.Client.post", side_effect=httpx.TimeoutException("timed out")):
            result = tts_service.synthesize_speech("Please review your report")
        self.assertFalse(result.available)
        self.assertIsNone(result.audio_bytes)

    # -- 5. malformed/error response -> unavailable ----------------------------

    def test_http_error_response_falls_back(self):
        with patch("httpx.Client.post", return_value=FakeResponse(status_code=500)):
            result = tts_service.synthesize_speech("Your report has been submitted")
        self.assertFalse(result.available)

    def test_empty_audio_response_falls_back(self):
        with patch("httpx.Client.post", return_value=FakeResponse(content=b"")):
            result = tts_service.synthesize_speech("Choose your preferred language")
        self.assertFalse(result.available)

    # -- caching / rate control -------------------------------------------------

    def test_repeated_identical_text_uses_cache_not_a_second_call(self):
        with patch("httpx.Client.post", return_value=FakeResponse(content=b"AUDIO")) as mock_post:
            first = tts_service.synthesize_speech("Your location has been captured.")
            second = tts_service.synthesize_speech("Your location has been captured.")
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(first.audio_bytes, second.audio_bytes)

    # -- 6. API key never leaks -------------------------------------------------

    def test_api_key_never_appears_in_error_path(self):
        with patch("httpx.Client.post", side_effect=httpx.ConnectError("refused")):
            result = tts_service.synthesize_speech("Speak your complaint")
        self.assertFalse(result.available)
        # Nothing about the result object should ever be able to leak the
        # key — there is no field carrying request headers/credentials.
        self.assertNotIn("sk_test_super_secret_key", repr(result))

    def test_endpoint_503_does_not_leak_api_key(self):
        # Patch synthesize_speech itself here, not httpx.Client.post — the
        # TestClient's own internal request transport also uses
        # httpx.Client, so a global httpx-level patch would intercept the
        # test client's own request too, not just the app's outbound call.
        with patch("app.routers.accessibility.synthesize_speech", return_value=tts_service.TTSResult(audio_bytes=None, content_type="", available=False)):
            resp = client.post("/accessibility/tts", json={"text": "Hello"})
        self.assertEqual(resp.status_code, 503)
        self.assertNotIn("sk_test_super_secret_key", resp.text)

    def test_endpoint_returns_audio_bytes_on_success(self):
        with patch("app.routers.accessibility.synthesize_speech", return_value=tts_service.TTSResult(audio_bytes=b"REAL_AUDIO_BYTES", content_type="audio/mpeg", available=True)):
            resp = client.post("/accessibility/tts", json={"text": "Hear this instruction"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content, b"REAL_AUDIO_BYTES")
        self.assertEqual(resp.headers["content-type"], "audio/mpeg")

    def test_endpoint_rejects_empty_text(self):
        resp = client.post("/accessibility/tts", json={"text": ""})
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main(verbosity=2)
