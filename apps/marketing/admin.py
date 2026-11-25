from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline
from unfold.decorators import display

from .models import Post, PostImage


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
