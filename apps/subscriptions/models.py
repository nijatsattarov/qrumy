from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel, TimeStampedModel


class Plan(TimeStampedModel):
    key = models.SlugField(_("key"), max_length=40, unique=True)
    name = models.CharField(_("name"), max_length=80)
    description = models.CharField(_("description"), max_length=255, blank=True)
    price_monthly_cents = models.PositiveIntegerField(_("monthly price (cents)"), default=0)
    price_yearly_cents = models.PositiveIntegerField(_("yearly price (cents)"), default=0)
    currency = models.CharField(_("currency"), max_length=3, default="USD")
    trial_days = models.PositiveIntegerField(_("trial days"), default=0)
    is_public = models.BooleanField(_("shown on pricing page"), default=True)
    is_beta = models.BooleanField(_("beta plan"), default=False)
    is_active = models.BooleanField(_("active"), default=True)
    sort_order = models.PositiveIntegerField(_("order"), default=0)

    class Meta:
        ordering = ["sort_order", "price_monthly_cents"]
        verbose_name = _("plan")
        verbose_name_plural = _("plans")

    def __str__(self) -> str:
        return self.name

    @property
    def price_monthly(self) -> float:
        return self.price_monthly_cents / 100

    @property
    def is_free(self) -> bool:
        return self.price_monthly_cents == 0 and self.price_yearly_cents == 0


class PlanFeature(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="features")
    feature_key = models.CharField(_("feature"), max_length=64)
    enabled = models.BooleanField(_("enabled"), default=True)
    limit_value = models.PositiveIntegerField(_("limit"), null=True, blank=True,
                                              help_text=_("Empty = unlimited"))

    class Meta:
        verbose_name = _("plan feature")
        verbose_name_plural = _("plan features")
        constraints = [models.UniqueConstraint(fields=["plan", "feature_key"],
                                               name="subscriptions_planfeature_unique")]

    def __str__(self) -> str:
        return f"{self.plan.key}:{self.feature_key}"


class Subscription(TenantModel):
    class Status(models.TextChoices):
        TRIALING = "trialing", _("Trialing")
        ACTIVE = "active", _("Active")
        PAST_DUE = "past_due", _("Past due")
        CANCELED = "canceled", _("Canceled")
        EXPIRED = "expired", _("Expired")

    class Interval(models.TextChoices):
        MONTH = "month", _("Monthly")
        YEAR = "year", _("Yearly")

    CURRENT_STATUSES = (Status.TRIALING, Status.ACTIVE, Status.PAST_DUE)

    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(_("status"), max_length=16, choices=Status.choices,
                              default=Status.ACTIVE)
    interval = models.CharField(_("billing interval"), max_length=8, choices=Interval.choices,
                                default=Interval.MONTH)
    gateway = models.CharField(_("gateway"), max_length=32, default="system",
                               help_text=_("system = assigned automatically, manual = by staff"))
    gateway_ref = models.CharField(_("gateway reference"), max_length=128, blank=True)
    started_at = models.DateTimeField(_("started at"))
    trial_ends_at = models.DateTimeField(_("trial ends"), null=True, blank=True)
    current_period_end = models.DateTimeField(_("current period ends"), null=True, blank=True)
    canceled_at = models.DateTimeField(_("canceled at"), null=True, blank=True)
    ended_at = models.DateTimeField(_("ended at"), null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = _("subscription")
        verbose_name_plural = _("subscriptions")
        constraints = [
            models.UniqueConstraint(
                fields=["organization"],
                condition=Q(status__in=["trialing", "active", "past_due"]),
                name="subscriptions_one_current_per_org",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.organization} — {self.plan} ({self.status})"


class FeatureOverride(TenantModel):
    """Per-organization exception to its plan (granted by staff)."""

    feature_key = models.CharField(_("feature"), max_length=64)
    enabled = models.BooleanField(_("enabled"), default=True)
    limit_value = models.PositiveIntegerField(_("limit"), null=True, blank=True,
                                              help_text=_("Empty = unlimited"))
    reason = models.CharField(_("reason"), max_length=255, blank=True)
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)

    class Meta:
        verbose_name = _("feature override")
        verbose_name_plural = _("feature overrides")
        constraints = [models.UniqueConstraint(fields=["organization", "feature_key"],
                                               name="subscriptions_override_unique")]

    def __str__(self) -> str:
        return f"{self.organization}:{self.feature_key}"


class UsageCounter(TenantModel):
    """Metered usage per period (e.g. metric="qr.scans", period="2026-11")."""

    metric = models.CharField(max_length=64)
    period = models.CharField(max_length=16, default="total")
    value = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "metric", "period"],
                                               name="subscriptions_usage_unique")]
