from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel, TimeStampedModel
from apps.core.utils import generate_token


def new_public_token() -> str:
    return generate_token(9)  # 12 URL-safe characters


def logo_upload_to(instance, filename):
    return f"public/survey-logos/{generate_token(12)}.png"


class Survey(TenantModel):
    class Status(models.TextChoices):
        DRAFT = "draft", _("Draft")
        PUBLISHED = "published", _("Published")
        CLOSED = "closed", _("Closed")

    class Contact(models.TextChoices):
        OFF = "off", _("Don't ask (anonymous)")
        OPTIONAL = "optional", _("Optional")
        REQUIRED = "required", _("Required")

    title = models.CharField(_("title"), max_length=150)
    description = models.TextField(_("description"), max_length=1000, blank=True)
    public_token = models.CharField(max_length=24, unique=True, default=new_public_token,
                                    editable=False)
    status = models.CharField(_("status"), max_length=10, choices=Status.choices,
                              default=Status.DRAFT, db_index=True)
    language = models.CharField(_("survey language"), max_length=8, choices=settings.LANGUAGES,
                                default=settings.LANGUAGE_CODE,
                                help_text=_("Language of buttons and messages on the public page."))
    accent_color = models.CharField(_("accent color"), max_length=7, default="#101B3A")
    logo = models.ImageField(_("logo"), upload_to=logo_upload_to, blank=True,
                             help_text=_("Shown on the survey page. "
                                         "Defaults to your organization logo."))
    thank_you_title = models.CharField(_("thank-you title"), max_length=120, blank=True)
    thank_you_message = models.TextField(_("thank-you message"), max_length=1000, blank=True)
    redirect_url = models.URLField(_("redirect after submit"), max_length=2000, blank=True)
    contact_mode = models.CharField(_("ask for contact details"), max_length=10,
                                    choices=Contact.choices, default=Contact.OFF)
    consent_text = models.CharField(_("consent text"), max_length=300, blank=True,
                                    help_text=_("Shown next to the consent checkbox when contact "
                                                "details are collected."))
    closes_at = models.DateTimeField(_("closes at"), null=True, blank=True)
    response_limit = models.PositiveIntegerField(_("maximum responses"), null=True, blank=True)
    qr_code = models.ForeignKey("qr_management.QRCode", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    published_at = models.DateTimeField(null=True, blank=True)
    response_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("survey")
        verbose_name_plural = _("surveys")

    def __str__(self) -> str:
        return self.title

    @property
    def public_url(self) -> str:
        return f"{settings.SITE_URL}/s/{self.public_token}"

    def closed_reason(self) -> str | None:
        """Why the public page does not accept responses (None = open)."""
        if self.status == self.Status.DRAFT:
            return "draft"
        if self.status == self.Status.CLOSED:
            return "closed"
        if self.closes_at and self.closes_at <= timezone.now():
            return "expired"
        if self.response_limit and self.response_count >= self.response_limit:
            return "full"
        return None


class Question(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="questions")
    qtype = models.CharField(_("type"), max_length=16)
    label = models.CharField(_("question"), max_length=300)
    help_text = models.CharField(_("help text"), max_length=300, blank=True)
    required = models.BooleanField(_("required"), default=False)
    position = models.PositiveIntegerField(default=0)
    config = models.JSONField(default=dict, blank=True)  # options, scale labels, placeholder
    # Conditional logic (architecture): {"show_if": {"question": <id>, "equals": <value>}}
    logic = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["position", "id"]
        verbose_name = _("question")
        verbose_name_plural = _("questions")

    def __str__(self) -> str:
        return self.label

    @property
    def type_def(self):
        from .qtypes import get_qtype

        return get_qtype(self.qtype)

    @property
    def options(self) -> list[str]:
        return list(self.config.get("options", []))


class ResponseTag(TenantModel):
    name = models.CharField(_("name"), max_length=40)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint("organization", Lower("name"),
                                               name="surveys_tag_unique_name")]

    def __str__(self) -> str:
        return self.name


class Response(TenantModel):
    class Status(models.TextChoices):
        OPEN = "open", _("Open")
        RESOLVED = "resolved", _("Resolved")

    class Source(models.TextChoices):
        LINK = "link", _("Direct link")
        QR = "qr", _("QR code")
        EMBED = "embed", _("Website embed")
        EMAIL = "email", _("Email")

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="responses")
    submitted_at = models.DateTimeField(default=timezone.now, db_index=True)
    source = models.CharField(_("source"), max_length=8, choices=Source.choices,
                              default=Source.LINK)
    language = models.CharField(max_length=8, blank=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    contact_name = models.CharField(_("name"), max_length=120, blank=True)
    contact_email = models.EmailField(_("email"), blank=True)
    consent = models.BooleanField(_("consent given"), default=False)
    consent_text = models.CharField(max_length=300, blank=True)
    status = models.CharField(_("status"), max_length=10, choices=Status.choices,
                              default=Status.OPEN, db_index=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+",
                                    verbose_name=_("assigned to"))
    resolved_at = models.DateTimeField(null=True, blank=True)
    tags = models.ManyToManyField(ResponseTag, blank=True, related_name="responses")
    # Headline scores copied from answers for fast filtering
    nps = models.PositiveSmallIntegerField(null=True, blank=True)
    csat = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = _("response")
        verbose_name_plural = _("responses")
        indexes = [models.Index(fields=["survey", "-submitted_at"])]

    def __str__(self) -> str:
        return f"{self.survey} — {self.submitted_at:%Y-%m-%d %H:%M}"


class Answer(models.Model):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    value_text = models.TextField(blank=True)
    value_number = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    value_json = models.JSONField(null=True, blank=True)  # list of selected options

    class Meta:
        constraints = [models.UniqueConstraint(fields=["response", "question"],
                                               name="surveys_answer_unique")]
        indexes = [models.Index(fields=["question", "value_number"])]

    def __str__(self) -> str:
        return f"{self.question_id}: {self.display}"

    @property
    def display(self) -> str:
        if self.value_json:
            return ", ".join(self.value_json)
        if self.value_text:
            return self.value_text
        if self.value_number is not None:
            n = self.value_number
            return str(int(n)) if n == int(n) else str(n)
        return ""


class ResponseNote(TimeStampedModel):
    response = models.ForeignKey(Response, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                               related_name="+")
    body = models.TextField(_("note"), max_length=2000)

    class Meta:
        ordering = ["created_at"]

    def __str__(self) -> str:
        return self.body[:50]


class SurveyDailyStat(models.Model):
    """Page views (form starts) per day — denominator for the completion rate."""

    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name="daily_stats")
    day = models.DateField()
    views = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["survey", "day"],
                                               name="surveys_dailystat_unique")]

    def __str__(self) -> str:
        return f"{self.survey_id} {self.day}: {self.views}"
