from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from timezone_field import TimeZoneField

from apps.core.models import TimeStampedModel
from apps.core.utils import generate_token

from .roles import Role


def logo_upload_to(instance, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    return f"public/org-logos/{generate_token(12)}.{ext}"


class Industry(models.TextChoices):
    HOSPITALITY = "hospitality", _("Hospitality & restaurants")
    RETAIL = "retail", _("Retail & e-commerce")
    MANUFACTURING = "manufacturing", _("Manufacturing")
    LOGISTICS = "logistics", _("Logistics & warehousing")
    CONSTRUCTION = "construction", _("Construction")
    HEALTHCARE = "healthcare", _("Healthcare")
    EDUCATION = "education", _("Education")
    EVENTS = "events", _("Events & exhibitions")
    MARKETING = "marketing", _("Marketing & agencies")
    REAL_ESTATE = "real_estate", _("Real estate & facilities")
    TECHNOLOGY = "technology", _("Technology")
    PUBLIC = "public", _("Public sector & non-profit")
    OTHER = "other", _("Other")


class Organization(TimeStampedModel):
    class Kind(models.TextChoices):
        STANDARD = "standard", _("Standard")
        AGENCY = "agency", _("Agency")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")

    name = models.CharField(_("organization name"), max_length=120)
    slug = models.SlugField(_("URL name"), max_length=60, unique=True)
    logo = models.ImageField(_("logo"), upload_to=logo_upload_to, blank=True)
    website = models.URLField(_("website"), blank=True)
    industry = models.CharField(_("industry"), max_length=32, choices=Industry.choices,
                                blank=True)
    country = CountryField(_("country"), blank=True)
    timezone = TimeZoneField(_("time zone"), default=settings.QRUMY_DEFAULT_TIMEZONE)
    language = models.CharField(_("default language"), max_length=8,
                                choices=settings.LANGUAGES, default=settings.LANGUAGE_CODE)
    contact_email = models.EmailField(_("contact email"), blank=True)
    contact_phone = models.CharField(_("contact phone"), max_length=32, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                              related_name="owned_organizations", verbose_name=_("owner"))
    # Agency groundwork (Phase 10): a client organization points to its agency.
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="clients", verbose_name=_("managed by"))
    kind = models.CharField(_("type"), max_length=16, choices=Kind.choices,
                            default=Kind.STANDARD)
    status = models.CharField(_("status"), max_length=16, choices=Status.choices,
                              default=Status.ACTIVE, db_index=True)

    class Meta:
        ordering = ["name"]
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")

    def __str__(self) -> str:
        return self.name

    @property
    def is_active(self) -> bool:
        return self.status == self.Status.ACTIVE


class Membership(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="memberships")
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                     related_name="memberships")
    role = models.CharField(_("role"), max_length=16, choices=Role.choices,
                            default=Role.MEMBER)

    class Meta:
        ordering = ["created_at"]
        verbose_name = _("membership")
        verbose_name_plural = _("memberships")
        constraints = [
            models.UniqueConstraint(fields=["user", "organization"],
                                    name="organizations_membership_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.role})"


class Invitation(TimeStampedModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE,
                                     related_name="invitations")
    email = models.EmailField(_("email"))
    role = models.CharField(_("role"), max_length=16, choices=Role.choices,
                            default=Role.MEMBER)
    token_hash = models.CharField(max_length=64, unique=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                   on_delete=models.SET_NULL, related_name="+")
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("invitation")
        verbose_name_plural = _("invitations")
        constraints = [
            models.UniqueConstraint(
                "organization", Lower("email"),
                condition=Q(accepted_at__isnull=True, revoked_at__isnull=True),
                name="organizations_invitation_one_pending_per_email",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.email} → {self.organization}"

    @property
    def is_pending(self) -> bool:
        return (self.accepted_at is None and self.revoked_at is None
                and self.expires_at > timezone.now())

    @property
    def is_expired(self) -> bool:
        return self.accepted_at is None and self.expires_at <= timezone.now()
