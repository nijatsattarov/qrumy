import hashlib
import hmac
import re
import secrets
import unicodedata
from datetime import date

from django.conf import settings
from django.utils.text import slugify

_AZ_TRANSLIT = str.maketrans({
    "ə": "e", "Ə": "E", "ı": "i", "I": "I", "İ": "I", "ş": "s", "Ş": "S",
    "ç": "c", "Ç": "C", "ğ": "g", "Ğ": "G", "ö": "o", "Ö": "O", "ü": "u", "Ü": "U",
})


def slugify_az(value: str, max_length: int = 50) -> str:
    """ASCII slug that transliterates Azerbaijani letters (ə→e, ş→s, ...)."""
    value = unicodedata.normalize("NFC", value or "").translate(_AZ_TRANSLIT)
    return slugify(value)[:max_length].strip("-")


def generate_token(nbytes: int = 32) -> str:
    """URL-safe random token for public links (invitations, tickets, ...)."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Tokens are stored hashed; only the recipient holds the raw value."""
    return hashlib.sha256(token.encode()).hexdigest()


def hash_ip(ip: str | None, day: date | None = None) -> str:
    """Privacy-preserving IP hash with a daily-rotating salt (not reversible)."""
    if not ip:
        return ""
    day = day or date.today()
    key = f"{settings.SECRET_KEY}:{day.isoformat()}".encode()
    return hmac.new(key, ip.encode(), hashlib.sha256).hexdigest()[:32]


def client_ip(request) -> str | None:
    """Client IP. Behind Nginx we trust exactly one X-Forwarded-For hop."""
    trusted = getattr(settings, "QRUMY_TRUSTED_PROXY_COUNT", 0)
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if trusted and forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if len(parts) >= trusted:
            return parts[-trusted]
    return request.META.get("REMOTE_ADDR")


_SAFE_SCHEMES = re.compile(r"^https?://", re.IGNORECASE)


def is_safe_external_url(url: str) -> bool:
    """Only absolute http(s) URLs are allowed as external destinations."""
    return bool(url) and bool(_SAFE_SCHEMES.match(url.strip())) and "\n" not in url
