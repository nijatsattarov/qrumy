"""Event Lead Capture: collect visitor contacts at fairs, conferences and stands."""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel
from apps.core.utils import generate_token, hash_token


def _token() -> str:
    return generate_token(8)


class Event(TenantModel):
    name = models.CharField(_("event name"), max_length=160)
    starts_on = models.DateField(_("first day"), null=True, blank=True)
    ends_on = models.DateField(_("last day"), null=True, blank=True)
    venue = models.CharField(_("venue"), max_length=200, blank=True)
    language = models.CharField(_("form language"), max_length=8, choices=settings.LANGUAGES,
                                default="az")
    welcome_text = models.CharField(
        _("text above the form"), max_length=300, blank=True,
        help_text=_("e.g. Leave your contacts and we will send you our catalogue."))
    interests = models.TextField(
        _("interests to choose from"), blank=True,
        help_text=_("One per line, e.g. products or services visitors can tick. Optional."))
    ask_phone = models.BooleanField(_("ask for phone"), default=True)
    ask_company = models.BooleanField(_("ask for company and job title"), default=True)
    ask_message = models.BooleanField(_("ask for a message"), default=True)
    consent_text = models.CharField(
        _("consent text"), max_length=400, blank=True,
        help_text=_("Shown next to the required consent checkbox. Empty: a standard text."))
    thank_you_text = models.CharField(_("thank-you message"), max_length=300, blank=True)
    thank_you_url = models.URLField(_("link after submitting"), max_length=500, blank=True,
                                    help_text=_("Optional, e.g. your catalogue or website."))
    is_active = models.BooleanField(_("collecting leads"), default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-starts_on", "-created_at"]
        verbose_name = _("event")
        verbose_name_plural = _("events")

    def __str__(self) -> str:
        return self.name

    @property
    def interest_list(self) -> list[str]:
        return [line.strip() for line in self.interests.splitlines() if line.strip()][:30]


class CapturePoint(TenantModel):
    """Where leads are collected: a stand, an exhibitor company, a booth or a person."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="points")
    name = models.CharField(_("name"), max_length=120,
                            help_text=_("e.g. Stand A12, exhibitor company or sales person"))
    company_name = models.CharField(
        _("exhibitor company"), max_length=160, blank=True,
        help_text=_("Fill in when the stand belongs to another company (exhibitor)."))
    contact_email = models.EmailField(_("email for new leads"), blank=True,
                                      help_text=_("Gets an email for every new lead."))
    capture_token = models.CharField(max_length=24, unique=True, default=_token,
                                     editable=False)
    portal_token_hash = models.CharField(max_length=64, blank=True, editable=False)
    qr_code = models.ForeignKey("qr_management.QRCode", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["name", "pk"]
        verbose_name = _("collection point")
        verbose_name_plural = _("collection points")

    def __str__(self) -> str:
        return f"{self.event} · {self.name}"

    @property
    def public_path(self) -> str:
        return f"/e/{self.capture_token}"

    @property
    def public_url(self) -> str:
        return f"{settings.SITE_URL}{self.public_path}"

    def new_portal_token(self) -> str:
        """Create (or replace) the private link for an exhibitor; only the hash is kept."""
        raw = generate_token(24)
        self.portal_token_hash = hash_token(raw)
        self.save(update_fields=["portal_token_hash", "updated_at"])
        return raw


class Lead(TenantModel):
    class Temperature(models.TextChoices):
        HOT = "hot", _("Hot")
        WARM = "warm", _("Warm")
        COLD = "cold", _("Cold")

    class Stage(models.TextChoices):
        NEW = "new", _("New")
        CONTACTED = "contacted", _("Contacted")
        QUALIFIED = "qualified", _("Qualified")
        WON = "won", _("Won")
        LOST = "lost", _("Lost")

    class Source(models.TextChoices):
        QR = "qr", _("QR form")
        STAFF = "staff", _("Added by staff")

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="leads")
    point = models.ForeignKey(CapturePoint, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="leads", verbose_name=_("collection point"))
    full_name = models.CharField(_("full name"), max_length=120)
    email = models.EmailField(_("email"), blank=True)
    phone = models.CharField(_("phone"), max_length=32, blank=True)
    company = models.CharField(_("company"), max_length=160, blank=True)
    job_title = models.CharField(_("job title"), max_length=120, blank=True)
    interests = models.JSONField(_("interests"), default=list, blank=True)
    message = models.TextField(_("message"), max_length=1000, blank=True)
    temperature = models.CharField(_("interest level"), max_length=4,
                                   choices=Temperature.choices, default=Temperature.WARM)
    stage = models.CharField(_("stage"), max_length=10, choices=Stage.choices,
                             default=Stage.NEW)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+",
                                    verbose_name=_("assigned to"))
    source = models.CharField(_("source"), max_length=6, choices=Source.choices,
                              default=Source.QR)
    consent = models.BooleanField(_("consent given"), default=False)
    consent_text = models.CharField(max_length=400, blank=True)
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("lead")
        verbose_name_plural = _("leads")
        indexes = [models.Index(fields=["organization", "event", "-created_at"])]

    def __str__(self) -> str:
        return self.full_name


class LeadNote(TenantModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                               related_name="+")
    body = models.TextField(_("note"), max_length=2000)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("lead note")
        verbose_name_plural = _("lead notes")

    def __str__(self) -> str:
        return self.body[:40]


class FollowUp(TenantModel):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="followups")
    title = models.CharField(_("task"), max_length=160)
    due_on = models.DateField(_("due"), null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["done_at", "due_on", "pk"]
        verbose_name = _("follow-up task")
        verbose_name_plural = _("follow-up tasks")

    def __str__(self) -> str:
        return self.title
