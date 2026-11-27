from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.html import format_html_join

register = template.Library()


@register.simple_tag
def site_verification():
    from apps.marketing.models import SeoSettings

    s = SeoSettings.load()
    pairs = [("google-site-verification", s.google_site_verification),
             ("msvalidate.01", s.bing_site_verification),
             ("yandex-verification", s.yandex_site_verification)]
    return format_html_join("\n", '<meta name="{}" content="{}">',
                            ((n, v.strip()) for n, v in pairs if v and v.strip()))


@register.simple_tag
def default_og_image():
    from apps.marketing.models import SeoSettings

    s = SeoSettings.load()
    url = s.default_og_image.url if s.default_og_image else static("brand/og-default.png")
    return url if url.startswith("http") else settings.SITE_URL + url


@register.simple_tag
def absolute(url: str) -> str:
    return url if str(url).startswith("http") else settings.SITE_URL + str(url)


@register.simple_tag(takes_context=True)
def hreflang_links(context):
    """hreflang + x-default for URL-name pages that exist in every language."""
    from django.urls import NoReverseMatch, reverse
    from django.utils import translation

    request = context.get("request")
    match = getattr(request, "resolver_match", None)
    if match is None or not match.url_name:
        return ""
    links = []
    try:
        for code, _name in settings.LANGUAGES:
            with translation.override(code):
                links.append((code, settings.SITE_URL + reverse(match.view_name,
                                                                kwargs=match.captured_kwargs)))
    except NoReverseMatch:
        return ""
    with translation.override(settings.LANGUAGE_CODE):
        links.append(("x-default", settings.SITE_URL + reverse(match.view_name,
                                                               kwargs=match.captured_kwargs)))
    return format_html_join("\n  ", '<link rel="alternate" hreflang="{}" href="{}">', links)


@register.simple_tag
def free_tools():
    """Links to the free QR generator pages in the current language (footer, 404)."""
    from django.utils import translation

    from apps.marketing.seo_tools import TOOLS, content

    lang = translation.get_language()
    return [{"url_name": t.url_name, "icon": t.icon, "label": content(t, lang)["link_label"]}
            for t in TOOLS]
