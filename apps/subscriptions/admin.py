from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import FeatureOverride, Plan, PlanFeature, Subscription


class PlanFeatureInline(TabularInline):
    model = PlanFeature
    extra = 0


@admin.register(Plan)
class PlanAdmin(ModelAdmin):
    list_display = ("name", "key", "price_monthly_cents", "price_yearly_cents", "is_public",
                    "is_beta", "is_active", "sort_order")
    list_editable = ("is_public", "is_active", "sort_order")
    inlines = [PlanFeatureInline]


@admin.register(Subscription)
class SubscriptionAdmin(ModelAdmin):
    list_display = ("organization", "plan", "status", "interval", "gateway", "started_at",
                    "ended_at")
    list_filter = ("status", "plan", "gateway")
    search_fields = ("organization__name",)
    readonly_fields = [f.name for f in Subscription._meta.fields]

    def has_add_permission(self, request):
        return False  # use Billing → Plan assignments (audited)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FeatureOverride)
class FeatureOverrideAdmin(ModelAdmin):
    list_display = ("organization", "feature_key", "enabled", "limit_value", "expires_at",
                    "reason")
    search_fields = ("organization__name", "feature_key")
    autocomplete_fields = ("organization",)
