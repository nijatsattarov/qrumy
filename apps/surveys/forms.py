import re

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.qr_management.types import SafeURLField

from .models import Response, Survey

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class SurveyCreateForm(forms.Form):
    title = forms.CharField(label=_("Survey title"), max_length=150,
                            widget=forms.TextInput(attrs={"placeholder": _("Guest feedback")}))
    language = forms.ChoiceField(label=_("Survey language"), choices=Survey._meta.get_field(
        "language").choices)


class SurveySettingsForm(forms.ModelForm):
    redirect_url = SafeURLField(label=_("Redirect after submit"), required=False,
                                help_text=_("Optional. Send people to your website after they "
                                            "answer instead of showing the thank-you message."))

    class Meta:
        model = Survey
        fields = ["title", "description", "language", "accent_color", "logo", "thank_you_title",
                  "thank_you_message", "redirect_url", "contact_mode", "consent_text",
                  "closes_at", "response_limit"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "thank_you_message": forms.Textarea(attrs={"rows": 3}),
            "accent_color": forms.TextInput(attrs={"type": "color"}),
            "closes_at": forms.DateTimeInput(attrs={"type": "datetime-local"},
                                             format="%Y-%m-%dT%H:%M"),
            "logo": forms.ClearableFileInput(attrs={"accept": "image/png,image/jpeg,image/webp"}),
        }

    def clean_accent_color(self):
        value = self.cleaned_data["accent_color"]
        if not HEX.match(value or ""):
            raise forms.ValidationError(_("Choose a valid color."))
        return value

    def clean_logo(self):
        from apps.organizations.forms import validate_logo

        logo = self.cleaned_data.get("logo")
        if logo and hasattr(logo, "content_type"):
            validate_logo(logo)
        return logo

    def clean(self):
        data = super().clean()
        if data.get("contact_mode") != Survey.Contact.OFF and not data.get("consent_text"):
            self.add_error("consent_text", _("Explain how you will use the contact details."))
        return data


class QuestionForm(forms.Form):
    label = forms.CharField(label=_("Question"), max_length=300)
    help_text = forms.CharField(label=_("Help text"), max_length=300, required=False)
    required = forms.BooleanField(label=_("Required"), required=False)
    options = forms.CharField(label=_("Options"), required=False,
                              widget=forms.Textarea(attrs={"rows": 4}),
                              help_text=_("One option per line."))
    low_label = forms.CharField(label=_("Label for the lowest value"), max_length=40,
                                required=False)
    high_label = forms.CharField(label=_("Label for the highest value"), max_length=40,
                                 required=False)


class PublicSurveyForm(forms.Form):
    """The respondent's form, built from the survey's questions."""

    started = forms.CharField(widget=forms.HiddenInput)
    website = forms.CharField(required=False, label=_("Leave this field empty"))  # honeypot

    def __init__(self, *args, survey: Survey, questions, **kwargs):
        super().__init__(*args, **kwargs)
        self.survey = survey
        self.questions = list(questions)
        for q in self.questions:
            self.fields[f"q_{q.pk}"] = q.type_def.field(q)
        if survey.contact_mode != Survey.Contact.OFF:
            required = survey.contact_mode == Survey.Contact.REQUIRED
            self.fields["contact_name"] = forms.CharField(label=_("Your name"), max_length=120,
                                                          required=required)
            self.fields["contact_email"] = forms.EmailField(label=_("Your email"),
                                                            required=required)
            self.fields["consent"] = forms.BooleanField(label=survey.consent_text,
                                                        required=required)

    def question_fields(self):
        return [(q, self[f"q_{q.pk}"]) for q in self.questions]

    def clean(self):
        data = super().clean()
        if data.get("website"):
            raise forms.ValidationError("spam")
        if (data.get("contact_email") or data.get("contact_name")) and not data.get("consent"):
            self.add_error("consent", _("Please confirm before we store your contact details."))
        return data

    def answers(self) -> dict:
        return {q: self.cleaned_data.get(f"q_{q.pk}") for q in self.questions}


class ResponseFilterForm(forms.Form):
    q = forms.CharField(required=False)
    status = forms.ChoiceField(required=False, choices=[("", _("All statuses")),
                                                        *Response.Status.choices])
    score = forms.ChoiceField(required=False, choices=[
        ("", _("All scores")), ("promoters", _("NPS promoters (9–10)")),
        ("passives", _("NPS passives (7–8)")), ("detractors", _("NPS detractors (0–6)")),
        ("unsatisfied", _("CSAT unsatisfied (1–2)"))])
    assigned = forms.CharField(required=False)
    tag = forms.CharField(required=False)
    days = forms.TypedChoiceField(required=False, coerce=int, empty_value=None, choices=[
        ("", _("All time")), (7, _("7 days")), (30, _("30 days")), (90, _("90 days"))])
