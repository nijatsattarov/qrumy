from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from .models import User


class SignupExtraForm(forms.Form):
    """Extra fields collected by allauth's signup form."""

    full_name = forms.CharField(label=_("Full name"), max_length=150,
                                widget=forms.TextInput(attrs={"autocomplete": "name"}))

    field_order = ["full_name", "email", "password1", "password2"]

    def signup(self, request, user):
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
