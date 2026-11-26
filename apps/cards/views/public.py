"""Public Qrumy Card pages: /c/<token>, vCard download, link clicks, colours."""

from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache

from apps.analytics.enrich import is_bot
from apps.core import quotas

from .. import services
from ..models import Card


def _public_card(token) -> Card:
    card = get_object_or_404(Card.objects.select_related("organization"), public_token=token)
    if not card.is_published or not card.organization.is_active:
        raise Http404
    return card


def _human(request) -> bool:
    return not is_bot(request.headers.get("User-Agent", ""), request.method)


def render_card(request, card, preview=False):
    return render(request, "cards/public/card.html", {
        "card": card, "preview": preview, "photos": list(card.photos.all()),
        "links": list(enumerate(card.links or [])),
        "branding": not quotas.is_enabled(card.organization, "branding.remove"),
        "template_name": card.template})


@never_cache
def card_page(request, token):
    card = _public_card(token)
    if _human(request):
        services.count(card, "views")
    return render_card(request, card)


def card_vcard(request, token):
    card = _public_card(token)
    if _human(request):
        services.count(card, "saves")
    filename = "".join(c for c in card.name if c.isalnum() or c in " -_").strip() or "contact"
    resp = HttpResponse(services.vcard(card), content_type="text/vcard; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="{filename}.vcf"'
    return resp


def card_link(request, token, n):
    card = _public_card(token)
    links = card.links or []
    if n >= len(links):
        raise Http404
    url = links[n].get("url", "")
    if not url.startswith(("https://", "http://", "mailto:", "tel:")):
        raise Http404
    if _human(request):
        services.count(card, "clicks")
    resp = HttpResponseRedirect(url)
    resp["Referrer-Policy"] = "no-referrer"
    return resp


def card_theme(request, token):
    """Card colour as a stylesheet (keeps the page free of inline styles for CSP)."""
    card = get_object_or_404(Card, public_token=token)
    color = card.accent_color if len(card.accent_color) == 7 else "#101B3A"
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    on_accent = "#FFFFFF" if luminance < 160 else "#101B3A"
    css = (f":root{{--card-accent:{color};--card-on-accent:{on_accent};"
           f"--card-accent-soft:rgb({r} {g} {b} / 0.10);"
           f"--card-accent-mid:rgb({r} {g} {b} / 0.22);}}\n")
    resp = HttpResponse(css, content_type="text/css; charset=utf-8")
    resp["Cache-Control"] = "no-cache"
    return resp
