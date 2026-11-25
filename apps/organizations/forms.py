from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image

from .models import Organization
from .roles import ROLE_DESCRIPTIONS, assignable_roles

MAX_LOGO_BYTES = 2 * 1024 * 1024
ALLOWED_LOGO_FORMATS = {"PNG", "JPEG", "WEBP"}


def validate_logo(file) -> None:
    if file.size > MAX_LOGO_BYTES:
        raise ValidationError(_("The logo must be 2 MB or smaller."))
    try:
        file.seek(0)
        with Image.open(file) as img:
            fmt = img.format
            img.verify()
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(_("Upload a valid PNG, JPEG or WebP image.")) from exc
    finally:
        file.seek(0)
    if fmt not in ALLOWED_LOGO_FORMATS:
        raise ValidationError(_("Upload a valid PNG, JPEG or WebP image."))


class OrganizationCreateForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields = ["name", "industry", "country", "timezone"]


class OrganizationSettingsForm(forms.ModelForm):
    website = forms.URLField(label=_("website"), required=False, assume_scheme="https")

    class Meta:
        model = Organization
        fields = ["name", "logo", "website", "industry", "country", "timezone", "language",
                  "contact_email", "contact_phone"]
        widgets = {"logo": forms.ClearableFileInput(
            attrs={"accept": "image/png,image/jpeg,image/webp"})}

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo and hasattr(logo, "content_type"):  # newly uploaded
            validate_logo(logo)
        return logo


class InviteForm(forms.Form):
    email = forms.EmailField(label=_("Email"))
    role = forms.ChoiceField(label=_("Role"))

    def __init__(self, *args, actor_role: str, **kwargs):
        super().__init__(*args, **kwargs)
        roles = assignable_roles(actor_role)
        self.fields["role"].choices = [(r.value, r.label) for r in roles]
        self.fields["role"].initial = "member"
        self.role_help = {r.value: ROLE_DESCRIPTIONS[r] for r in roles}


class RoleForm(forms.Form):
    role = forms.ChoiceField(label=_("Role"))

    def __init__(self, *args, actor_role: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [(r.value, r.label) for r in assignable_roles(actor_role)]
