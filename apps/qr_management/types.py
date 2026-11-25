"""QR content types.

Each type declares its payload form, which modes it supports and how it behaves:
* ``encode(payload)``       → text stored in a *static* QR symbol
* ``destination(payload)``  → redirect target for a *dynamic* code
* ``landing``               → dynamic code renders a hosted Qrumy page instead
* ``hosted_file``           → dynamic code serves an uploaded file (PDF / image)
New types are added by registering another QRType.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import quote, urlencode

from django import forms
from django.utils.translation import gettext_lazy as _
from segno import helpers

from .validators import validate_destination_url

STATIC, DYNAMIC = "static", "dynamic"


# ---------------------------------------------------------------- helpers
def _clean_phone(value: str) -> str:
    digits = re.sub(r"[^\d+]", "", value or "")
    if digits.count("+") > 1 or (digits and "+" in digits[1:]):
        raise forms.ValidationError(_("Enter a valid phone number."))
    if len(re.sub(r"\D", "", digits)) < 6:
        raise forms.ValidationError(_("Enter a valid phone number."))
    return digits


class SafeURLField(forms.URLField):
    def __init__(self, **kwargs):
        kwargs.setdefault("assume_scheme", "https")
        kwargs.setdefault("max_length", 2000)
        super().__init__(**kwargs)

    def clean(self, value):
        value = super().clean(value)
        return validate_destination_url(value) if value else value


class PhoneField(forms.CharField):
    def clean(self, value):
        value = super().clean(value)
        return _clean_phone(value) if value else value


# ---------------------------------------------------------------- payload forms
class URLForm(forms.Form):
    url = SafeURLField(label=_("Website URL"))


class TextForm(forms.Form):
    text = forms.CharField(label=_("Text"), max_length=1000,
                           widget=forms.Textarea(attrs={"rows": 4}))


class WifiForm(forms.Form):
    ssid = forms.CharField(label=_("Network name (SSID)"), max_length=64)
    security = forms.ChoiceField(label=_("Security"), choices=[
        ("WPA", "WPA/WPA2/WPA3"), ("WEP", "WEP"), ("nopass", _("No password"))])
    password = forms.CharField(label=_("Password"), max_length=64, required=False)
    hidden = forms.BooleanField(label=_("Hidden network"), required=False)

    def clean(self):
        data = super().clean()
        if data.get("security") != "nopass" and not data.get("password"):
            self.add_error("password", _("Enter the network password."))
        return data


class VCardForm(forms.Form):
    first_name = forms.CharField(label=_("First name"), max_length=60)
    last_name = forms.CharField(label=_("Last name"), max_length=60, required=False)
    organization = forms.CharField(label=_("Company"), max_length=100, required=False)
    title = forms.CharField(label=_("Job title"), max_length=100, required=False)
    phone = PhoneField(label=_("Phone"), max_length=32, required=False)
    email = forms.EmailField(label=_("Email"), required=False)
    website = SafeURLField(label=_("Website"), required=False)
    address = forms.CharField(label=_("Address"), max_length=200, required=False)
    note = forms.CharField(label=_("Note"), max_length=300, required=False,
                           widget=forms.Textarea(attrs={"rows": 2}))


class PhoneForm(forms.Form):
    phone = PhoneField(label=_("Phone number"), max_length=32)


class SMSForm(forms.Form):
    phone = PhoneField(label=_("Phone number"), max_length=32)
    message = forms.CharField(label=_("Message"), max_length=300, required=False,
                              widget=forms.Textarea(attrs={"rows": 3}))


class EmailForm(forms.Form):
    email = forms.EmailField(label=_("Email address"))
    subject = forms.CharField(label=_("Subject"), max_length=150, required=False)
    body = forms.CharField(label=_("Message"), max_length=1000, required=False,
                           widget=forms.Textarea(attrs={"rows": 3}))


class WhatsAppForm(forms.Form):
    phone = PhoneField(label=_("WhatsApp number (with country code)"), max_length=32)
    message = forms.CharField(label=_("Pre-filled message"), max_length=500, required=False,
                              widget=forms.Textarea(attrs={"rows": 3}))


class LocationForm(forms.Form):
    latitude = forms.DecimalField(label=_("Latitude"), min_value=-90, max_value=90,
                                  max_digits=9, decimal_places=6)
    longitude = forms.DecimalField(label=_("Longitude"), min_value=-180, max_value=180,
                                   max_digits=10, decimal_places=6)
    label = forms.CharField(label=_("Place name"), max_length=120, required=False)


class LinksForm(forms.Form):
    title = forms.CharField(label=_("Page title"), max_length=80)
    description = forms.CharField(label=_("Description"), max_length=300, required=False,
                                  widget=forms.Textarea(attrs={"rows": 2}))
    links = forms.CharField(
        label=_("Links"), widget=forms.Textarea(attrs={"rows": 5}),
        help_text=_("One per line: Label | https://example.com (up to 12 links)."))

    def clean_links(self):
        items = []
        for n, line in enumerate(self.cleaned_data["links"].splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            label, sep, url = line.partition("|")
            if not sep:
                label, url = "", label
            label, url = label.strip()[:60], url.strip()
            try:
                url = SafeURLField().clean(url)
            except forms.ValidationError as exc:
                raise forms.ValidationError(
                    _("Line %(n)s: %(error)s") % {"n": n, "error": exc.messages[0]}) from exc
            items.append({"label": label or url, "url": url})
        if not items:
            raise forms.ValidationError(_("Add at least one link."))
        if len(items) > 12:
            raise forms.ValidationError(_("You can add up to 12 links."))
        return items

    @staticmethod
    def initial_from(payload):
        data = dict(payload)
        if isinstance(data.get("links"), list):
            data["links"] = "\n".join(f'{i["label"]} | {i["url"]}' for i in data["links"])
        return data


class AppForm(forms.Form):
    app_name = forms.CharField(label=_("App name"), max_length=80)
    ios_url = SafeURLField(label=_("App Store link"), required=False)
    android_url = SafeURLField(label=_("Google Play link"), required=False)
    fallback_url = SafeURLField(label=_("Link for other devices"), required=False)

    def clean(self):
        data = super().clean()
        if not any(data.get(k) for k in ("ios_url", "android_url", "fallback_url")):
            raise forms.ValidationError(_("Add at least one store link."))
        return data


class CouponForm(forms.Form):
    title = forms.CharField(label=_("Offer title"), max_length=80)
    description = forms.CharField(label=_("Description"), max_length=300, required=False,
                                  widget=forms.Textarea(attrs={"rows": 2}))
    code = forms.CharField(label=_("Coupon code"), max_length=40, required=False)
    valid_until = forms.DateField(label=_("Valid until"), required=False,
                                  widget=forms.DateInput(attrs={"type": "date"}))
    terms = forms.CharField(label=_("Terms"), max_length=500, required=False,
                            widget=forms.Textarea(attrs={"rows": 2}))
    button_label = forms.CharField(label=_("Button label"), max_length=40, required=False)
    button_url = SafeURLField(label=_("Button link"), required=False)


class FileForm(forms.Form):
    title = forms.CharField(label=_("Title"), max_length=120, required=False)
    file = forms.FileField(label=_("File"), required=False)


# ---------------------------------------------------------------- encoders
def _maps_url(p) -> str:
    return "https://www.google.com/maps/search/?" + urlencode(
        {"api": 1, "query": f'{p["latitude"]},{p["longitude"]}'})


def _wa_url(p) -> str:
    url = "https://wa.me/" + re.sub(r"\D", "", p["phone"])
    return url + ("?text=" + quote(p["message"]) if p.get("message") else "")


def _vcard(p) -> str:
    name = f'{p.get("last_name", "")};{p.get("first_name", "")}'
    display = " ".join(x for x in (p.get("first_name"), p.get("last_name")) if x)
    return helpers.make_vcard_data(
        name, display, email=p.get("email") or None, phone=p.get("phone") or None,
        url=p.get("website") or None, org=p.get("organization") or None,
        title=p.get("title") or None, street=p.get("address") or None,
        memo=p.get("note") or None)


def _sms(p) -> str:
    return f'SMSTO:{p["phone"]}:{p.get("message", "")}'


def _email(p) -> str:
    return helpers.make_make_email_data(p["email"], subject=p.get("subject") or None,
                                        body=p.get("body") or None)


def _wifi(p) -> str:
    return helpers.make_wifi_data(ssid=p["ssid"], password=p.get("password") or None,
                                  security=p["security"], hidden=bool(p.get("hidden")))


# ---------------------------------------------------------------- registry
@dataclass(frozen=True)
class QRType:
    key: str
    label: object
    icon: str
    description: object
    form: type[forms.Form]
    modes: tuple[str, ...]
    encode: Callable[[dict], str] | None = None
    destination: Callable[[dict], str] | None = None
    landing: bool = False
    hosted_file: tuple[str, ...] = ()  # allowed MIME types
    listed: bool = True  # False: created from another module (e.g. a survey), not the QR picker

    @property
    def default_mode(self) -> str:
        return DYNAMIC if DYNAMIC in self.modes else STATIC

    def initial(self, payload: dict) -> dict:
        fn = getattr(self.form, "initial_from", None)
        return fn(payload) if fn else dict(payload)


TYPES: dict[str, QRType] = {}


def register(t: QRType) -> None:
    TYPES[t.key] = t


def get_type(key: str) -> QRType:
    return TYPES[key]


register(QRType("url", _("Website"), "globe", _("Open any web page"), URLForm,
                (STATIC, DYNAMIC), encode=lambda p: p["url"], destination=lambda p: p["url"]))
register(QRType("links", _("Multi-link & social"), "share",
                _("A mobile page with several links"), LinksForm, (DYNAMIC,), landing=True))
register(QRType("pdf", _("PDF"), "file", _("Share a PDF document"), FileForm, (DYNAMIC,),
                hosted_file=("application/pdf",)))
register(QRType("menu", _("Menu"), "menu-book", _("Restaurant menu as PDF or image"),
                FileForm, (DYNAMIC,),
                hosted_file=("application/pdf", "image/png", "image/jpeg", "image/webp")))
register(QRType("image", _("Image"), "image", _("Show an image"), FileForm, (DYNAMIC,),
                hosted_file=("image/png", "image/jpeg", "image/webp")))
register(QRType("vcard", _("Contact card"), "user", _("Save contact details (vCard)"),
                VCardForm, (DYNAMIC, STATIC), encode=_vcard, landing=True))
register(QRType("whatsapp", _("WhatsApp"), "message", _("Start a WhatsApp chat"),
                WhatsAppForm, (DYNAMIC, STATIC), encode=_wa_url, destination=_wa_url))
register(QRType("location", _("Location"), "pin", _("Open a place on the map"), LocationForm,
                (DYNAMIC, STATIC), encode=_maps_url, destination=_maps_url))
register(QRType("app", _("App download"), "phone-device", _("Send people to the right app store"),
                AppForm, (DYNAMIC,)))
register(QRType("coupon", _("Coupon"), "ticket", _("Show a discount or offer"), CouponForm,
                (DYNAMIC,), landing=True))
register(QRType("text", _("Text"), "text", _("Show a short text"), TextForm,
                (STATIC, DYNAMIC), encode=lambda p: p["text"], landing=True))
register(QRType("wifi", _("Wi-Fi"), "wifi", _("Join a Wi-Fi network"), WifiForm, (STATIC,),
                encode=_wifi))
register(QRType("phone", _("Phone call"), "phone", _("Call a number"), PhoneForm, (STATIC,),
                encode=lambda p: f'tel:{p["phone"]}'))
register(QRType("sms", _("SMS"), "sms", _("Send a text message"), SMSForm, (STATIC,),
                encode=_sms))
register(QRType("email", _("Email"), "mail", _("Write an email"), EmailForm, (STATIC,),
                encode=_email))


def listed_types() -> list[QRType]:
    return [t for t in TYPES.values() if t.listed]


def payload_from_form(form: forms.Form) -> dict:
    """JSON-safe payload (dates/decimals → strings; uploaded files excluded)."""
    out = {}
    for key, value in form.cleaned_data.items():
        if key == "file" or value in (None, ""):
            continue
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        elif type(value).__name__ == "Decimal":
            value = str(value)
        out[key] = value
    return out
