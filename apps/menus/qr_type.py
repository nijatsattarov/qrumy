"""Registers the "digital_menu" QR type: a dynamic code that opens a Digital Menu."""

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.qr_management.types import DYNAMIC, TYPES, QRType
from apps.qr_management.types import register as register_qr_type


class MenuQRForm(forms.Form):
    menu_token = forms.CharField(widget=forms.HiddenInput, disabled=True, required=False)
    menu_name = forms.CharField(widget=forms.HiddenInput, disabled=True, required=False)


def _destination(payload: dict) -> str:
    return f"{settings.SITE_URL}/m/{payload['menu_token']}?src=qr"


def register() -> None:
    register_qr_type(QRType("digital_menu", _("Digital Menu"), "menu-book",
                            _("Open an interactive menu"), MenuQRForm, (DYNAMIC,),
                            destination=_destination, listed=False))
    # The old PDF/image menu is replaced by the Digital Menu in the QR type picker.
    # Codes created with it keep working.
    if "menu" in TYPES:
        from dataclasses import replace

        TYPES["menu"] = replace(TYPES["menu"], listed=False)
