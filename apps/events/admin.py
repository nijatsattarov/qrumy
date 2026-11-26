from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import CapturePoint, Event, Lead


@admin.register(Event)
class EventAdmin(ModelAdmin):
    list_display = ("name", "organization", "starts_on", "ends_on", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "organization__name")


@admin.register(CapturePoint)
class CapturePointAdmin(ModelAdmin):
    list_display = ("name", "event", "company_name")
    search_fields = ("name", "company_name", "event__name")
    readonly_fields = ("capture_token", "portal_token_hash", "qr_code")


@admin.register(Lead)
class LeadAdmin(ModelAdmin):
    list_display = ("full_name", "event", "point", "temperature", "stage", "created_at")
    list_filter = ("temperature", "stage", "source")
    search_fields = ("full_name", "email", "company", "event__name")
