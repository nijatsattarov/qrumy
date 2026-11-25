"""Registers the "asset" QR type: a dynamic code that opens an asset's QR profile."""

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.qr_management.types import DYNAMIC, QRType
from apps.qr_management.types import register as register_qr_type


class AssetQRForm(forms.Form):
    asset_token = forms.CharField(widget=forms.HiddenInput, disabled=True, required=False)
    asset_name = forms.CharField(widget=forms.HiddenInput, disabled=True, required=False)
    asset_code = forms.CharField(widget=forms.HiddenInput, disabled=True, required=False)


def _destination(payload: dict) -> str:
    return f"{settings.SITE_URL}/a/{payload['asset_token']}?src=qr"


def register() -> None:
    register_qr_type(QRType("asset", _("Asset profile"), "box", _("Open an asset's QR profile"),
                            AssetQRForm, (DYNAMIC,), destination=_destination, listed=False))
