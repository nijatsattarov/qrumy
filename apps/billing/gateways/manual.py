from django.utils import timezone

from apps.audit_logs.services import record
from apps.subscriptions.models import Subscription
from apps.subscriptions.services import change_plan

from .base import CheckoutUnavailable, PaymentGateway


class ManualGateway(PaymentGateway):
    """No real payments: plans are assigned by staff and always audited as manual."""

    key = "manual"

    def start_checkout(self, *, organization, plan, interval, actor):
        raise CheckoutUnavailable("Online payment is not available yet.")

    def cancel(self, *, subscription, actor):
        subscription.status = Subscription.Status.CANCELED
        subscription.canceled_at = timezone.now()
        subscription.ended_at = timezone.now()
        subscription.save(update_fields=["status", "canceled_at", "ended_at", "updated_at"])
        record("billing.subscription_canceled", actor=actor,
               organization=subscription.organization, target=subscription)

    def handle_webhook(self, request):
        raise NotImplementedError("The manual gateway has no webhooks.")

    def assign_plan(self, *, organization, plan, interval="month", actor, reason="",
                    request=None) -> Subscription:
        sub = change_plan(organization=organization, plan=plan, gateway=self.key,
                          interval=interval)
        record("admin.billing.plan_assigned", actor=actor, organization=organization,
               target=sub, changes={"plan": plan.key, "interval": interval, "reason": reason},
               request=request)
        return sub
