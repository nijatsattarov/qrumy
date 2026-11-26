from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    i18n = True
    alternates = True
    x_default = True
    changefreq = "weekly"

    def items(self):
        return ["home", "pricing", "blog", "contact"]

    def location(self, item):
        return reverse(item)


class BlogSitemap(Sitemap):
    """Each post exists in one language, so it is listed under its own address only."""

    changefreq = "monthly"

    def items(self):
        from .models import Post

        return Post.objects.published()

    def lastmod(self, post):
        return post.updated_at
