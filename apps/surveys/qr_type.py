"""Registers the "survey" QR type: a dynamic code that opens a survey (source=qr)."""

from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apps.qr_management.types import DYNAMIC, QRType
from apps.qr_management.types import register as register_qr_type


class SurveyQRForm(forms.Form):
    # The linked survey never changes from the QR editor (disabled → POST is ignored).
    survey_token = forms.CharField(widget=forms.HiddenInput, disabled=True, required=False)
    survey_title = forms.CharField(widget=forms.HiddenInput, disabled=True, required=False)


def _destination(payload: dict) -> str:
    return f"{settings.SITE_URL}/s/{payload['survey_token']}?src=qr"


def register() -> None:
    register_qr_type(QRType("survey", _("Survey"), "message", _("Open a feedback survey"),
                            SurveyQRForm, (DYNAMIC,), destination=_destination, listed=False))
