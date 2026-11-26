from django import template
from django.urls import reverse
from django.utils import translation

register = template.Library()


def pick_promo(request, area: str):
    """The offer to show on this page, or None. area: "home" | "public" | "app"."""
    from apps.marketing.models import Promo

    placements = {"home": ["home", "public", "everywhere"], "public": ["public", "everywhere"],
                  "app": ["app", "everywhere"]}[area]
    user = getattr(request, "user", None)
    signed_in = bool(user and user.is_authenticated)
    audiences = ["all", "users" if signed_in else "guests"]
    lang = translation.get_language()
    for promo in Promo.objects.live().filter(placement__in=placements, audience__in=audiences):
        if promo.language in ("", lang):
            return promo
    return None


@register.inclusion_tag("marketing/promo/_popup.html", takes_context=True)
def promo_popup(context, area="public"):
    request = context.get("request")
    if request is None:
        return {}
    promo = pick_promo(request, area)
    if promo is None:
        return {}
    url = promo.button_url or reverse("account_signup")
    return {"promo": promo, "button_url": url}
