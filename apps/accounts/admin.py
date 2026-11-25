from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm

from apps.audit_logs.services import record

from .models import User


class QrumyUserCreationForm(AdminUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)


class QrumyUserChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(DjangoUserAdmin, ModelAdmin):
    form = QrumyUserChangeForm
    add_form = QrumyUserCreationForm
    change_password_form = AdminPasswordChangeForm
    ordering = ("-date_joined",)
    list_display = ("email", "full_name", "language", "is_active", "is_staff", "date_joined",
                    "last_login")
    list_filter = ("is_active", "is_staff", "language")
    search_fields = ("email", "full_name")
    readonly_fields = ("date_joined", "last_login")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Profile"), {"fields": ("full_name", "language")}),
        (_("Access"), {"fields": ("is_active", "is_staff", "is_superuser", "groups",
                                  "user_permissions")}),
        (_("Dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",),
                             "fields": ("email", "password1", "password2")}),)
    actions = ["suspend_users", "activate_users"]

    @admin.action(description=_("Suspend selected users"))
    def suspend_users(self, request, queryset):
        queryset = queryset.exclude(pk=request.user.pk)
        for user in queryset.filter(is_active=True):
            user.is_active = False
            user.save(update_fields=["is_active"])
            record("admin.user.suspended", actor=request.user, target=user, request=request)
        messages.success(request, _("Selected users were suspended."))

    @admin.action(description=_("Activate selected users"))
    def activate_users(self, request, queryset):
        for user in queryset.filter(is_active=False):
            user.is_active = True
            user.save(update_fields=["is_active"])
            record("admin.user.activated", actor=request.user, target=user, request=request)
        messages.success(request, _("Selected users were activated."))
