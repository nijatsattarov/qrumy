from django.conf import settings
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TenantModel
from apps.core.utils import generate_token


def private_storage():
    from django.core.files.storage import storages

    return storages["private"]


def document_upload_to(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"asset-files/{instance.organization_id}/{generate_token(16)}.{ext}"


def new_public_token() -> str:
    return generate_token(9)


class AssetCategory(TenantModel):
    name = models.CharField(_("name"), max_length=80)

    class Meta:
        ordering = ["name"]
        verbose_name = _("asset category")
        verbose_name_plural = _("asset categories")
        constraints = [models.UniqueConstraint("organization", Lower("name"),
                                               name="assets_category_unique_name")]

    def __str__(self) -> str:
        return self.name


class Location(TenantModel):
    class Kind(models.TextChoices):
        BRANCH = "branch", _("Branch")
        BUILDING = "building", _("Building")
        FLOOR = "floor", _("Floor")
        ROOM = "room", _("Room")
        DEPARTMENT = "department", _("Department")
        AREA = "area", _("Area")

    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE,
                               related_name="children", verbose_name=_("inside"))
    kind = models.CharField(_("type"), max_length=12, choices=Kind.choices, default=Kind.ROOM)
    name = models.CharField(_("name"), max_length=100)

    class Meta:
        ordering = ["name"]
        verbose_name = _("location")
        verbose_name_plural = _("locations")

    def __str__(self) -> str:
        return self.name


class Asset(TenantModel):
    class Status(models.TextChoices):
        ACTIVE = "active", _("Active")
        IN_USE = "in_use", _("In use")
        AVAILABLE = "available", _("Available")
        MAINTENANCE = "maintenance", _("Under maintenance")
        BROKEN = "broken", _("Broken")
        LOST = "lost", _("Lost")
        RETIRED = "retired", _("Retired")

    class Visibility(models.TextChoices):
        MINIMAL = "minimal", _("Name and fault reporting only")
        STANDARD = "standard", _("Plus status, location and model")
        FULL = "full", _("Plus warranty and last maintenance")

    asset_code = models.CharField(_("asset ID"), max_length=40)
    name = models.CharField(_("name"), max_length=150)
    category = models.ForeignKey(AssetCategory, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="assets", verbose_name=_("category"))
    brand = models.CharField(_("brand"), max_length=80, blank=True)
    model_name = models.CharField(_("model"), max_length=80, blank=True)
    serial_number = models.CharField(_("serial number"), max_length=80, blank=True)
    description = models.TextField(_("description"), max_length=2000, blank=True)
    instructions = models.TextField(_("instructions for staff"), max_length=2000, blank=True,
                                    help_text=_("Shown on the QR profile, e.g. how to use or "
                                                "who to call."))
    purchase_date = models.DateField(_("purchase date"), null=True, blank=True)
    warranty_expires_at = models.DateField(_("warranty until"), null=True, blank=True)
    purchase_price = models.DecimalField(_("purchase price"), max_digits=12, decimal_places=2,
                                         null=True, blank=True)
    currency = models.CharField(_("currency"), max_length=3, default="AZN")
    supplier = models.CharField(_("supplier"), max_length=120, blank=True)
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="assets", verbose_name=_("location"))
    department = models.CharField(_("department"), max_length=80, blank=True)
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+",
                                    verbose_name=_("responsible person"))
    status = models.CharField(_("status"), max_length=12, choices=Status.choices,
                              default=Status.ACTIVE, db_index=True)
    custom_fields = models.JSONField(_("custom fields"), default=dict, blank=True)
    public_token = models.CharField(max_length=24, unique=True, default=new_public_token,
                                    editable=False)
    public_visibility = models.CharField(_("QR profile shows"), max_length=10,
                                         choices=Visibility.choices, default=Visibility.STANDARD)
    qr_code = models.ForeignKey("qr_management.QRCode", null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["name"]
        verbose_name = _("asset")
        verbose_name_plural = _("assets")
        constraints = [models.UniqueConstraint("organization", Lower("asset_code"),
                                               name="assets_asset_unique_code")]

    def __str__(self) -> str:
        return f"{self.asset_code} · {self.name}"

    @property
    def public_url(self) -> str:
        return f"{settings.SITE_URL}/a/{self.public_token}"

    @property
    def warranty_active(self) -> bool | None:
        if not self.warranty_expires_at:
            return None
        return self.warranty_expires_at >= timezone.now().date()


class AssetDocument(TenantModel):
    class Kind(models.TextChoices):
        IMAGE = "image", _("Photo")
        DOCUMENT = "document", _("Document")

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    file = models.FileField(upload_to=document_upload_to, storage=private_storage)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                    on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.original_name


class FaultReport(TenantModel):
    class Category(models.TextChoices):
        NOT_WORKING = "not_working", _("Not working")
        DAMAGED = "damaged", _("Damaged")
        NOISE = "noise", _("Noise or leak")
        SAFETY = "safety", _("Safety issue")
        MISSING = "missing", _("Missing parts")
        CLEANING = "cleaning", _("Needs cleaning")
        OTHER = "other", _("Other")

    class Priority(models.TextChoices):
        LOW = "low", _("Low")
        NORMAL = "normal", _("Normal")
        HIGH = "high", _("High")
        URGENT = "urgent", _("Urgent")

    class Status(models.TextChoices):
        NEW = "new", _("New")
        ASSIGNED = "assigned", _("Assigned")
        IN_PROGRESS = "in_progress", _("In progress")
        WAITING = "waiting", _("Waiting")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")

    OPEN_STATUSES = (Status.NEW, Status.ASSIGNED, Status.IN_PROGRESS, Status.WAITING)

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="faults")
    category = models.CharField(_("problem"), max_length=12, choices=Category.choices)
    description = models.TextField(_("description"), max_length=2000)
    priority = models.CharField(_("priority"), max_length=8, choices=Priority.choices,
                                default=Priority.NORMAL, db_index=True)
    status = models.CharField(_("status"), max_length=12, choices=Status.choices,
                              default=Status.NEW, db_index=True)
    photo = models.FileField(upload_to=document_upload_to, storage=private_storage, blank=True)
    reporter_name = models.CharField(_("reported by"), max_length=120, blank=True)
    reporter_contact = models.CharField(_("contact"), max_length=120, blank=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    via_qr = models.BooleanField(default=False)
    location_label = models.CharField(max_length=300, blank=True)  # snapshot at report time
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+",
                                    verbose_name=_("assigned to"))
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution = models.TextField(_("resolution"), max_length=2000, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("fault report")
        verbose_name_plural = _("fault reports")

    def __str__(self) -> str:
        return f"{self.asset} — {self.get_category_display()}"

    @property
    def is_open(self) -> bool:
        return self.status in self.OPEN_STATUSES


class MaintenanceRecord(TenantModel):
    class Kind(models.TextChoices):
        PREVENTIVE = "preventive", _("Preventive")
        CORRECTIVE = "corrective", _("Corrective (repair)")
        INSPECTION = "inspection", _("Inspection")

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="maintenance")
    kind = models.CharField(_("type"), max_length=12, choices=Kind.choices,
                            default=Kind.CORRECTIVE)
    performed_on = models.DateField(_("date"), default=timezone.localdate)
    technician = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+",
                                   verbose_name=_("technician"))
    technician_name = models.CharField(_("external technician"), max_length=120, blank=True)
    cost = models.DecimalField(_("cost"), max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(_("notes"), max_length=2000, blank=True)
    fault = models.ForeignKey(FaultReport, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="maintenance", verbose_name=_("related fault"))
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-performed_on", "-created_at"]
        verbose_name = _("maintenance record")
        verbose_name_plural = _("maintenance records")

    def __str__(self) -> str:
        return f"{self.asset} — {self.performed_on}"


class AssetActivity(TenantModel):
    """Per-asset history shown on the asset page."""

    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="activity")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=40)
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.asset_id} {self.action}"
