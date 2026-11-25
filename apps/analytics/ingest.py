"""Scan ingestion.

The redirect view calls ``record_scan`` with a small snapshot. With the Redis buffer
the snapshot is pushed to a list in O(1) and the redirect returns immediately; a
Celery task drains the list in batches (``process_batch``). Raw IPs never leave this
module: they are hashed (daily salt) and geolocated, then discarded.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime

from django.apps import apps
from django.conf import settings
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone

from apps.core.utils import hash_ip

from .enrich import geolocate, is_bot, parse_user_agent, referrer_host
from .models import Scan

logger = logging.getLogger(__name__)
BUFFER_KEY = "qrumy:scan-buffer"
DIMENSIONS = ("device", "os", "browser", "country", "city", "referrer", "source", "campaign")


def _redis():
    import redis

    return redis.Redis.from_url(settings.REDIS_URL)


def record_scan(*, qr_code_id: int, organization_id: int, ip: str | None, user_agent: str,
                referrer: str, query: dict, method: str = "GET", country_header: str = "",
                when: datetime | None = None) -> None:
    when = when or timezone.now()
    geo = geolocate(ip, country_header)
    snapshot = {
        "qr": qr_code_id, "org": organization_id, "at": when.isoformat(),
        "ip": hash_ip(ip, when.date()), "ua": (user_agent or "")[:400],
        "ref": referrer_host(referrer or ""), "method": method,
        "utm": {k: str(query.get(f"utm_{k}", ""))[:80] for k in ("source", "medium", "campaign")},
        **geo,
    }
    if settings.QRUMY_SCAN_BUFFER == "redis":
        try:
            _redis().rpush(BUFFER_KEY, json.dumps(snapshot))
            return
        except Exception:  # noqa: BLE001 — never lose a redirect because Redis is down
            logger.warning("Scan buffer unavailable; writing synchronously", exc_info=True)
    process_batch([snapshot])


def drain_buffer(max_items: int = 2000) -> int:
    client = _redis()
    pipe = client.pipeline()
    pipe.lrange(BUFFER_KEY, 0, max_items - 1)
    pipe.ltrim(BUFFER_KEY, max_items, -1)
    raw, _ = pipe.execute()
    if raw:
        process_batch([json.loads(item) for item in raw])
    return len(raw)


@transaction.atomic
def process_batch(snapshots: list[dict]) -> None:
    QRCode = apps.get_model("qr_management", "QRCode")  # noqa: N806 — lower layer, no import

    rows = []
    for s in snapshots:
        ua = parse_user_agent(s["ua"])
        rows.append(Scan(
            organization_id=s["org"], qr_code_id=s["qr"],
            scanned_at=datetime.fromisoformat(s["at"]), ip_hash=s["ip"],
            device=ua["device"], os=ua["os"], browser=ua["browser"],
            country=s.get("country", ""), region=s.get("region", ""), city=s.get("city", ""),
            referrer=s.get("ref", ""), utm_source=s["utm"]["source"],
            utm_medium=s["utm"]["medium"], utm_campaign=s["utm"]["campaign"],
            is_bot=is_bot(s["ua"], s.get("method", "GET")),
        ))
    existing_ids = set(QRCode.objects.filter(pk__in={r.qr_code_id for r in rows})
                       .values_list("pk", flat=True))
    rows = [r for r in rows if r.qr_code_id in existing_ids]
    if not rows:
        return

    # Which (qr, day, ip) were already seen before this batch? → unique counting
    humans = [r for r in rows if not r.is_bot]
    seen = set()
    if humans:
        days = {r.scanned_at.date() for r in humans}
        seen = set(Scan.objects.filter(
            qr_code_id__in={r.qr_code_id for r in humans}, scanned_at__date__in=days,
            is_bot=False).exclude(ip_hash="")
            .values_list("qr_code_id", "scanned_at__date", "ip_hash"))
    Scan.objects.bulk_create(rows)

    agg: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
    latest: dict[int, datetime] = {}
    counts: dict[int, int] = defaultdict(int)
    for r in humans:
        day = r.scanned_at.date()
        key = (r.qr_code_id, day, r.ip_hash)
        unique = 1 if r.ip_hash and key not in seen else 0
        seen.add(key)
        values = {"total": "", "device": r.device, "os": r.os, "browser": r.browser,
                  "country": r.country, "city": r.city, "referrer": r.referrer,
                  "source": r.utm_source, "campaign": r.utm_campaign}
        for dim, value in values.items():
            if dim != "total" and not value:
                continue
            slot = agg[(r.organization_id, r.qr_code_id, day, dim, value)]
            slot[0] += 1
            slot[1] += unique
        counts[r.qr_code_id] += 1
        latest[r.qr_code_id] = max(latest.get(r.qr_code_id, r.scanned_at), r.scanned_at)

    if agg:
        _upsert_rollups(agg)
    for qr_id, n in counts.items():
        QRCode.objects.filter(pk=qr_id).update(total_scans=F("total_scans") + n,
                                               last_scan_at=latest[qr_id])


def _upsert_rollups(agg) -> None:
    sql = (
        "INSERT INTO analytics_scandaily "
        "(organization_id, qr_code_id, day, dimension, value, scans, unique_scans) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (qr_code_id, day, dimension, value) DO UPDATE SET "
        "scans = analytics_scandaily.scans + EXCLUDED.scans, "
        "unique_scans = analytics_scandaily.unique_scans + EXCLUDED.unique_scans"
    )
    params = [(org, qr, day, dim, value, n, u)
              for (org, qr, day, dim, value), (n, u) in agg.items()]
    with connection.cursor() as cursor:
        cursor.executemany(sql, params)
