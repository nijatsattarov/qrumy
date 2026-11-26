"""Public contact page (/contact/) with a message form. Content is edited in the admin."""

import time

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core import signing
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit

from apps.qr_management.types import PhoneField

from .models import ContactMessage, ContactPage

SALT = "qrumy.contact"


class ContactForm(forms.ModelForm):
    phone = PhoneField(label=gettext_lazy("Phone"), max_length=32, required=False)
    website = forms.CharField(required=False, label=gettext_lazy("Leave this field empty"))
    started = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "phone", "company", "topic", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}
        labels = {"name": gettext_lazy("Your name"), "email": gettext_lazy("Your email")}

    def clean(self):
        data = super().clean()
        if data.get("website"):
            raise forms.ValidationError(_("Something went wrong. Please try again."))
        try:
            started = signing.loads(data.get("started", ""), salt=SALT, max_age=86400)
        except signing.BadSignature as exc:
            raise forms.ValidationError(_("This form expired. Please try again.")) from exc
        if time.time() - started.get("t", 0) < 2:  # filled faster than a person can
            raise forms.ValidationError(_("Something went wrong. Please try again."))
        return data


def page_for(language: str) -> ContactPage | None:
    return (ContactPage.objects.filter(language=language).first()
            or ContactPage.objects.filter(language=settings.LANGUAGE_CODE).first())


@never_cache
@ratelimit(key="ip", rate="5/m", method="POST", block=True)
@ratelimit(key="ip", rate="20/h", method="POST", block=True)
def contact(request):
    page = page_for(translation.get_language())
    if page is None:
        raise Http404
    form = None
    if page.form_enabled:
        form = ContactForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            msg = form.save(commit=False)
            msg.language = translation.get_language() or ""
            msg.save()
            if page.notify_email:
                from apps.notifications.services import send_templated_email

                send_templated_email(to=page.notify_email,
                                     template="marketing/email/contact_message",
                                     context={"msg": msg}, language=settings.LANGUAGE_CODE)
            messages.success(request, page.success_message or _(
                "Thank you! Your message was sent. We will reply to you by email."))
            return redirect("contact")
        form.initial["started"] = signing.dumps({"t": time.time()}, salt=SALT)
        if not form.is_bound:
            form.initial.setdefault("topic", request.GET.get("topic", "general"))
    return render(request, "marketing/contact.html", {"page": page, "form": form})
