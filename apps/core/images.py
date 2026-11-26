"""Shared rules for public images uploaded by customers (cards, menus, ...)."""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image

from .utils import generate_token

MAX_IMAGE_BYTES = 5 * 1024 * 1024
FORMATS = ("PNG", "JPEG", "WEBP")


def validate_image(file) -> None:
    if file.size > MAX_IMAGE_BYTES:
        raise ValidationError(_("The image must be 5 MB or smaller."))
    try:
        file.seek(0)
        with Image.open(file) as img:
            fmt = img.format
            img.verify()
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(_("Upload a valid PNG, JPEG or WebP image.")) from exc
    finally:
        file.seek(0)
    if fmt not in FORMATS:
        raise ValidationError(_("Upload a valid PNG, JPEG or WebP image."))


def public_path(folder: str, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    if ext not in ("png", "jpg", "jpeg", "webp"):
        ext = "jpg"
    return f"public/{folder}/{generate_token(12)}.{ext}"
