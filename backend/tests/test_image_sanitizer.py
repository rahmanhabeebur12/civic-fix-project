"""
tests/test_image_sanitizer.py

Security tests for app.services.image_sanitizer — the single canonical
choke point every uploaded image (citizen report photo, staff resolution
photo) must pass through before the rest of CivicFix ever sees it.

Run with:
    cd backend && venv/bin/python -m unittest tests.test_image_sanitizer -v
"""
import hashlib
import io
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Point UPLOAD_DIR at an isolated temp directory BEFORE anything imports
# app.config (Settings reads env vars at import time), so these tests
# never touch the real backend/uploads/ directory.
_TEST_UPLOAD_DIR = tempfile.mkdtemp(prefix="civicfix-test-uploads-")
os.environ["UPLOAD_DIR"] = _TEST_UPLOAD_DIR

from PIL import Image  # noqa: E402

from app.config import settings  # noqa: E402
from app.services.image_sanitizer import ImageSanitizationError, sanitize_image_bytes  # noqa: E402


def make_jpeg(size=(400, 300), color=(120, 40, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def make_png(size=(300, 200), color=(0, 200, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def make_jpeg_with_gps_exif() -> bytes:
    img = Image.new("RGB", (200, 150), (10, 120, 200))
    exif = img.getexif()
    exif[0x010F] = "TestCameraMake"
    exif[0x0110] = "TestCameraModel"
    exif[0x0131] = "TestSoftware"
    gps_ifd = exif.get_ifd(0x8825)
    gps_ifd[1] = "N"
    gps_ifd[2] = (13.0, 5.0, 30.0)
    gps_ifd[3] = "E"
    gps_ifd[4] = (80.0, 10.0, 15.0)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


class ImageSanitizerTests(unittest.TestCase):
    def setUp(self):
        self.subdir = "test_uploads"

    def tearDown(self):
        d = os.path.join(settings.UPLOAD_DIR, self.subdir)
        if os.path.isdir(d):
            shutil.rmtree(d)

    # -- Valid uploads --------------------------------------------------

    def test_valid_jpeg_is_decoded_sanitized_and_saved(self):
        result = sanitize_image_bytes(make_jpeg(), subdir=self.subdir)
        self.assertTrue(result.sanitized_path.startswith(f"{self.subdir}/"))
        full_path = os.path.join(settings.UPLOAD_DIR, result.sanitized_path)
        self.assertTrue(os.path.isfile(full_path))
        self.assertGreater(result.size_bytes, 0)
        self.assertEqual((result.width, result.height), (400, 300))
        with Image.open(full_path) as img:
            img.verify()

    def test_valid_png_is_decoded_sanitized_and_saved(self):
        result = sanitize_image_bytes(make_png(), subdir=self.subdir)
        full_path = os.path.join(settings.UPLOAD_DIR, result.sanitized_path)
        self.assertTrue(os.path.isfile(full_path))
        with Image.open(full_path) as img:
            img.verify()

    # -- Type verification (never trust extension/Content-Type) --------

    def test_fake_extension_text_file_is_rejected(self):
        # A .txt file's real content, regardless of any extension/MIME
        # type a client might claim for it.
        data = b"this is not an image, just plain text pretending to be one" * 20
        with self.assertRaises(ImageSanitizationError):
            sanitize_image_bytes(data, subdir=self.subdir)

    def test_content_type_header_claim_is_irrelevant(self):
        # sanitize_image_bytes has no Content-Type parameter at all —
        # bytes that are neither a real GIF nor a real JPEG must be
        # rejected purely on decoded content, no matter what a client
        # claims the type is at the HTTP layer.
        fake_bytes = b"GIF89a" + b"\x00" * 100
        with self.assertRaises(ImageSanitizationError):
            sanitize_image_bytes(fake_bytes, subdir=self.subdir)

    def test_svg_is_rejected(self):
        svg = b"<?xml version='1.0'?><svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
        with self.assertRaises(ImageSanitizationError):
            sanitize_image_bytes(svg, subdir=self.subdir)

    # -- Decode / corruption handling ------------------------------------

    def test_corrupt_truncated_jpeg_is_rejected(self):
        truncated = make_jpeg()[:100]  # cut off mid-stream, well before EOF
        with self.assertRaises(ImageSanitizationError):
            sanitize_image_bytes(truncated, subdir=self.subdir)

    def test_empty_file_is_rejected(self):
        with self.assertRaises(ImageSanitizationError):
            sanitize_image_bytes(b"", subdir=self.subdir)

    # -- Size / dimension limits ------------------------------------------

    def test_oversized_upload_is_rejected(self):
        max_bytes = settings.MAX_IMAGE_UPLOAD_MB * 1024 * 1024
        oversized = b"\xff" * (max_bytes + 1024)
        with self.assertRaises(ImageSanitizationError) as ctx:
            sanitize_image_bytes(oversized, subdir=self.subdir)
        self.assertIn("smaller than", ctx.exception.user_message)

    def test_extreme_dimensions_are_rejected(self):
        # Exceeds the configured MAX_IMAGE_WIDTH without needing a
        # genuinely enormous file on disk to prove the limit is enforced.
        data = make_jpeg(size=(settings.MAX_IMAGE_WIDTH + 500, 100))
        with self.assertRaises(ImageSanitizationError):
            sanitize_image_bytes(data, subdir=self.subdir)

    def test_never_upscales_small_images(self):
        result = sanitize_image_bytes(make_jpeg(size=(50, 40)), subdir=self.subdir)
        self.assertEqual((result.width, result.height), (50, 40))

    def test_downscales_images_larger_than_stored_limit(self):
        big = make_jpeg(size=(settings.MAX_STORED_WIDTH + 800, 1000))
        result = sanitize_image_bytes(big, subdir=self.subdir)
        self.assertLessEqual(result.width, settings.MAX_STORED_WIDTH)
        self.assertLessEqual(result.height, settings.MAX_STORED_HEIGHT)

    # -- Metadata stripping -------------------------------------------------

    def test_exif_and_gps_metadata_are_removed(self):
        data = make_jpeg_with_gps_exif()

        # Sanity check: the source really does carry EXIF + GPS, so this
        # test would fail loudly if the fixture itself were broken.
        source_exif = Image.open(io.BytesIO(data)).getexif()
        self.assertGreater(len(source_exif), 0)
        self.assertIn(0x8825, source_exif)  # GPSInfo IFD pointer present

        result = sanitize_image_bytes(data, subdir=self.subdir)
        full_path = os.path.join(settings.UPLOAD_DIR, result.sanitized_path)

        with Image.open(full_path) as sanitized:
            sanitized.load()
            sanitized_exif = sanitized.getexif()
            self.assertEqual(len(sanitized_exif), 0, "sanitized image must carry no EXIF tags at all")
            self.assertNotIn(0x8825, sanitized_exif)
            self.assertIsNone(sanitized.info.get("exif"))
            self.assertIsNone(sanitized.info.get("icc_profile"))

    def test_transparency_is_flattened_into_supported_mode(self):
        img = Image.new("RGBA", (100, 100), (10, 20, 30, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result = sanitize_image_bytes(buf.getvalue(), subdir=self.subdir)
        full_path = os.path.join(settings.UPLOAD_DIR, result.sanitized_path)
        with Image.open(full_path) as sanitized:
            self.assertEqual(sanitized.mode, "RGB")

    # -- Filenames / paths ----------------------------------------------

    def test_malicious_filename_is_never_used_as_path(self):
        # sanitize_image_bytes doesn't even accept a filename parameter —
        # the stored path is always <subdir>/<server-generated-uuid><ext>.
        result = sanitize_image_bytes(make_jpeg(), subdir=self.subdir)
        self.assertNotIn("..", result.sanitized_path)
        filename = result.sanitized_path.split("/")[-1]
        stem = filename.rsplit(".", 1)[0]
        self.assertEqual(len(stem), 32)
        int(stem, 16)  # raises ValueError if this isn't a valid uuid4 hex

    # -- Re-encoding proof ------------------------------------------------

    def test_reencoded_output_is_not_the_original_bytes(self):
        data = make_jpeg()
        original_sha256 = hashlib.sha256(data).hexdigest()

        result = sanitize_image_bytes(data, subdir=self.subdir)
        full_path = os.path.join(settings.UPLOAD_DIR, result.sanitized_path)
        with open(full_path, "rb") as f:
            sanitized_bytes = f.read()

        self.assertNotEqual(original_sha256, hashlib.sha256(sanitized_bytes).hexdigest())

        with Image.open(io.BytesIO(sanitized_bytes)) as reopened:
            self.assertEqual(reopened.format, result.format.upper())
            reopened.load()


if __name__ == "__main__":
    unittest.main(verbosity=2)
