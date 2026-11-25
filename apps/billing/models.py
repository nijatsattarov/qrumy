from django.utils.translation import gettext_lazy as _

from apps.subscriptions.models import Subscription


class PlanAssignment(Subscription):
    """Admin-only proxy: staff assign a plan through the ManualGateway (audited)."""

    class Meta:
        proxy = True
        verbose_name = _("plan assignment")
        verbose_name_plural = _("plan assignments")
