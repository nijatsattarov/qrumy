from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Card, CardPhoto


class CardPhotoInline(TabularInline):
    model = CardPhoto
    extra = 0
    fields = ("image", "caption", "position")


@admin.register(Card)
class CardAdmin(ModelAdmin):
    list_display = ("name", "organization", "kind", "template", "is_published", "updated_at")
    list_filter = ("is_published", "kind", "template")
    search_fields = ("name", "company", "email", "organization__name", "public_token")
    readonly_fields = ("public_token", "created_by", "qr_code")
    inlines = [CardPhotoInline]
