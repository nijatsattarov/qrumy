from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(ModelAdmin):
    list_display = ("created_at", "action", "actor_email", "organization", "target_repr",
                    "is_staff_action")
    list_filter = ("is_staff_action", "action")
    search_fields = ("action", "actor_email", "target_repr", "organization__name")
    date_hierarchy = "created_at"
    list_select_related = ("organization",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
