from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Asset, FaultReport


@admin.register(Asset)
class AssetAdmin(ModelAdmin):
    list_display = ("asset_code", "name", "organization", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("asset_code", "name", "serial_number", "organization__name")
    list_select_related = ("organization",)
    readonly_fields = ("public_token", "created_by", "qr_code")


@admin.register(FaultReport)
class FaultReportAdmin(ModelAdmin):
    list_display = ("asset", "organization", "category", "priority", "status", "created_at")
    list_filter = ("status", "priority", "category")
    search_fields = ("asset__name", "organization__name", "description")
    list_select_related = ("asset", "organization")
