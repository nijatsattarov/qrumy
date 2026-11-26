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
