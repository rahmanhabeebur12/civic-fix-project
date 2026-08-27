"""
image_sanitizer.py

The single canonical choke-point for turning an untrusted uploaded image
(citizen report photo, officer resolution photo, or any future image
upload) into a safe, normalized file. No router or other service may save
uploaded image bytes directly.

This is defense-in-depth image sanitization — layered controls that make
a broad range of attacks (fake extensions, oversized files, decompression
bombs, EXIF/GPS leakage, path traversal, polyglots) meaningfully harder.
It is not a claim that no image-parser vulnerability could ever exist.

Flow:

    raw bytes (already size-capped while reading the stream)
    -> optional antivirus scan
    -> decode with Pillow (structural verify + full pixel load)
    -> reject unsupported formats / corrupt data / decompression bombs
    -> apply EXIF orientation, then discard all EXIF/ICC/XMP metadata
    -> copy pixel data into a brand-new Image object (no original chunks)
    -> resize down (never up) if larger than what CivicFix needs
    -> re-encode to a single configured format under a server-generated
       UUID filename
    -> return only the sanitized path + basic dimensions

The original uploaded bytes are held in memory only (never written to
disk unsanitized) and are discarded as soon as this function returns or
raises — there is no on-disk temporary-original to leak or clean up.
"""
from __future__ import annotations

import io
import logging
import os
import uuid
import warnings
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import UploadFile

from app.config import settings
from app.services.antivirus_service import scan_bytes

logger = logging.getLogger("civicfix.image_sanitizer")

# Pillow's Image.format value for each format we accept. Deliberately
# small — SVG (active XML content), GIF, BMP, and TIFF are all rejected.
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP"}

SAFE_USER_MESSAGE = "We couldn't process this image. Please choose a valid JPEG, PNG, or WebP image."
SAFE_TOO_LARGE_MESSAGE = "This image is too large to process. Please choose a smaller image."


class ImageSanitizationError(Exception):
    """Raised for any rejected upload.

    `user_message` is safe to return to citizens/staff as-is. The
    technical `log_detail` (parser exception type, byte counts, etc.)
    is logged server-side only and never included in the HTTP response.
    """

    def __init__(self, user_message: str, log_detail: str):
        super().__init__(log_detail)
        self.user_message = user_message
        self.log_detail = log_detail


@dataclass
class SanitizedImage:
    sanitized_path: str  # relative path under UPLOAD_DIR, e.g. "reports/<uuid>.webp"
    format: str
    width: int
    height: int
    size_bytes: int


def _output_format() -> str:
    fmt = (settings.SANITIZED_IMAGE_FORMAT or "webp").strip().upper()
    return fmt if fmt in ("WEBP", "JPEG") else "WEBP"


def _output_extension(output_format: str) -> str:
    return ".webp" if output_format == "WEBP" else ".jpg"


# ---------------------------------------------------------------------------
# 1. SIZE ENFORCEMENT (stream-level, not just Content-Length)
# ---------------------------------------------------------------------------

async def read_upload_enforcing_limit(file: UploadFile) -> bytes:
    """Reads an UploadFile in bounded chunks, aborting as soon as the
    running total exceeds the configured limit — a client cannot bypass
    this by lying about (or omitting) Content-Length."""
    max_bytes = settings.MAX_IMAGE_UPLOAD_MB * 1024 * 1024
    chunk_size = 1024 * 1024
    buffer = io.BytesIO()
    total = 0

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ImageSanitizationError(
                f"Image must be smaller than {settings.MAX_IMAGE_UPLOAD_MB}MB.",
                f"upload rejected: size limit exceeded while streaming (>{max_bytes} bytes)",
            )
        buffer.write(chunk)

    return buffer.getvalue()


def _enforce_size(data: bytes) -> None:
    """Backstop size check for callers that already have full bytes in
    hand (e.g. tests, or offline-synced reports)."""
    if not data:
        raise ImageSanitizationError(SAFE_USER_MESSAGE, "upload rejected: empty file")
    max_bytes = settings.MAX_IMAGE_UPLOAD_MB * 1024 * 1024
    if len(data) > max_bytes:
        raise ImageSanitizationError(
            f"Image must be smaller than {settings.MAX_IMAGE_UPLOAD_MB}MB.",
            f"upload rejected: size limit ({len(data)} bytes)",
        )


# ---------------------------------------------------------------------------
# 2-3. TYPE VERIFICATION + DECODE (never trust extension/Content-Type)
# ---------------------------------------------------------------------------

def _decode(data: bytes) -> Image.Image:
    # Pass 1: structural verify(). verify() renders the image object
    # unusable afterward, so pixel data is loaded from a fresh handle.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            probe = Image.open(io.BytesIO(data))
            probe.verify()
    except Image.DecompressionBombWarning as e:
        raise ImageSanitizationError(SAFE_TOO_LARGE_MESSAGE, f"upload rejected: decompression bomb warning ({e})")
    except Image.DecompressionBombError as e:
        raise ImageSanitizationError(SAFE_TOO_LARGE_MESSAGE, f"upload rejected: decompression bomb ({e})")
    except UnidentifiedImageError as e:
        raise ImageSanitizationError(SAFE_USER_MESSAGE, f"upload rejected: unsupported/unrecognized format ({e})")
    except Exception as e:
        raise ImageSanitizationError(SAFE_USER_MESSAGE, f"upload rejected: decoder error ({type(e).__name__})")

    detected_format = probe.format

    # Pass 2: fully decode pixel data (verify() alone does not decode
    # every pixel, so this also catches truncated/corrupt payloads that
    # verify() would miss, and re-triggers Pillow's bomb protection on
    # the full decode path).
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(data))
            img.load()
    except Image.DecompressionBombWarning as e:
        raise ImageSanitizationError(SAFE_TOO_LARGE_MESSAGE, f"upload rejected: decompression bomb warning ({e})")
    except Image.DecompressionBombError as e:
        raise ImageSanitizationError(SAFE_TOO_LARGE_MESSAGE, f"upload rejected: decompression bomb ({e})")
    except Exception as e:
        raise ImageSanitizationError(SAFE_USER_MESSAGE, f"upload rejected: decoder error ({type(e).__name__})")

    if detected_format not in SUPPORTED_FORMATS:
        raise ImageSanitizationError(
            "Only JPEG, PNG, or WebP images are supported.",
            f"upload rejected: unsupported type (detected={detected_format})",
        )

    return img


# ---------------------------------------------------------------------------
# 4. DIMENSION / PIXEL-COUNT LIMITS (hard reject, independent of Pillow's
#    own default decompression-bomb threshold — configurable and tighter)
# ---------------------------------------------------------------------------

def _enforce_dimensions(img: Image.Image) -> None:
    width, height = img.size
    pixels = width * height
    if width > settings.MAX_IMAGE_WIDTH or height > settings.MAX_IMAGE_HEIGHT or pixels > settings.MAX_IMAGE_PIXELS:
        raise ImageSanitizationError(
            SAFE_TOO_LARGE_MESSAGE,
            f"upload rejected: invalid dimensions ({width}x{height}={pixels}px, "
            f"limits {settings.MAX_IMAGE_WIDTH}x{settings.MAX_IMAGE_HEIGHT}/{settings.MAX_IMAGE_PIXELS}px)",
        )


# ---------------------------------------------------------------------------
# 5-8. ORIENTATION, METADATA STRIP, FRESH IMAGE, MODE NORMALIZATION
# ---------------------------------------------------------------------------

def _normalize_and_strip_metadata(img: Image.Image) -> Image.Image:
    # Apply EXIF orientation before the EXIF data is discarded, so the
    # sanitized image still looks correctly rotated.
    img = ImageOps.exif_transpose(img) or img

    # Flatten any transparency onto a white background, then copy pixel
    # data into a brand-new Image object. The new object carries no
    # .info, no EXIF, no ICC profile, no XMP, no embedded thumbnails —
    # only pixels. This also normalizes every possible source mode
    # (RGBA, LA, P, L, CMYK, ...) into one explicit output mode: RGB.
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        flattened = Image.new("RGB", rgba.size, (255, 255, 255))
        flattened.paste(rgba, mask=rgba.split()[-1])
    else:
        flattened = img.convert("RGB")

    clean = Image.new("RGB", flattened.size)
    clean.paste(flattened)
    return clean


# ---------------------------------------------------------------------------
# 9. RESIZE (downscale only, never upscale)
# ---------------------------------------------------------------------------

def _resize_if_needed(img: Image.Image) -> Image.Image:
    max_w, max_h = settings.MAX_STORED_WIDTH, settings.MAX_STORED_HEIGHT
    if img.width <= max_w and img.height <= max_h:
        return img
    # thumbnail() mutates in place and only ever shrinks to fit the box —
    # it never enlarges an image smaller than the target.
    img.thumbnail((max_w, max_h), Image.LANCZOS)
    return img


# ---------------------------------------------------------------------------
# 10-11. RE-ENCODE + SERVER-GENERATED FILENAME
# ---------------------------------------------------------------------------

def _save(img: Image.Image, subdir: str) -> tuple[str, int]:
    output_format = _output_format()
    ext = _output_extension(output_format)

    # subdir is always one of our own constants ("reports"/"resolutions"),
    # never derived from user input, and the filename is always a fresh
    # UUID — there is no path-traversal surface here.
    target_dir = os.path.join(settings.UPLOAD_DIR, subdir)
    os.makedirs(target_dir, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    full_path = os.path.join(target_dir, filename)

    save_kwargs = {"quality": settings.SANITIZED_IMAGE_QUALITY}
    if output_format == "WEBP":
        save_kwargs["method"] = 6
    else:
        save_kwargs["optimize"] = True

    # img is the freshly-constructed clean object with no .info — Pillow
    # has nothing inherited to write back out, so no EXIF/ICC/XMP survives.
    img.save(full_path, format=output_format, **save_kwargs)

    return f"{subdir}/{filename}", os.path.getsize(full_path)


# ---------------------------------------------------------------------------
# ORCHESTRATOR — the only function callers should use
# ---------------------------------------------------------------------------

def sanitize_image_bytes(data: bytes, *, subdir: str) -> SanitizedImage:
    """Runs the full sanitization pipeline over already-collected bytes
    and returns the sanitized file's path/format/dimensions/size.

    Raises ImageSanitizationError (safe user_message + server-only
    log_detail) for any rejected upload. Never partially writes a file —
    either a fully sanitized file is saved, or nothing is.
    """
    _enforce_size(data)

    if settings.ANTIVIRUS_ENABLED:
        scan = scan_bytes(data)
        if not scan.clean:
            raise ImageSanitizationError(SAFE_USER_MESSAGE, f"antivirus scan failure: {scan.reason}")

    img = _decode(data)
    _enforce_dimensions(img)
    img = _normalize_and_strip_metadata(img)
    img = _resize_if_needed(img)
    sanitized_path, size_bytes = _save(img, subdir)

    logger.info(
        "upload sanitized successfully: path=%s format=%s dims=%dx%d size=%d",
        sanitized_path, _output_format(), img.width, img.height, size_bytes,
    )

    return SanitizedImage(
        sanitized_path=sanitized_path,
        format=_output_format().lower(),
        width=img.width,
        height=img.height,
        size_bytes=size_bytes,
    )


async def sanitize_uploaded_file(file: UploadFile, *, subdir: str) -> SanitizedImage:
    """Convenience wrapper for FastAPI routes: streams the upload with a
    size cap enforced during reading, then sanitizes it."""
    data = await read_upload_enforcing_limit(file)
    return sanitize_image_bytes(data, subdir=subdir)


def delete_sanitized_image(relative_path: str) -> None:
    """Best-effort cleanup of a previously sanitized file (used when the
    surrounding report/resolution creation fails after the image was
    already saved, so we don't strand orphaned files)."""
    if not relative_path:
        return
    full_path = os.path.join(settings.UPLOAD_DIR, relative_path)
    try:
        if os.path.commonpath([os.path.abspath(full_path), os.path.abspath(settings.UPLOAD_DIR)]) == os.path.abspath(settings.UPLOAD_DIR):
            os.remove(full_path)
    except FileNotFoundError:
        pass
    except OSError as e:
        logger.warning("failed to delete sanitized image %s: %s", relative_path, e)
