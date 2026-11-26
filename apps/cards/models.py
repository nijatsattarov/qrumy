"""Qrumy Card: digital business cards for people and companies."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from PIL import Image

from apps.core.models import TenantModel
from apps.core.utils import generate_token

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_GALLERY = 12


def validate_image(file) -> None:
    if file.size > MAX_IMAGE_BYTES:
        raise ValidationError(_("The image must be 5 MB or smaller."))
    try:
        file.seek(0)
        with Image.open(file) as img:
            fmt = img.format
            img.verify()
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(_("Upload a valid PNG, JPEG or WebP image.")) from exc
    finally:
        file.seek(0)
    if fmt not in ("PNG", "JPEG", "WEBP"):
        raise ValidationError(_("Upload a valid PNG, JPEG or WebP image."))


def card_upload_to(instance, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    if ext not in ("png", "jpg", "jpeg", "webp"):
        ext = "jpg"
    return f"public/cards/{generate_token(12)}.{ext}"


def _new_token() -> str:
    return generate_token(8)


class Card(TenantModel):
    class Kind(models.TextChoices):
        PERSON = "person", _("Person")
        COMPANY = "company", _("Company")

    class Template(models.TextChoices):
        CLASSIC = "classic", _("Classic")
        MODERN = "modern", _("Modern")
        BOLD = "bold", _("Bold")
        MINIMAL = "minimal", _("Minimal")

    public_token = models.CharField(max_length=24, unique=True, default=_new_token,
                                    editable=False)
    kind = models.CharField(_("card for"), max_length=8, choices=Kind.choices,
                            default=Kind.PERSON)
    template = models.CharField(_("template"), max_length=10, choices=Template.choices,
                                default=Template.CLASSIC)
    accent_color = models.CharField(_("colour"), max_length=7, default="#101B3A")

    name = models.CharField(_("name"), max_length=120)
    headline = models.CharField(_("job title or slogan"), max_length=120, blank=True)
    company = models.CharField(_("company"), max_length=120, blank=True)
    about = models.TextField(_("about"), max_length=1500, blank=True)
    photo = models.ImageField(_("profile photo or logo"), upload_to=card_upload_to, blank=True,
                              validators=[validate_image])
    cover = models.ImageField(_("cover image"), upload_to=card_upload_to, blank=True,
                              validators=[validate_image])

    phone = models.CharField(_("phone"), max_length=32, blank=True)
    phone_2 = models.CharField(_("second phone"), max_length=32, blank=True)
    email = models.EmailField(_("email"), blank=True)
    website = models.URLField(_("website"), max_length=500, blank=True)
    address = models.CharField(_("address"), max_length=240, blank=True)
    map_url = models.URLField(_("map link"), max_length=500, blank=True,
                              help_text=_("Optional. A Google Maps link to your place."))
    links = models.JSONField(_("social links"), default=list, blank=True)

    is_published = models.BooleanField(_("published"), default=False)
    qr_code = models.ForeignKey("qr_management.QRCode", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = _("digital card")
        verbose_name_plural = _("digital cards")

    def __str__(self) -> str:
        return self.name

    @property
    def public_path(self) -> str:
        return f"/c/{self.public_token}"

    @property
    def public_url(self) -> str:
        return f"{settings.SITE_URL}{self.public_path}"

    @property
    def maps_link(self) -> str:
        if self.map_url:
            return self.map_url
        if self.address:
            from urllib.parse import quote

            return "https://www.google.com/maps/search/?api=1&query=" + quote(self.address)
        return ""

    @property
    def initials(self) -> str:
        parts = [p for p in self.name.split() if p]
        return "".join(p[0] for p in parts[:2]).upper() or "Q"

    def completeness(self) -> list[tuple[str, bool]]:
        """Checklist shown in the editor."""
        return [(_("Name"), bool(self.name)), (_("Photo"), bool(self.photo)),
                (_("Contact"), bool(self.phone or self.email)),
                (_("About"), bool(self.about)), (_("Social links"), bool(self.links)),
                (_("Published"), self.is_published)]


class CardPhoto(TenantModel):
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(_("photo"), upload_to=card_upload_to, validators=[validate_image])
    caption = models.CharField(_("caption"), max_length=120, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]
        verbose_name = _("gallery photo")
        verbose_name_plural = _("gallery photos")


class CardDaily(models.Model):
    """Daily counters for a card: page views, saved contacts and link clicks."""

    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="daily")
    day = models.DateField()
    views = models.PositiveIntegerField(default=0)
    saves = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["card", "day"],
                                               name="cards_daily_unique")]

    def __str__(self) -> str:
        return f"{self.card_id} {self.day}: {self.views} views"
