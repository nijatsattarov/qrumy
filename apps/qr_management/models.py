import secrets

from django.conf import settings
from django.core.files.storage import storages
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import OrgScopedQuerySet, TenantModel
from apps.core.utils import generate_token

SHORT_CODE_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ"
SHORT_CODE_LENGTH = 7


def new_short_code() -> str:
    return "".join(secrets.choice(SHORT_CODE_ALPHABET) for _ in range(SHORT_CODE_LENGTH))


def private_storage():
    return storages["private"]


def logo_upload_to(instance, filename):
    return f"qr-logos/{instance.organization_id}/{generate_token(12)}.png"


def file_upload_to(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"qr-files/{instance.organization_id}/{generate_token(16)}.{ext}"


class Folder(TenantModel):
    name = models.CharField(_("name"), max_length=80)

    class Meta:
        ordering = ["name"]
        verbose_name = _("folder")
        verbose_name_plural = _("folders")
        constraints = [models.UniqueConstraint("organization", Lower("name"),
                                               name="qr_folder_unique_name")]

    def __str__(self) -> str:
        return self.name


class Tag(TenantModel):
    name = models.CharField(_("name"), max_length=40)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint("organization", Lower("name"),
                                               name="qr_tag_unique_name")]

    def __str__(self) -> str:
        return self.name


class QRCodeQuerySet(OrgScopedQuerySet):
    def live(self):
        return self.filter(deleted_at__isnull=True)


class QRCode(TenantModel):
    class Mode(models.TextChoices):
        STATIC = "static", _("Static")
        DYNAMIC = "dynamic", _("Dynamic")

    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        PAUSED = "paused", _("Paused")
        SUSPENDED = "suspended", _("Suspended")

    name = models.CharField(_("name"), max_length=120)
    qr_type = models.CharField(_("type"), max_length=20, db_index=True)
    mode = models.CharField(_("mode"), max_length=8, choices=Mode.choices)
    # Dynamic codes only. Immutable once issued and never reused (rows are soft-deleted).
    short_code = models.CharField(max_length=16, unique=True, null=True, blank=True,
                                  editable=False)
    payload = models.JSONField(_("content"), default=dict)
    style = models.JSONField(_("design"), default=dict, blank=True)
    logo = models.ImageField(_("logo"), upload_to=logo_upload_to, storage=private_storage,
                             blank=True)
    status = models.CharField(_("status"), max_length=10, choices=Status.choices,
                              default=Status.ACTIVE, db_index=True)
    suspended_reason = models.CharField(_("suspension reason"), max_length=255, blank=True)
    expires_at = models.DateTimeField(_("expires at"), null=True, blank=True)
    folder = models.ForeignKey(Folder, null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="codes", verbose_name=_("folder"))
    tags = models.ManyToManyField(Tag, blank=True, related_name="codes", verbose_name=_("tags"))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")
    total_scans = models.PositiveBigIntegerField(_("scans"), default=0)
    last_scan_at = models.DateTimeField(_("last scan"), null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = QRCodeQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("QR code")
        verbose_name_plural = _("QR codes")
        indexes = [models.Index(fields=["organization", "deleted_at", "-created_at"])]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if self.mode == self.Mode.DYNAMIC and not self.short_code:
            code = new_short_code()
            while QRCode.objects.filter(short_code=code).exists():
                code = new_short_code()
            self.short_code = code
        super().save(*args, **kwargs)

    # ---- derived ---------------------------------------------------------
    @property
    def type_def(self):
        from .types import get_type

        return get_type(self.qr_type)

    @property
    def is_dynamic(self) -> bool:
        return self.mode == self.Mode.DYNAMIC

    @property
    def short_url(self) -> str:
        return f"{settings.QRUMY_QR_BASE_URL}{self.short_code}" if self.short_code else ""

    @property
    def encoded_content(self) -> str:
        """The exact text stored inside the QR symbol."""
        if self.is_dynamic:
            return self.short_url
        return self.type_def.encode(self.payload)

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def effective_status(self) -> str:
        if self.deleted_at:
            return "deleted"
        if self.status == self.Status.ACTIVE and self.is_expired:
            return "expired"
        return self.status

    def logo_bytes(self) -> bytes | None:
        if not self.logo:
            return None
        with self.logo.open("rb") as fh:
            return fh.read()


class HostedFile(TenantModel):
    """A file served by a dynamic code (PDF, menu, image). Stored outside the web root."""

    qr_code = models.OneToOneField(QRCode, on_delete=models.CASCADE, related_name="hosted_file")
    file = models.FileField(upload_to=file_upload_to, storage=private_storage)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=64)
    size = models.PositiveIntegerField()

    def __str__(self) -> str:
        return self.original_name


class BlockedDomain(models.Model):
    """Destinations staff have banned (phishing, malware, ...). Subdomains are included."""

    domain = models.CharField(_("domain"), max_length=253, unique=True)
    reason = models.CharField(_("reason"), max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["domain"]
        verbose_name = _("blocked domain")
        verbose_name_plural = _("blocked domains")

    def __str__(self) -> str:
        return self.domain

    def save(self, *args, **kwargs):
        self.domain = self.domain.strip().lower().lstrip(".")
        super().save(*args, **kwargs)
        _clear_blocklist_cache()

    def delete(self, *args, **kwargs):
        result = super().delete(*args, **kwargs)
        _clear_blocklist_cache()
        return result


def _clear_blocklist_cache() -> None:
    from django.core.cache import cache

    from .validators import BLOCKLIST_CACHE_KEY

    cache.delete(BLOCKLIST_CACHE_KEY)
