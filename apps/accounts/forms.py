from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from .models import User


class SignupExtraForm(forms.Form):
    """Extra fields collected by allauth's signup form."""

    full_name = forms.CharField(label=_("Full name"), max_length=150,
                                widget=forms.TextInput(attrs={"autocomplete": "name"}))

    field_order = ["full_name", "email", "password1", "password2", "accept_terms"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.urls import reverse
        from django.utils.html import format_html

        from .legal import terms_required

        if terms_required():
            self.fields["accept_terms"] = forms.BooleanField(
                required=True,
                label=format_html(
                    _('I agree to the <a href="{}" target="_blank">Terms of Service</a> and '
                      '<a href="{}" target="_blank">Privacy Policy</a>'),
                    reverse("terms"), reverse("privacy")))

    def signup(self, request, user):
        from .legal import LegalDocument, TermsAcceptance, current

        terms = current(LegalDocument.Kind.TERMS)
        if terms and self.cleaned_data.get("accept_terms"):
            privacy = current(LegalDocument.Kind.PRIVACY)
            TermsAcceptance.objects.create(user=user, terms_version=terms.version,
                                           privacy_version=privacy.version if privacy else "")
        user.full_name = self.cleaned_data["full_name"].strip()
        lang = getattr(request, "LANGUAGE_CODE", settings.LANGUAGE_CODE)
        if lang in dict(settings.LANGUAGES):
            user.language = lang
        user.save(update_fields=["full_name", "language"])


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["full_name", "language"]
        labels = {"full_name": _("Full name"), "language": _("Interface language")}
