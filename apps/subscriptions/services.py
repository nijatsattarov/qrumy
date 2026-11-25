from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .entitlements import current_subscription, invalidate
from .models import Plan, Subscription


class SubscriptionError(Exception):
    pass


@transaction.atomic
def change_plan(*, organization, plan: Plan, gateway: str, interval: str = "month",
                gateway_ref: str = "") -> Subscription:
    """End the current subscription (if any) and start a new active one."""
    now = timezone.now()
    previous = current_subscription(organization)
    if previous is not None:
        previous.status = Subscription.Status.CANCELED
        previous.canceled_at = previous.canceled_at or now
        previous.ended_at = now
        previous.save(update_fields=["status", "canceled_at", "ended_at", "updated_at"])
    status = Subscription.Status.TRIALING if plan.trial_days else Subscription.Status.ACTIVE
    sub = Subscription.objects.create(
        organization=organization, plan=plan, status=status, interval=interval,
        gateway=gateway, gateway_ref=gateway_ref, started_at=now,
        trial_ends_at=now + timezone.timedelta(days=plan.trial_days) if plan.trial_days else None,
    )
    invalidate(organization)
    return sub


def start_default_subscription(organization) -> Subscription:
    try:
        plan = Plan.objects.get(key=settings.QRUMY_DEFAULT_PLAN, is_active=True)
    except Plan.DoesNotExist as exc:
        raise SubscriptionError(
            f"Default plan '{settings.QRUMY_DEFAULT_PLAN}' is missing; run migrations.") from exc
    return change_plan(organization=organization, plan=plan, gateway="system")
