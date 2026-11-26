from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Menu, MenuCategory, MenuItem


@admin.register(Menu)
class MenuAdmin(ModelAdmin):
    list_display = ("name", "organization", "currency", "is_published", "updated_at")
    list_filter = ("is_published", "currency", "language")
    search_fields = ("name", "organization__name", "public_token")
    readonly_fields = ("public_token", "created_by", "qr_code")


@admin.register(MenuCategory)
class MenuCategoryAdmin(ModelAdmin):
    list_display = ("name", "menu", "position", "is_visible")
    search_fields = ("name", "menu__name")


@admin.register(MenuItem)
class MenuItemAdmin(ModelAdmin):
    list_display = ("name", "menu", "category", "price", "discount_price", "availability")
    list_filter = ("availability",)
    search_fields = ("name", "menu__name")
