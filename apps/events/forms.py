from django import forms
from django.utils.translation import gettext_lazy as _

from apps.organizations.models import Membership
from apps.qr_management.types import PhoneField, SafeURLField

from .models import CapturePoint, Event, Lead

DEFAULT_CONSENT = _("I agree that %(org)s stores my contact details and contacts me about "
                    "this enquiry.")


class EventForm(forms.ModelForm):
    thank_you_url = SafeURLField(label=_("Link after submitting"), required=False,
                                 help_text=_("Optional, e.g. your catalogue or website."))

    class Meta:
        model = Event
        fields = ["name", "starts_on", "ends_on", "venue", "language", "welcome_text",
                  "interests", "ask_phone", "ask_company", "ask_message", "consent_text",
                  "thank_you_text", "thank_you_url", "is_active"]
        widgets = {"starts_on": forms.DateInput(attrs={"type": "date"}),
                   "ends_on": forms.DateInput(attrs={"type": "date"}),
                   "interests": forms.Textarea(attrs={"rows": 4}),
                   "name": forms.TextInput(
                       attrs={"placeholder": _("e.g. Caspian Build Expo 2026")})}

    def clean(self):
        data = super().clean()
        if data.get("starts_on") and data.get("ends_on") and data["ends_on"] < data["starts_on"]:
            self.add_error("ends_on", _("The last day must be after the first day."))
        return data


class PointForm(forms.ModelForm):
    class Meta:
        model = CapturePoint
        fields = ["name", "company_name", "contact_email"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": _("e.g. Stand A12")})}


class PublicLeadForm(forms.Form):
    full_name = forms.CharField(label=_("Your name"), max_length=120)
    email = forms.EmailField(label=_("Email"), required=False)
    phone = PhoneField(label=_("Phone"), max_length=32, required=False)
    company = forms.CharField(label=_("Company"), max_length=160, required=False)
    job_title = forms.CharField(label=_("Job title"), max_length=120, required=False)
    interests = forms.MultipleChoiceField(label=_("I am interested in"), required=False,
                                          widget=forms.CheckboxSelectMultiple)
    message = forms.CharField(label=_("Message"), max_length=1000, required=False,
                              widget=forms.Textarea(attrs={"rows": 3}))
    consent = forms.BooleanField(required=True)
    website = forms.CharField(required=False, label=_("Leave this field empty"))  # honeypot
    started = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, event, org_name: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.consent_label = event.consent_text or str(DEFAULT_CONSENT % {"org": org_name})
        self.fields["consent"].label = self.consent_label
        self.fields["consent"].error_messages["required"] = _(
            "Please confirm so we can store your details.")
        if not event.ask_phone:
            del self.fields["phone"]
        if not event.ask_company:
            del self.fields["company"], self.fields["job_title"]
        if not event.ask_message:
            del self.fields["message"]
        choices = event.interest_list
        if choices:
            self.fields["interests"].choices = [(c, c) for c in choices]
        else:
            del self.fields["interests"]

    def clean(self):
        data = super().clean()
        if data.get("website"):
            raise forms.ValidationError(_("Something went wrong. Please try again."))
        if not data.get("email") and not data.get("phone"):
            raise forms.ValidationError(_("Enter an email or a phone number so we can reach "
                                          "you."))
        return data

    def lead_data(self) -> dict:
        d = self.cleaned_data
        return {k: (d.get(k) or ([] if k == "interests" else "")) for k in
                ("full_name", "email", "phone", "company", "job_title", "interests", "message")}


class StaffLeadForm(forms.ModelForm):
    phone = PhoneField(label=_("Phone"), max_length=32, required=False)
    interests = forms.MultipleChoiceField(label=_("Interests"), required=False,
                                          widget=forms.CheckboxSelectMultiple)
    consent = forms.BooleanField(label=_("The person agreed to be contacted"), required=True)

    class Meta:
        model = Lead
        fields = ["full_name", "email", "phone", "company", "job_title", "point", "temperature",
                  "interests", "message", "consent"]
        widgets = {"message": forms.Textarea(attrs={"rows": 3}),
                   "temperature": forms.RadioSelect}

    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["point"].queryset = CapturePoint.objects.for_org(
            event.organization).filter(event=event)
        self.fields["point"].required = False
        if event.interest_list:
            self.fields["interests"].choices = [(c, c) for c in event.interest_list]
        else:
            del self.fields["interests"]

    def clean(self):
        data = super().clean()
        if not data.get("email") and not data.get("phone"):
            raise forms.ValidationError(_("Enter an email or a phone number."))
        return data


class LeadUpdateForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ["temperature", "stage", "assigned_to"]

    def __init__(self, *args, organization, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth import get_user_model

        ids = Membership.objects.filter(organization=organization).values_list("user_id",
                                                                               flat=True)
        self.fields["assigned_to"].queryset = get_user_model().objects.filter(pk__in=ids)
        self.fields["assigned_to"].required = False
        self.fields["assigned_to"].empty_label = _("Nobody")


class FollowUpForm(forms.Form):
    title = forms.CharField(label=_("Task"), max_length=160,
                            widget=forms.TextInput(
                                attrs={"placeholder": _("e.g. Send price list")}))
    due_on = forms.DateField(label=_("Due"), required=False,
                             widget=forms.DateInput(attrs={"type": "date"}))
