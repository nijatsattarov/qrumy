"""Registers the "event_lead" QR type: opens the lead form of a collection point."""

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.qr_management.types import DYNAMIC, QRType
from apps.qr_management.types import register as register_qr_type


class EventLeadQRForm(forms.Form):
    capture_token = forms.CharField(widget=forms.HiddenInput, disabled=True, required=False)
    point_name = forms.CharField(widget=forms.HiddenInput, disabled=True, required=False)


def _destination(payload: dict) -> str:
    return f"{settings.SITE_URL}/e/{payload['capture_token']}?src=qr"


def register() -> None:
    register_qr_type(QRType("event_lead", _("Event lead form"), "calendar",
                            _("Collect visitor contacts at an event"), EventLeadQRForm,
                            (DYNAMIC,), destination=_destination, listed=False))
