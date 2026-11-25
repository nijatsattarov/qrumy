from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin, TabularInline

from apps.audit_logs.services import record

from .models import Invitation, Membership, Organization


class MembershipInline(TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user",)
    fields = ("user", "role", "created_at")
    readonly_fields = ("created_at",)


@admin.register(Organization)
class OrganizationAdmin(ModelAdmin):
    list_display = ("name", "slug", "owner", "kind", "status", "country", "created_at")
    list_filter = ("status", "kind", "industry", "country")
    search_fields = ("name", "slug", "owner__email")
    autocomplete_fields = ("owner", "parent")
    readonly_fields = ("created_at", "updated_at")
    inlines = [MembershipInline]
    actions = ["suspend", "activate"]

    @admin.action(description=_("Suspend selected organizations"))
    def suspend(self, request, queryset):
        for org in queryset.filter(status=Organization.Status.ACTIVE):
            org.status = Organization.Status.SUSPENDED
            org.save(update_fields=["status", "updated_at"])
            record("admin.organization.suspended", actor=request.user, organization=org,
                   target=org, request=request)
        messages.success(request, _("Selected organizations were suspended."))

    @admin.action(description=_("Activate selected organizations"))
    def activate(self, request, queryset):
        for org in queryset.filter(status=Organization.Status.SUSPENDED):
            org.status = Organization.Status.ACTIVE
            org.save(update_fields=["status", "updated_at"])
            record("admin.organization.activated", actor=request.user, organization=org,
                   target=org, request=request)
        messages.success(request, _("Selected organizations were activated."))


@admin.register(Invitation)
class InvitationAdmin(ModelAdmin):
    list_display = ("email", "organization", "role", "created_at", "expires_at", "accepted_at",
                    "revoked_at")
    list_filter = ("role",)
    search_fields = ("email", "organization__name")
    readonly_fields = [f.name for f in Invitation._meta.fields]

    def has_add_permission(self, request):
        return False
