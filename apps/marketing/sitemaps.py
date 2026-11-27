from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class SiteUrlSitemap(Sitemap):
    """Always list canonical URLs on SITE_URL (https://qrumy.com), whatever host the
    request came in on."""

    @property
    def protocol(self):
        return urlsplit(settings.SITE_URL).scheme or "https"

    def get_domain(self, site=None):
        return urlsplit(settings.SITE_URL).netloc


class StaticViewSitemap(SiteUrlSitemap):
    i18n = True
    alternates = True
    x_default = True
    changefreq = "weekly"

    def items(self):
        from apps.accounts.legal import LegalDocument, current

        pages = ["home", "pricing", "blog", "contact"]
        for kind in (LegalDocument.Kind.TERMS, LegalDocument.Kind.PRIVACY):
            if current(kind, settings.LANGUAGE_CODE):
                pages.append(str(kind))
        return [p for p in pages if not _noindexed(p)]

    def location(self, item):
        return reverse(item)

    def priority(self, item):
        return {"home": 1.0, "pricing": 0.7, "blog": 0.6}.get(item, 0.4)


class ToolSitemap(SiteUrlSitemap):
    """The free QR generator landing pages."""

    i18n = True
    alternates = True
    x_default = True
    changefreq = "monthly"

    def items(self):
        from .seo_tools import TOOLS

        return [t for t in TOOLS if not _noindexed(f"tool:{t.slug}")]

    def location(self, tool):
        return reverse(tool.url_name)

    def priority(self, tool):
        return 0.9 if tool.slug == "qr-code-generator" else 0.8


class BlogSitemap(SiteUrlSitemap):
    """Each post exists in one language, so it is listed under its own address only."""

    changefreq = "monthly"

    def items(self):
        from .models import Post

        return Post.objects.published()

    def lastmod(self, post):
        return post.updated_at

    def priority(self, post):
        return 0.6


def _noindexed(page: str) -> bool:
    """Pages an admin marked noindex in every language are left out."""
    from .models import SeoPage

    langs = {code for code, _n in settings.LANGUAGES}
    hidden = set(SeoPage.objects.filter(page=page, noindex=True)
                 .values_list("language", flat=True))
    return langs <= hidden
