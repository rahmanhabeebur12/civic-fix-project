"""
Storage-path helpers. Actual upload validation/sanitization lives in
app/services/image_sanitizer.py — the single canonical place any image
upload is decoded, cleaned, and saved. Nothing in this module writes
uploaded bytes to disk.
"""


def resolve_url(relative_path: str) -> str:
    if not relative_path:
        return ""
    return f"/uploads/{relative_path}"
