from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from . import locations as loc_helpers
from .models import Asset, AssetCategory, FaultReport, Location, MaintenanceRecord


def _members(organization):
    return get_user_model().objects.filter(
        memberships__organization=organization).order_by("full_name", "email")


def parse_custom_fields(text: str) -> dict:
    out = {}
    for line in (text or "").splitlines()[:30]:
        key, sep, value = line.partition(":")
        if sep and key.strip():
            out[key.strip()[:60]] = value.strip()[:200]
    return out


class AssetForm(forms.ModelForm):
    asset_code = forms.CharField(label=_("Asset ID"), max_length=40, required=False,
                                 help_text=_("Leave empty to generate one (AST-00001)."))
    location = forms.TypedChoiceField(label=_("Location"), required=False, coerce=int,
                                      empty_value=None)
    custom_fields_text = forms.CharField(
        label=_("Custom fields"), required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text=_("One per line, e.g. “Voltage: 220 V”."))

    class Meta:
        model = Asset
        fields = ["name", "asset_code", "category", "status", "brand", "model_name",
                  "serial_number", "description", "instructions", "location", "department",
                  "responsible", "purchase_date", "warranty_expires_at", "purchase_price",
                  "currency", "supplier", "public_visibility"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "instructions": forms.Textarea(attrs={"rows": 3}),
            "purchase_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "warranty_expires_at": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.fields["category"].queryset = AssetCategory.objects.for_org(organization)
        self.fields["category"].empty_label = _("No category")
        self.fields["responsible"].queryset = _members(organization)
        self.fields["responsible"].empty_label = _("Nobody")
        self.location_objs = {pk: loc for pk, _l, loc in
                              loc_helpers.ordered_choices(organization)}
        self.fields["location"].choices = [("", _("No location"))] + [
            (pk, label) for pk, label, _loc in loc_helpers.ordered_choices(organization)]
        if self.instance.pk:
            self.initial["location"] = self.instance.location_id
            self.initial["custom_fields_text"] = "\n".join(
                f"{k}: {v}" for k, v in (self.instance.custom_fields or {}).items())

    def clean_location(self):
        pk = self.cleaned_data.get("location")
        return self.location_objs.get(pk) if pk else None

    def clean_asset_code(self):
        from . import services

        code = (self.cleaned_data.get("asset_code") or "").strip()
        if code and services.code_taken(self.organization, code, exclude_pk=self.instance.pk):
            raise forms.ValidationError(_("Another asset already uses this ID."))
        return code

    def clean(self):
        data = super().clean()
        data["custom_fields"] = parse_custom_fields(data.get("custom_fields_text", ""))
        return data

    def save(self, commit=True):
        self.instance.custom_fields = self.cleaned_data["custom_fields"]
        if not self.cleaned_data.get("asset_code") and self.instance.pk:
            self.instance.asset_code = Asset.objects.get(pk=self.instance.pk).asset_code
        return super().save(commit)

    def create_data(self) -> dict:
        data = {f: self.cleaned_data.get(f) for f in self.Meta.fields}
        data["custom_fields"] = self.cleaned_data["custom_fields"]
        return data


class LocationForm(forms.Form):
    name = forms.CharField(label=_("Name"), max_length=100)
    kind = forms.ChoiceField(label=_("Type"), choices=Location.Kind.choices)
    parent = forms.TypedChoiceField(label=_("Inside"), required=False, coerce=int,
                                    empty_value=None)

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.objs = {pk: loc for pk, _l, loc in loc_helpers.ordered_choices(organization)}
        self.fields["parent"].choices = [("", _("Top level"))] + [
            (pk, label) for pk, label, _loc in loc_helpers.ordered_choices(organization)]

    def clean_parent(self):
        pk = self.cleaned_data.get("parent")
        return self.objs.get(pk) if pk else None


class CategoryForm(forms.Form):
    name = forms.CharField(label=_("Category name"), max_length=80)


class PublicFaultForm(forms.Form):
    started = forms.CharField(widget=forms.HiddenInput)
    website = forms.CharField(required=False)  # honeypot
    category = forms.ChoiceField(label=_("What is the problem?"),
                                 choices=FaultReport.Category.choices, widget=forms.RadioSelect)
    description = forms.CharField(label=_("Describe the problem"), max_length=2000,
                                  widget=forms.Textarea(attrs={"rows": 4}))
    priority = forms.ChoiceField(label=_("How urgent is it?"),
                                 choices=FaultReport.Priority.choices,
                                 initial=FaultReport.Priority.NORMAL)
    photo = forms.FileField(label=_("Photo"), required=False, widget=forms.ClearableFileInput(
        attrs={"accept": "image/*", "capture": "environment"}))
    reporter_name = forms.CharField(label=_("Your name"), max_length=120, required=False)
    reporter_contact = forms.CharField(label=_("Phone or email"), max_length=120,
                                       required=False)

    def clean(self):
        data = super().clean()
        if data.get("website"):
            raise forms.ValidationError("spam")
        return data


class InternalFaultForm(forms.Form):
    category = forms.ChoiceField(label=_("Problem"), choices=FaultReport.Category.choices)
    priority = forms.ChoiceField(label=_("Priority"), choices=FaultReport.Priority.choices,
                                 initial=FaultReport.Priority.NORMAL)
    description = forms.CharField(label=_("Description"), max_length=2000,
                                  widget=forms.Textarea(attrs={"rows": 3}))


class MaintenanceForm(forms.ModelForm):
    class Meta:
        model = MaintenanceRecord
        fields = ["kind", "performed_on", "technician", "technician_name", "cost", "notes"]
        widgets = {"performed_on": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["technician"].queryset = _members(organization)
        self.fields["technician"].empty_label = _("Nobody from the team")


class DocumentForm(forms.Form):
    file = forms.FileField(label=_("Photo or PDF"))
