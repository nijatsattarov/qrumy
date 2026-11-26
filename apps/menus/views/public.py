"""Public Digital Menu page (/m/<token>), view counting and colours."""

import json

from django.db.models import Prefetch
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import translation
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.analytics.enrich import is_bot
from apps.core import quotas

from .. import services
from ..models import Menu, MenuCategory, MenuItem


def _public_menu(token) -> Menu:
    menu = get_object_or_404(Menu.objects.select_related("organization"), public_token=token)
    if not menu.is_published or not menu.organization.is_active:
        raise Http404
    return menu


def render_menu(request, menu, preview=False):
    items = MenuItem.objects.exclude(availability="hidden").order_by("position", "pk") \
        .prefetch_related("options")
    categories = [c for c in menu.categories.filter(is_visible=True).prefetch_related(
        Prefetch("items", queryset=items)) if c.items.all()]
    with translation.override(menu.language):
        return render(request, "menus/public/menu.html", {
            "menu": menu, "categories": categories, "preview": preview,
            "branding": not quotas.is_enabled(menu.organization, "branding.remove")})


@never_cache
def menu_page(request, token):
    menu = _public_menu(token)
    if not is_bot(request.headers.get("User-Agent", ""), request.method):
        services.count(menu, "view")
    return render_menu(request, menu)


@csrf_exempt  # anonymous beacon from the menu page; it only increments counters
@require_POST
@ratelimit(key="ip", rate="120/m", block=False)
def menu_event(request, token):
    menu = _public_menu(token)
    if getattr(request, "limited", False) or is_bot(request.headers.get("User-Agent", "")):
        return JsonResponse({"ok": True})
    try:
        data = json.loads(request.body or b"{}")
        kind, oid = data.get("t"), int(data.get("id", 0))
    except (ValueError, TypeError):
        return JsonResponse({"ok": False}, status=400)
    model = {"item": MenuItem, "category": MenuCategory}.get(kind)
    if model is None or not model.objects.filter(pk=oid, menu=menu).exists():
        return JsonResponse({"ok": False}, status=400)
    services.count(menu, kind, oid)
    return JsonResponse({"ok": True})


def menu_theme(request, token):
    menu = get_object_or_404(Menu, public_token=token)
    color = menu.accent_color if len(menu.accent_color) == 7 else "#101B3A"
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    on_accent = "#FFFFFF" if (0.2126 * r + 0.7152 * g + 0.0722 * b) < 160 else "#101B3A"
    css = (f":root{{--menu-accent:{color};--menu-on-accent:{on_accent};"
           f"--menu-accent-soft:rgb({r} {g} {b} / 0.10);}}\n")
    resp = HttpResponse(css, content_type="text/css; charset=utf-8")
    resp["Cache-Control"] = "no-cache"
    return resp
