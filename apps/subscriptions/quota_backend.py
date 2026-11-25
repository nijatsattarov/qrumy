from apps.core.quotas import QuotaBackend, register_backend

from .entitlements import get_entitlements


def register() -> None:
    register_backend(QuotaBackend(
        is_enabled=lambda org, key: get_entitlements(org).can(key),
        get_limit=lambda org, key: get_entitlements(org).limit(key),
        plan_name=lambda org: getattr(get_entitlements(org).plan, "name", None),
    ))
