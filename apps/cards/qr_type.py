"""Registers the "card" QR type: a dynamic code that opens a Qrumy Card."""

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.qr_management.types import DYNAMIC, QRType
from apps.qr_management.types import register as register_qr_type


class CardQRForm(forms.Form):
    card_token = forms.CharField(widget=forms.HiddenInput, disabled=True, required=False)
    card_name = forms.CharField(widget=forms.HiddenInput, disabled=True, required=False)


def _destination(payload: dict) -> str:
    return f"{settings.SITE_URL}/c/{payload['card_token']}?src=qr"


def register() -> None:
    register_qr_type(QRType("card", _("Qrumy Card"), "user", _("Open a digital business card"),
                            CardQRForm, (DYNAMIC,), destination=_destination, listed=False))
