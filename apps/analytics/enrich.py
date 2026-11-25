"""Turn a raw request snapshot into analytics fields (device, OS, browser, geo, bot)."""

import logging
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from ua_parser import parse

logger = logging.getLogger(__name__)

BOT_PATTERN = re.compile(
    r"bot|crawl|spider|slurp|preview|fetch|scan|monitor|curl|wget|python|httpclient|"
    r"facebookexternalhit|whatsapp|telegram|discord|skype|headless|lighthouse",
    re.IGNORECASE)


def is_bot(user_agent: str, method: str = "GET") -> bool:
    return method == "HEAD" or not user_agent or bool(BOT_PATTERN.search(user_agent))


def parse_user_agent(user_agent: str) -> dict:
    result = parse(user_agent or "")
    os_family = (result.os.family if result.os else "") or ""
    browser = (result.user_agent.family if result.user_agent else "") or ""
    device = (result.device.family if result.device else "") or ""
    ua = (user_agent or "").lower()
    if "ipad" in ua or "tablet" in ua or ("android" in ua and "mobile" not in ua):
        kind = "tablet"
    elif "mobi" in ua or "iphone" in ua or os_family in ("iOS", "Android"):
        kind = "mobile"
    elif os_family in ("Windows", "Mac OS X", "macOS", "Linux", "Ubuntu", "Chrome OS"):
        kind = "desktop"
    else:
        kind = "other"
    return {"device": kind, "os": "" if os_family == "Other" else os_family[:40],
            "browser": "" if browser == "Other" else browser[:40],
            "device_family": device}


@lru_cache(maxsize=1)
def _geo_reader():
    path = Path(settings.QRUMY_GEOIP_CITY_DB)
    if not path.exists():
        return None
    try:
        import geoip2.database

        return geoip2.database.Reader(str(path))
    except Exception:  # noqa: BLE001
        logger.exception("Could not open GeoIP database")
        return None


def geolocate(ip: str | None, country_header: str = "") -> dict:
    """Country/region/city from IP (approximate; never GPS). Empty when unknown."""
    reader = _geo_reader()
    if reader and ip:
        try:
            r = reader.city(ip)
            return {"country": (r.country.iso_code or "")[:2],
                    "region": (r.subdivisions.most_specific.name or "")[:80],
                    "city": (r.city.name or "")[:80]}
        except Exception:  # noqa: BLE001, S110 — private/unknown IPs have no location
            pass
    country = (country_header or "").upper()
    if len(country) == 2 and country.isalpha() and country not in ("XX", "T1"):
        return {"country": country, "region": "", "city": ""}
    return {"country": "", "region": "", "city": ""}


def referrer_host(referrer: str) -> str:
    try:
        return (urlsplit(referrer).hostname or "")[:120]
    except ValueError:
        return ""
