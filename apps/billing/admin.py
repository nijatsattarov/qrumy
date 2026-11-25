from django import forms
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin

from .gateways import ManualGateway
from .models import PlanAssignment


class PlanAssignmentForm(forms.ModelForm):
    reason = forms.CharField(label=_("Reason"), max_length=255, required=True)

    class Meta:
        model = PlanAssignment
        fields = ["organization", "plan", "interval"]


@admin.register(PlanAssignment)
class PlanAssignmentAdmin(ModelAdmin):
    form = PlanAssignmentForm
    list_display = ("organization", "plan", "status", "gateway", "started_at")
    list_filter = ("gateway", "status")
    search_fields = ("organization__name",)
    autocomplete_fields = ("organization",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(gateway=ManualGateway.key)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        sub = ManualGateway().assign_plan(
            organization=form.cleaned_data["organization"], plan=form.cleaned_data["plan"],
            interval=form.cleaned_data["interval"], actor=request.user,
            reason=form.cleaned_data["reason"], request=request)
        obj.pk = obj.id = sub.pk
        obj._state.adding = False
