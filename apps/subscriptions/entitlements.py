"""What an organization may do, resolved from its current plan + staff overrides."""

from dataclasses import dataclass, field

from django.db.models import Q
from django.utils import timezone

from .features import FEATURES
from .models import FeatureOverride, PlanFeature, Subscription


@dataclass
class Entitlements:
    subscription: Subscription | None
    values: dict[str, tuple[bool, int | None]] = field(default_factory=dict)

    @property
    def plan(self):
        return self.subscription.plan if self.subscription else None

    def can(self, key: str) -> bool:
        return self.values.get(key, (False, 0))[0]

    def limit(self, key: str) -> int | None:
        """Numeric limit; 0 if disabled; None = unlimited."""
        enabled, limit = self.values.get(key, (False, 0))
        return limit if enabled else 0


def current_subscription(organization) -> Subscription | None:
    return (Subscription.objects.for_org(organization)
            .filter(status__in=Subscription.CURRENT_STATUSES).select_related("plan").first())


def get_entitlements(organization) -> Entitlements:
    cached = getattr(organization, "_qrumy_entitlements", None)
    if cached is not None:
        return cached
    sub = current_subscription(organization)
    values: dict[str, tuple[bool, int | None]] = {}
    if sub is not None:
        for pf in PlanFeature.objects.filter(plan=sub.plan):
            values[pf.feature_key] = (pf.enabled, pf.limit_value)
    overrides = FeatureOverride.objects.for_org(organization).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
    for ov in overrides:
        values[ov.feature_key] = (ov.enabled, ov.limit_value)
    # Bool features ignore limits.
    for key, (enabled, _limit) in list(values.items()):
        if key in FEATURES and FEATURES[key].kind == "bool":
            values[key] = (enabled, None)
    ent = Entitlements(subscription=sub, values=values)
    organization._qrumy_entitlements = ent
    return ent


def invalidate(organization) -> None:
    if hasattr(organization, "_qrumy_entitlements"):
        del organization._qrumy_entitlements
