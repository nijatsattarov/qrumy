"""SEO helpers: page metadata with admin overrides, structured data, funnel events."""

import json
from urllib.parse import urlsplit

from django.conf import settings
from django.core.cache import cache
from django.db.models import F
from django.templatetags.static import static
from django.utils import timezone, translation
from django.utils.safestring import mark_safe

SEARCH_ENGINES = ("google.", "bing.", "yandex.", "duckduckgo.", "yahoo.", "baidu.",
                  "ecosia.", "brave.")
SOCIAL = ("facebook.", "instagram.", "t.co", "twitter.", "x.com", "linkedin.", "tiktok.",
          "youtube.", "whatsapp.", "telegram.", "t.me")


def _override(page: str, language: str):
    from .models import SeoPage

    key = f"qrumy:seo:{page}:{language}"
    value = cache.get(key)
    if value is None:
        value = SeoPage.objects.filter(page=page, language=language).first() or False
        cache.set(key, value, 300)
    return value or None


def brand_title(title: str) -> str:
    from .models import SeoSettings

    if "qrumy" in title.lower():
        return title
    return title + SeoSettings.load().title_suffix


def page_meta(request, page: str, *, title: str, description: str, h1: str = "",
              image: str = "", og_type: str = "website") -> dict:
    """Metadata for a public page: built-in texts, replaced by what admins set."""
    from .models import SeoSettings

    lang = translation.get_language() or settings.LANGUAGE_CODE
    ov = _override(page, lang)
    site = SeoSettings.load()
    if ov and ov.og_image:
        image = ov.og_image.url
    elif not image:
        image = site.default_og_image.url if site.default_og_image else \
            static("brand/og-default.png")
    if image.startswith("/"):
        image = settings.SITE_URL + image
    meta = {
        "page": page,
        "title": brand_title((ov and ov.title) or title),
        "description": (ov and ov.meta_description) or description,
        "keywords": (ov and ov.keywords) or "",
        "h1": (ov and ov.h1) or h1,
        "image": image,
        "noindex": bool(ov and ov.noindex),
        "og_type": og_type,
        "url": settings.SITE_URL + request.path,
    }
    return meta


def json_ld(data) -> str:
    """JSON-LD safe to place inside <script> (same escaping as json_script)."""
    text = json.dumps(data, ensure_ascii=False)
    text = text.translate({ord(">"): "\\u003E", ord("<"): "\\u003C", ord("&"): "\\u0026"})
    return mark_safe(text)  # noqa: S308 — escaped above


def organization_ld() -> dict:
    from .models import SeoSettings

    data = {"@type": "Organization", "@id": settings.SITE_URL + "/#organization",
            "name": "Qrumy", "url": settings.SITE_URL + "/",
            "logo": settings.SITE_URL + static("brand/qrumy-logo-512.png")}
    same = SeoSettings.load().same_as_list
    if same:
        data["sameAs"] = same
    return data


def breadcrumbs_ld(items: list[tuple[str, str]]) -> dict:
    return {"@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i, "name": name, "item": settings.SITE_URL + url}
        for i, (name, url) in enumerate(items, start=1)]}


def faq_ld(pairs) -> dict:
    return {"@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": str(q),
         "acceptedAnswer": {"@type": "Answer", "text": str(a)}} for q, a in pairs]}


def graph(*nodes) -> str:
    return json_ld({"@context": "https://schema.org", "@graph": [n for n in nodes if n]})


# ------------------------------------------------------------------------------ events
FUNNEL = ["tool_view", "qr_type_selected", "qr_generated", "qr_download_png",
          "qr_download_svg", "pricing_view", "cta_dynamic_click", "cta_upgrade_click",
          "signup_completed", "signup_google", "subscription_started"]


def traffic_source(request) -> str:
    ref = (request.headers.get("Referer") or "").lower()
    if not ref:
        return "direct"
    host = urlsplit(ref).hostname or ""
    if host and host == urlsplit(settings.SITE_URL).hostname:
        return "internal"
    if any(s in host for s in SEARCH_ENGINES):
        return "search"
    if any(s in host for s in SOCIAL):
        return "social"
    return "other"


def track(name: str, *, page: str = "", language: str = "", source: str = "") -> None:
    """Add one to today's anonymous counter. Never raises."""
    from .models import SiteEvent

    if name not in FUNNEL:
        return
    try:
        day = timezone.localdate()
        key = {"day": day, "name": name, "page": page[:80], "language": language[:8],
               "source": source[:10]}
        if not SiteEvent.objects.filter(**key).update(count=F("count") + 1):
            obj, created = SiteEvent.objects.get_or_create(**key, defaults={"count": 1})
            if not created:
                SiteEvent.objects.filter(pk=obj.pk).update(count=F("count") + 1)
    except Exception:  # noqa: BLE001 — analytics must never break a page
        import logging

        logging.getLogger(__name__).warning("Could not record site event %s", name)


def is_bot(request) -> bool:
    from apps.analytics.enrich import is_bot as _is_bot

    return _is_bot(request.headers.get("User-Agent", ""), request.method)


def defaults_for(page: str, language: str | None = None) -> dict:
    """Built-in title / description / H1 of a page (shown in the admin, used as fallback)."""
    from django.utils.translation import gettext as _

    language = language or translation.get_language() or settings.LANGUAGE_CODE
    with translation.override(language):
        if page.startswith("tool:"):
            from .seo_tools import TOOLS_BY_SLUG, content

            tool = TOOLS_BY_SLUG.get(page[5:])
            if tool is None:
                return {}
            c = content(tool, language)
            return {"title": c["title"], "description": c["description"], "h1": c["h1"]}
        texts = {
            "home": (_("Free QR Code Generator – Create & Download QR Codes | Qrumy"),
                     _("Create free QR codes for URLs, WiFi, email, phone, WhatsApp and more. "
                       "Customize your QR code and download PNG or SVG instantly. No signup "
                       "required."),
                     _("Free QR Code Generator – Create QR Codes Instantly")),
            "pricing": (_("Pricing – Free Beta, Simple Plans | Qrumy"),
                        _("Qrumy is free during the beta: dynamic QR codes, analytics, digital "
                          "cards, menus, surveys and more. See the planned plans and limits."),
                        ""),
            "blog": (_("QR Code Guides & Business Tips – Qrumy Blog"),
                     _("Guides and news about QR codes, customer feedback and asset "
                       "management from the Qrumy team."), ""),
        }
        if page in texts:
            t, d, h = texts[page]
            return {"title": str(t), "description": str(d), "h1": str(h)}
        if page == "contact":
            from .models import ContactPage

            cp = ContactPage.objects.filter(language=language).first()
            return {"title": cp.title if cp else str(_("Contact")),
                    "description": (cp.intro[:160] if cp else ""), "h1": ""}
        if page in ("terms", "privacy"):
            from apps.accounts.legal import current

            doc = current(page, language)
            return {"title": doc.title if doc else page, "description": "", "h1": ""}
        return {}


SEO_PAGES = ["home", "pricing", "blog", "contact", "terms", "privacy"]


def all_page_keys() -> list[str]:
    from .seo_tools import TOOLS

    return SEO_PAGES + [f"tool:{t.slug}" for t in TOOLS]
