import re

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.qr_management.types import PhoneField, SafeURLField, SocialLinksMixin

from .models import Card

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
PRESET_COLORS = ["#101B3A", "#2F6BFF", "#12805C", "#D92D20", "#6941C6", "#E8590C", "#DD2590",
                 "#111111", "#0E7490", "#B54708"]


class StartForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ["kind", "template", "name"]
        widgets = {"kind": forms.RadioSelect, "template": forms.RadioSelect}
        labels = {"name": _("Full name or company name")}


class DesignForm(forms.ModelForm):
    class Meta:
        model = Card
        fields = ["kind", "template", "accent_color"]
        widgets = {"kind": forms.RadioSelect, "template": forms.RadioSelect,
                   "accent_color": forms.TextInput(attrs={"type": "color"})}

    def clean_accent_color(self):
        color = (self.cleaned_data.get("accent_color") or "").strip()
        if not HEX.match(color):
            raise forms.ValidationError(_("Choose a valid color."))
        return color.upper()


class ProfileForm(forms.ModelForm):
    remove_photo = forms.BooleanField(label=_("Remove photo"), required=False)
    remove_cover = forms.BooleanField(label=_("Remove cover"), required=False)

    class Meta:
        model = Card
        fields = ["photo", "cover", "name", "headline", "company", "about"]
        widgets = {
            "photo": forms.ClearableFileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}),
            "cover": forms.ClearableFileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}),
            "about": forms.Textarea(attrs={"rows": 5}),
            "headline": forms.TextInput(attrs={"placeholder": _("e.g. Sales manager")}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        company = self.instance.kind == Card.Kind.COMPANY
        self.fields["name"].label = _("Company name") if company else _("Full name")
        self.fields["headline"].label = _("Slogan") if company else _("Job title")
        self.fields["about"].label = _("About the company") if company else _("About me")
        if company:
            del self.fields["company"]
            self.fields["photo"].label = _("Logo")
            self.fields["headline"].widget.attrs["placeholder"] = _(
                "e.g. Coffee & bakery since 2015")

    def save(self, commit=True):
        card = super().save(commit=False)
        for field in ("photo", "cover"):
            if self.cleaned_data.get(f"remove_{field}") and getattr(card, field):
                getattr(card, field).delete(save=False)
                setattr(card, field, "")
        if commit:
            card.save()
        return card


class ContactForm(forms.ModelForm):
    phone = PhoneField(label=_("Phone"), max_length=32, required=False)
    phone_2 = PhoneField(label=_("Second phone"), max_length=32, required=False)
    website = SafeURLField(label=_("Website"), required=False)
    map_url = SafeURLField(label=_("Map link"), required=False,
                           help_text=_("Optional. Paste a Google Maps link to your place; "
                                       "without it the address opens in Google Maps."))

    class Meta:
        model = Card
        fields = ["phone", "phone_2", "email", "website", "address", "map_url"]
        widgets = {"email": forms.EmailInput(attrs={"placeholder": "name@company.com"}),
                   "address": forms.TextInput(attrs={"placeholder": _("e.g. Baku, Nizami st. 10")})}


class SocialForm(SocialLinksMixin, forms.Form):
    max_links = 12
    links_required = False

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        if instance is not None and "initial" not in kwargs:
            kwargs["initial"] = self.link_initial(instance.links or [])
        super().__init__(*args, **kwargs)
        self.add_link_fields()

    def clean(self):
        data = super().clean()
        data["links"] = self.clean_links_rows(data)
        return data

    @property
    def changed_data(self):
        return ["links"]

    def save(self):
        self.instance.links = self.cleaned_data["links"]
        self.instance.save(update_fields=["links", "updated_at"])
        return self.instance


class PhotoForm(forms.Form):
    image = forms.ImageField(label=_("Photo"), widget=forms.ClearableFileInput(
        attrs={"accept": "image/png,image/jpeg,image/webp"}))
    caption = forms.CharField(label=_("Caption"), max_length=120, required=False)

    def clean_image(self):
        from .models import validate_image

        image = self.cleaned_data["image"]
        validate_image(image)
        return image
