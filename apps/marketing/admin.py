from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from .models import ContactMessage, ContactPage, Post, PostImage, Promo


class PostImageInline(TabularInline):
    model = PostImage
    extra = 1
    fields = ("image", "markup")
    readonly_fields = ("markup",)
    verbose_name_plural = _("Images for the text (upload, save, then paste the line shown)")

    @admin.display(description=_("Paste into the text"))
    def markup(self, obj):
        if not obj.pk or not obj.image:
            return "—"
        return format_html("<code>![{}]({})</code>", _("description"), obj.image.url)


@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ("title", "language", "state", "published_at", "updated_at")
    list_filter = ("language",)
    search_fields = ("title", "excerpt", "body")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [PostImageInline]
    actions = ["publish_now", "unpublish"]
    save_as = True
    fieldsets = (
        (None, {"fields": ("language", "title", "slug", "excerpt", "body")}),
        (_("SEO"), {"fields": ("seo_title", "meta_description", "keywords")}),
        (_("Cover"), {"fields": ("cover", "cover_alt")}),
        (_("Publishing"), {"fields": ("author_name", "published_at")}),
    )

    @display(description=_("Status"), label={_("Published"): "success",
                                              _("Scheduled"): "info", _("Draft"): "warning"})
    def state(self, obj):
        if obj.is_published:
            return _("Published")
        return _("Scheduled") if obj.published_at else _("Draft")

    @admin.action(description=_("Publish now"))
    def publish_now(self, request, queryset):
        queryset.filter(published_at__isnull=True).update(published_at=timezone.now())

    @admin.action(description=_("Unpublish (back to draft)"))
    def unpublish(self, request, queryset):
        queryset.update(published_at=None)


@admin.register(Promo)
class PromoAdmin(ModelAdmin):
    list_display = ("name", "title", "live_state", "placement", "audience", "language",
                    "starts_at", "ends_at", "priority")
    list_filter = ("is_active", "placement", "audience", "language")
    search_fields = ("name", "title", "message", "coupon_code")
    save_as = True
    fieldsets = (
        (None, {"fields": ("name", "is_active", "priority")}),
        (_("Content"), {"fields": ("language", "badge", "title", "message", "image",
                                   "coupon_code", "button_label", "button_url")}),
        (_("Display"), {"fields": ("placement", "audience", "frequency", "delay_seconds",
                                   "starts_at", "ends_at")}),
    )

    @display(description=_("Status"), label={_("Showing"): "success",
                                              _("Scheduled"): "info", _("Ended"): "danger",
                                              _("Off"): "warning"})
    def live_state(self, obj):
        now = timezone.now()
        if not obj.is_active:
            return _("Off")
        if obj.ends_at and obj.ends_at <= now:
            return _("Ended")
        if obj.starts_at and obj.starts_at > now:
            return _("Scheduled")
        return _("Showing")


@admin.register(ContactPage)
class ContactPageAdmin(ModelAdmin):
    list_display = ("title", "language", "email", "phone", "form_enabled", "updated_at")
    fieldsets = (
        (None, {"fields": ("language", "title", "intro")}),
        (_("Contact details"), {"fields": ("email", "phone", "whatsapp", "address", "map_url",
                                           "hours")}),
        (_("Contact form"), {"fields": ("form_enabled", "notify_email", "success_message")}),
    )


@admin.register(ContactMessage)
class ContactMessageAdmin(ModelAdmin):
    list_display = ("name", "email", "topic", "handled_state", "created_at")
    list_filter = ("is_handled", "topic", "language")
    search_fields = ("name", "email", "company", "message")
    readonly_fields = ("name", "email", "phone", "company", "topic", "message", "language",
                       "created_at")
    fields = ("name", "email", "phone", "company", "topic", "message", "language",
              "created_at", "is_handled", "staff_notes")
    actions = ["mark_handled"]

    def has_add_permission(self, request):
        return False

    @display(description=_("Status"), label={_("New"): "warning", _("Handled"): "success"})
    def handled_state(self, obj):
        return _("Handled") if obj.is_handled else _("New")

    @admin.action(description=_("Mark as handled"))
    def mark_handled(self, request, queryset):
        queryset.update(is_handled=True)


# ------------------------------------------------------------------------------- SEO
from .models import SeoPage, SeoSettings  # noqa: E402


def _page_label(key: str) -> str:
    from .seo_tools import TOOLS_BY_SLUG

    names = {"home": _("Home page"), "pricing": _("Pricing"), "blog": _("Blog"),
             "contact": _("Contact"), "terms": _("Terms of Service"),
             "privacy": _("Privacy Policy")}
    if key.startswith("tool:") and key[5:] in TOOLS_BY_SLUG:
        return TOOLS_BY_SLUG[key[5:]].content["en"]["h1"]
    return str(names.get(key, key))


@admin.register(SeoPage)
class SeoPageAdmin(ModelAdmin):
    list_display = ("page_name", "language", "effective_title", "title_length",
                    "description_length", "keyword_check", "noindex")
    list_filter = ("language", "noindex")
    search_fields = ("page", "title", "meta_description", "keywords", "focus_keyword")
    readonly_fields = ("page", "language", "builtin_texts", "public_link")
    fieldsets = (
        (None, {"fields": ("page", "language", "public_link", "builtin_texts")}),
        (_("Search result"), {"fields": ("title", "meta_description", "focus_keyword",
                                         "keywords")}),
        (_("Page"), {"fields": ("h1", "og_image", "noindex")}),
    )

    def has_add_permission(self, request):
        return False  # one row per page and language is created automatically

    def has_delete_permission(self, request, obj=None):
        return False

    def _effective(self, obj):
        from . import seo

        d = seo.defaults_for(obj.page, obj.language)
        return {"title": seo.brand_title(obj.title or d.get("title", "")),
                "description": obj.meta_description or d.get("description", "")}

    @admin.display(description=_("Page"), ordering="page")
    def page_name(self, obj):
        return _page_label(obj.page)

    @admin.display(description=_("Title in Google"))
    def effective_title(self, obj):
        return self._effective(obj)["title"]

    @display(description=_("Title length"), label={"ok": "success", "long": "warning",
                                                     "short": "warning"})
    def title_length(self, obj):
        n = len(self._effective(obj)["title"])
        return ("ok" if 30 <= n <= 65 else "long" if n > 65 else "short"), f"{n}"

    @display(description=_("Description length"), label={"ok": "success", "long": "warning",
                                                           "short": "warning"})
    def description_length(self, obj):
        n = len(self._effective(obj)["description"])
        return ("ok" if 110 <= n <= 165 else "long" if n > 165 else "short"), f"{n}"

    @display(description=_("Focus keyword"), label={"✓": "success", "✗": "danger"})
    def keyword_check(self, obj):
        kw = obj.focus_keyword.strip().lower()
        if not kw:
            return "—"
        e = self._effective(obj)
        hit = kw in e["title"].lower() and kw in e["description"].lower()
        return "✓" if hit else "✗"

    @admin.display(description=_("Built-in texts (used when the fields below are empty)"))
    def builtin_texts(self, obj):
        from django.utils.html import format_html

        from . import seo

        d = seo.defaults_for(obj.page, obj.language)
        return format_html("<b>{}</b><br>{}<br><i>H1: {}</i>", d.get("title", "—"),
                           d.get("description", "—"), d.get("h1") or "—")

    @admin.display(description=_("Open page"))
    def public_link(self, obj):
        from django.urls import NoReverseMatch, reverse
        from django.utils import translation
        from django.utils.html import format_html

        name = (obj.page if not obj.page.startswith("tool:")
                else "tool_" + obj.page[5:].replace("-", "_"))
        try:
            with translation.override(obj.language):
                url = reverse(name)
        except NoReverseMatch:
            return "—"
        return format_html('<a href="{}" target="_blank" rel="noopener">{}</a>', url, url)


@admin.register(SeoSettings)
class SeoSettingsAdmin(ModelAdmin):
    fieldsets = (
        (_("Titles and sharing"), {"fields": ("title_suffix", "default_og_image")}),
        (_("Search engine verification"), {
            "fields": ("google_site_verification", "bing_site_verification",
                       "yandex_site_verification"),
            "description": _("Paste only the code from the meta tag the search engine gives "
                             "you. It is added to every public page.")}),
        (_("Organization"), {"fields": ("same_as",)}),
    )

    def has_add_permission(self, request):
        return not SeoSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
