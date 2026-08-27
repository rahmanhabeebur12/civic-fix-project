import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'civicfix.db'}")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "civicfix-dev-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

    # --- Issue understanding (app.services.issue_understanding_service) ----
    # Two independent switches: AI_PROVIDER for text, VLM_PROVIDER for
    # images. Both default to the side that needs no external credentials,
    # so the report pipeline never breaks because a provider is
    # unavailable, misconfigured, slow, or returns something malformed.
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "mock")  # mock | groq
    VLM_PROVIDER: str = os.getenv("VLM_PROVIDER", "none")  # none | groq
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")  # backend-only, never sent to the frontend
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    GROQ_VLM_MODEL: str = os.getenv("GROQ_VLM_MODEL", "llama-3.2-11b-vision-preview")
    GROQ_TIMEOUT_SECONDS: float = float(os.getenv("GROQ_TIMEOUT_SECONDS", "8"))

    # --- Voice accessibility: text-to-speech (app.services.tts_service) ----
    # TTS_PROVIDER=browser (default) means no backend TTS call is even
    # attempted — the frontend uses window.speechSynthesis directly, which
    # works fully offline when the browser supports it. ELEVENLABS_API_KEY
    # is backend-only and is never sent to, or readable by, the frontend.
    TTS_PROVIDER: str = os.getenv("TTS_PROVIDER", "browser")  # browser | elevenlabs
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "")
    ELEVENLABS_MODEL_ID: str = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
    ELEVENLABS_TIMEOUT_SECONDS: float = float(os.getenv("ELEVENLABS_TIMEOUT_SECONDS", "8"))

    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))

    # --- Image upload security (app.services.image_sanitizer) --------------
    # Every uploaded image — citizen report photos and staff resolution
    # photos alike — is decoded, stripped of metadata, resized, and
    # re-encoded before anything else in the app ever sees it. See
    # app/services/image_sanitizer.py for the full pipeline.
    MAX_IMAGE_UPLOAD_MB: int = int(os.getenv("MAX_IMAGE_UPLOAD_MB", "10"))
    MAX_IMAGE_WIDTH: int = int(os.getenv("MAX_IMAGE_WIDTH", "6000"))
    MAX_IMAGE_HEIGHT: int = int(os.getenv("MAX_IMAGE_HEIGHT", "6000"))
    MAX_IMAGE_PIXELS: int = int(os.getenv("MAX_IMAGE_PIXELS", "25000000"))
    MAX_STORED_WIDTH: int = int(os.getenv("MAX_STORED_WIDTH", "1920"))
    MAX_STORED_HEIGHT: int = int(os.getenv("MAX_STORED_HEIGHT", "1920"))
    SANITIZED_IMAGE_FORMAT: str = os.getenv("SANITIZED_IMAGE_FORMAT", "webp")
    SANITIZED_IMAGE_QUALITY: int = int(os.getenv("SANITIZED_IMAGE_QUALITY", "85"))
    ANTIVIRUS_ENABLED: bool = os.getenv("ANTIVIRUS_ENABLED", "false").strip().lower() == "true"

    CORS_ORIGINS: list = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173",
    ).split(",")

    CITY_NAME: str = os.getenv("CITY_NAME", "Chennai")
    CITY_CENTER_LAT: float = float(os.getenv("CITY_CENTER_LAT", "13.0827"))
    CITY_CENTER_LNG: float = float(os.getenv("CITY_CENTER_LNG", "80.2707"))

    # SLA hours per severity
    SLA_HOURS = {"CRITICAL": 4, "HIGH": 12, "MEDIUM": 48, "LOW": 72}

    DUPLICATE_DISTANCE_METERS: float = 50.0
    REOPEN_PRIORITY_BOOST: int = 15

    # --- Duplicate candidate pre-filtering (app.services.duplicate_detector) -
    # These narrow the candidate set with cheap DB-level filters BEFORE
    # calling the canonical app.services.core.duplicate engine — they never
    # change its scoring/thresholds, only which rows are even compared.
    DUPLICATE_CANDIDATE_LOOKBACK_DAYS: int = int(os.getenv("DUPLICATE_CANDIDATE_LOOKBACK_DAYS", "60"))
    DUPLICATE_CANDIDATE_MAX_DISTANCE_METERS: float = float(os.getenv("DUPLICATE_CANDIDATE_MAX_DISTANCE_METERS", "500"))

    # --- Rate limiting / anti-spam (app.services.rate_limiter) -------------
    # Applied to POST /citizen/reports and the "add support" endpoint.
    # Keyed by the citizen's mobile-derived user_id (the closest thing this
    # app has to an "account"); a hashed client IP is stored for weak
    # anti-abuse visibility only — see app.services.rate_limiter for why it
    # is never used as a sole blocking signal (shared WiFi/NAT).
    RATE_LIMIT_ANON_COUNT: int = int(os.getenv("RATE_LIMIT_ANON_COUNT", "5"))
    RATE_LIMIT_AUTH_COUNT: int = int(os.getenv("RATE_LIMIT_AUTH_COUNT", "10"))
    RATE_LIMIT_WINDOW_SECONDS: int = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "600"))


settings = Settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
