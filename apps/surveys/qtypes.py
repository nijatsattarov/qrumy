"""Survey question types.

Each type knows how to build its public form field, how to store a cleaned value
(text / number / list) and which statistics apply ("stats" kind).
"""

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.qr_management.types import PhoneField

MAX_OPTIONS = 30


@dataclass(frozen=True)
class QType:
    key: str
    label: object
    icon: str
    stats: str                       # choice | multi | scale | yesno | text | count
    has_options: bool = False
    scale: tuple[int, int] | None = None
    low_label: object = ""
    high_label: object = ""
    build: Callable | None = None    # (question, label) -> forms.Field

    def field(self, question) -> forms.Field:
        return self.build(self, question)

    def to_answer(self, value) -> dict:
        """Cleaned form value → Answer columns. Returns {} for empty answers."""
        if value in (None, "", []):
            return {}
        if self.stats == "multi":
            return {"value_json": list(value)}
        if self.stats in ("scale",):
            return {"value_number": Decimal(int(value))}
        if self.stats == "yesno":
            return {"value_number": Decimal(1 if value == "yes" else 0),
                    "value_text": str(value)}
        if hasattr(value, "isoformat"):
            return {"value_text": value.isoformat()}
        return {"value_text": str(value)}


def _choices(q):
    return [(o, o) for o in q.options]


def _scale_choices(t: QType):
    lo, hi = t.scale
    return [(str(i), str(i)) for i in range(lo, hi + 1)]


def _common(q):
    return {"label": q.label, "required": q.required, "help_text": q.help_text}


def _single(t, q):
    return forms.ChoiceField(choices=_choices(q), widget=forms.RadioSelect, **_common(q))


def _multi(t, q):
    return forms.MultipleChoiceField(choices=_choices(q), widget=forms.CheckboxSelectMultiple,
                                     **_common(q))


def _dropdown(t, q):
    return forms.ChoiceField(choices=[("", "—"), *_choices(q)], **_common(q))


def _scale(t, q):
    field = forms.TypedChoiceField(choices=_scale_choices(t), coerce=int,
                                   widget=forms.RadioSelect, **_common(q))
    field.qrumy_scale = t  # used by the template to render a scale row
    return field


def _yesno(t, q):
    return forms.ChoiceField(choices=[("yes", _("Yes")), ("no", _("No"))],
                             widget=forms.RadioSelect, **_common(q))


def _text(t, q):
    return forms.CharField(max_length=500, widget=forms.TextInput(
        attrs={"placeholder": q.config.get("placeholder", "")}), **_common(q))


def _longtext(t, q):
    return forms.CharField(max_length=5000, widget=forms.Textarea(
        attrs={"rows": 4, "placeholder": q.config.get("placeholder", "")}), **_common(q))


def _email(t, q):
    return forms.EmailField(widget=forms.EmailInput(attrs={"autocomplete": "email"}),
                            **_common(q))


def _phone(t, q):
    return PhoneField(max_length=32, widget=forms.TextInput(
        attrs={"type": "tel", "autocomplete": "tel"}), **_common(q))


def _date(t, q):
    return forms.DateField(widget=forms.DateInput(attrs={"type": "date"}), **_common(q))


QTYPES: dict[str, QType] = {t.key: t for t in [
    QType("single", _("Single choice"), "check", "choice", has_options=True, build=_single),
    QType("multiple", _("Multiple choice"), "clipboard", "multi", has_options=True, build=_multi),
    QType("dropdown", _("Dropdown"), "chevron-down", "choice", has_options=True, build=_dropdown),
    QType("rating", _("Rating (1–10)"), "chart", "scale", scale=(1, 10),
          low_label=_("Poor"), high_label=_("Excellent"), build=_scale),
    QType("stars", _("Star rating"), "sparkles", "scale", scale=(1, 5), build=_scale),
    QType("nps", _("Net Promoter Score (NPS)"), "activity", "scale", scale=(0, 10),
          low_label=_("Not at all likely"), high_label=_("Extremely likely"), build=_scale),
    QType("csat", _("Customer satisfaction (CSAT)"), "message", "scale", scale=(1, 5),
          low_label=_("Very unsatisfied"), high_label=_("Very satisfied"), build=_scale),
    QType("ces", _("Customer effort (CES)"), "activity", "scale", scale=(1, 7),
          low_label=_("Very difficult"), high_label=_("Very easy"), build=_scale),
    QType("yesno", _("Yes / No"), "check", "yesno", build=_yesno),
    QType("text", _("Short text"), "text", "text", build=_text),
    QType("longtext", _("Long text"), "file", "text", build=_longtext),
    QType("email", _("Email"), "mail", "count", build=_email),
    QType("phone", _("Phone"), "phone", "count", build=_phone),
    QType("date", _("Date"), "calendar", "count", build=_date),
]}

DEFAULT_LABELS = {
    "nps": _("How likely are you to recommend us to a friend or colleague?"),
    "csat": _("How satisfied are you with your experience?"),
    "ces": _("How easy was it to get what you needed?"),
    "stars": _("How would you rate us?"),
    "rating": _("How would you rate your visit?"),
    "yesno": _("Would you visit us again?"),
    "single": _("Which option fits best?"),
    "multiple": _("Select all that apply"),
    "dropdown": _("Choose one"),
    "text": _("Your answer"),
    "longtext": _("Is there anything we could do better?"),
    "email": _("Your email"),
    "phone": _("Your phone number"),
    "date": _("Date of your visit"),
}


def get_qtype(key: str) -> QType:
    return QTYPES[key]


def parse_options(text: str) -> list[str]:
    seen, out = set(), []
    for line in (text or "").splitlines():
        line = line.strip()[:120]
        if line and line.lower() not in seen:
            seen.add(line.lower())
            out.append(line)
    return out[:MAX_OPTIONS]
