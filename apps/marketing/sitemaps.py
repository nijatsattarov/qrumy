from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    i18n = True
    alternates = True
    x_default = True
    changefreq = "weekly"

    def items(self):
        return ["home", "pricing"]

    def location(self, item):
        return reverse(item)
