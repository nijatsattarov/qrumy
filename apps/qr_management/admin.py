from django import forms
from django.contrib import admin, messages
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from . import services
from .models import BlockedDomain, Folder, QRCode


class SuspendForm(forms.Form):
    reason = forms.CharField(label=_("Reason"), max_length=255)


@admin.register(QRCode)
class QRCodeAdmin(ModelAdmin):
    list_display = ("name", "organization", "qr_type", "mode", "short_code", "status",
                    "total_scans", "created_at", "deleted_at")
    list_filter = ("status", "mode", "qr_type")
    search_fields = ("name", "short_code", "organization__name", "payload")
    list_select_related = ("organization",)
    readonly_fields = [f.name for f in QRCode._meta.fields]
    actions = ["suspend", "unsuspend"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description=_("Suspend selected QR codes (abuse)"))
    def suspend(self, request, queryset):
        if "apply" in request.POST:
            form = SuspendForm(request.POST)
            if form.is_valid():
                for qr in queryset:
                    services.suspend_qr(qr=qr, actor=request.user,
                                        reason=form.cleaned_data["reason"], request=request)
                messages.success(request, _("Selected QR codes were suspended."))
                return None
        else:
            form = SuspendForm()
        return render(request, "admin/qr_management/suspend.html", {
            **self.admin_site.each_context(request), "form": form, "codes": queryset,
            "opts": self.model._meta, "title": _("Suspend QR codes")})

    @admin.action(description=_("Lift suspension (set active)"))
    def unsuspend(self, request, queryset):
        from apps.audit_logs.services import record

        from .redirect_cache import invalidate

        for qr in queryset.filter(status=QRCode.Status.SUSPENDED):
            qr.status, qr.suspended_reason = QRCode.Status.ACTIVE, ""
            qr.save(update_fields=["status", "suspended_reason", "updated_at"])
            invalidate(qr)
            record("admin.qr.unsuspended", actor=request.user, organization=qr.organization,
                   target=qr, request=request)
        messages.success(request, _("Suspension lifted."))


@admin.register(BlockedDomain)
class BlockedDomainAdmin(ModelAdmin):
    list_display = ("domain", "reason", "created_at")
    search_fields = ("domain",)


@admin.register(Folder)
class FolderAdmin(ModelAdmin):
    list_display = ("name", "organization")
    search_fields = ("name", "organization__name")
