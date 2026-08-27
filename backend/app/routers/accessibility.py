from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field

from app.services.tts_service import synthesize_speech

router = APIRouter(prefix="/accessibility", tags=["accessibility"])

MAX_TTS_TEXT_LENGTH = 500


class TTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TTS_TEXT_LENGTH)


@router.post("/tts")
def text_to_speech(payload: TTSRequest):
    """Backend-only ElevenLabs proxy. The frontend never holds an
    ElevenLabs API key. A 503 here is not an error the citizen needs to
    see — it just means the frontend should fall back to
    window.speechSynthesis, which it always does automatically."""
    result = synthesize_speech(payload.text)
    if not result.available or not result.audio_bytes:
        raise HTTPException(status_code=503, detail="Voice guidance audio is unavailable right now.")
    return Response(content=result.audio_bytes, media_type=result.content_type)
