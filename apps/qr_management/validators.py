"""Destination URL checks (abuse prevention). Applied to every user-supplied link."""

import ipaddress
import json
import logging
import urllib.request
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)
MAX_URL_LENGTH = 2000


def _host_matches(host: str, domains) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


BLOCKLIST_CACHE_KEY = "qr:blocked-domains"


def blocked_domains() -> set[str]:
    """Settings + staff-managed blocklist, cached for 5 minutes (cleared on change)."""
    from django.core.cache import cache

    from .models import BlockedDomain

    domains = cache.get(BLOCKLIST_CACHE_KEY)
    if domains is None:
        domains = set(getattr(settings, "QRUMY_BLOCKED_DOMAINS", []))
        domains.update(BlockedDomain.objects.values_list("domain", flat=True))
        cache.set(BLOCKLIST_CACHE_KEY, domains, 300)
    return domains


def is_blocked(url: str) -> bool:
    host = (urlsplit(url or "").hostname or "").lower().rstrip(".")
    return bool(host) and _host_matches(host, blocked_domains())


def validate_destination_url(url: str) -> str:
    url = (url or "").strip()
    if len(url) > MAX_URL_LENGTH:
        raise ValidationError(_("The link is too long."))
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValidationError(_("Enter a full web address starting with https:// or http://."))
    if parts.username or parts.password:
        raise ValidationError(_("Links with embedded usernames or passwords are not allowed."))
    host = parts.hostname.lower().rstrip(".")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None and (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved):
        raise ValidationError(_("This address is not allowed."))
    own = urlsplit(settings.QRUMY_QR_BASE_URL)
    if host == (own.hostname or "") and parts.path.startswith(own.path):
        raise ValidationError(_("A QR code cannot point to another Qrumy short link."))
    if _host_matches(host, blocked_domains()):
        raise ValidationError(_("This destination is not allowed on Qrumy."))
    if not url_reputation_ok(url):
        raise ValidationError(_("This link was flagged as unsafe and cannot be used."))
    return url


def url_reputation_ok(url: str) -> bool:
    """Google Safe Browsing lookup when an API key is configured; otherwise allow.

    Network errors never block users (fail open) but are logged.
    """
    key = getattr(settings, "QRUMY_SAFE_BROWSING_KEY", "")
    if not key:
        return True
    body = json.dumps({
        "client": {"clientId": "qrumy", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }).encode()
    req = urllib.request.Request(
        f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={key}",
        data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:  # noqa: S310 — fixed https URL
            return not json.loads(resp.read() or b"{}").get("matches")
    except Exception:  # noqa: BLE001
        logger.warning("Safe Browsing lookup failed", exc_info=True)
        return True
