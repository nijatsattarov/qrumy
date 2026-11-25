"""Validation of files hosted behind dynamic codes (PDF / images)."""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from PIL import Image

IMAGE_FORMATS = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


def sniff_content_type(upload) -> str:
    """Detect the real type from the file's bytes (the client's claim is ignored)."""
    upload.seek(0)
    head = upload.read(8)
    upload.seek(0)
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    try:
        with Image.open(upload) as img:
            fmt = img.format
            img.verify()
    except Exception:  # noqa: BLE001
        fmt = None
    finally:
        upload.seek(0)
    return IMAGE_FORMATS.get(fmt or "", "")


def validate_hosted_file(upload, allowed: tuple[str, ...], max_mb: int | None) -> str:
    if max_mb is not None and upload.size > max_mb * 1024 * 1024:
        raise ValidationError(_("The file must be %(mb)s MB or smaller.") % {"mb": max_mb})
    content_type = sniff_content_type(upload)
    if content_type not in allowed:
        raise ValidationError(_("This file type is not supported here."))
    return content_type
