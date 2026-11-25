"""Quota/entitlement hooks.

Lower-layer apps (e.g. organizations) must check plan limits without importing
the subscriptions app. subscriptions registers the real backend at startup;
the default backend allows everything (used only before registration).
"""

from collections.abc import Callable
from dataclasses import dataclass


class QuotaExceeded(Exception):
    def __init__(self, feature_key: str, limit: int | None, message: str = ""):
        self.feature_key = feature_key
        self.limit = limit
        super().__init__(message or f"Limit reached for {feature_key} ({limit}).")


@dataclass
class QuotaBackend:
    is_enabled: Callable[[object, str], bool]
    get_limit: Callable[[object, str], int | None]
    plan_name: Callable[[object], str | None] = lambda org: None


_backend = QuotaBackend(is_enabled=lambda org, key: True, get_limit=lambda org, key: None)


def register_backend(backend: QuotaBackend) -> None:
    global _backend
    _backend = backend


def is_enabled(organization, feature_key: str) -> bool:
    return _backend.is_enabled(organization, feature_key)


def get_limit(organization, feature_key: str) -> int | None:
    """None means unlimited."""
    return _backend.get_limit(organization, feature_key)


def check(organization, feature_key: str, current: int, increment: int = 1) -> None:
    """Raise QuotaExceeded if adding ``increment`` would exceed the plan limit."""
    if not is_enabled(organization, feature_key):
        raise QuotaExceeded(feature_key, 0)
    limit = get_limit(organization, feature_key)
    if limit is not None and current + increment > limit:
        raise QuotaExceeded(feature_key, limit)


def plan_name(organization) -> str | None:
    return _backend.plan_name(organization)
