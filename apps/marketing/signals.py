"""Funnel counters from other apps' signals (auth and subscription code stays unchanged)."""

from django.db.models.signals import post_save


def connect() -> None:
    from allauth.account.signals import user_signed_up

    from apps.subscriptions.models import Subscription

    user_signed_up.connect(on_signed_up, dispatch_uid="qrumy-seo-signup")
    post_save.connect(on_subscription, sender=Subscription, dispatch_uid="qrumy-seo-sub")


def on_signed_up(sender, request, user, sociallogin=None, **kwargs):
    from . import seo

    lang = getattr(request, "LANGUAGE_CODE", "") if request else ""
    seo.track("signup_completed", page="signup", language=lang or "")
    if sociallogin is not None:
        seo.track("signup_google", page="signup", language=lang or "")


def on_subscription(sender, instance, created, **kwargs):
    from . import seo

    if created and not instance.plan.is_free:
        seo.track("subscription_started", page=f"plan:{instance.plan.key}")
