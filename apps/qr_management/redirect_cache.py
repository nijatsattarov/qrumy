"""Cache of short code → redirect info, so a scan normally costs no database query."""

from django.core.cache import cache

TTL = 300


def _key(code: str) -> str:
    return f"qr:code:{code}"


def get(code: str) -> dict | None:
    return cache.get(_key(code))


def put(code: str, info: dict) -> None:
    cache.set(_key(code), info, TTL)


def invalidate(qr) -> None:
    if qr.short_code:
        cache.delete(_key(qr.short_code))
