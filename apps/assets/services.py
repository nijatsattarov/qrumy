"""Asset business logic. Views only call these functions."""

import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.functions import Lower
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from PIL import Image

from apps.audit_logs.services import record
from apps.core import quotas
from apps.notifications.services import notify, send_templated_email
from apps.organizations.models import Membership

from . import locations as loc_helpers
from .models import Asset, AssetActivity, AssetDocument, FaultReport, Location, MaintenanceRecord

ASSETS_FEATURE = "assets.max"
MAX_FILE_MB = 10
IMAGE_TYPES = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}


class AssetError(Exception):
    pass


def log(asset, actor, action: str, **details) -> None:
    AssetActivity.objects.create(organization=asset.organization, asset=asset,
                                 actor=actor if getattr(actor, "is_authenticated", False)
                                 else None, action=action, details=details)


# ------------------------------------------------------------------ assets
def next_asset_code(organization) -> str:
    codes = (Asset.objects.for_org(organization).annotate(c=Lower("asset_code"))
             .filter(c__startswith="ast-").values_list("asset_code", flat=True))
    numbers = [int(m.group(1)) for c in codes if (m := re.match(r"(?i)AST-(\d+)$", c))]
    return f"AST-{(max(numbers) + 1) if numbers else 1:05d}"


def code_taken(organization, code: str, exclude_pk=None) -> bool:
    qs = Asset.objects.for_org(organization).filter(asset_code__iexact=code.strip())
    return qs.exclude(pk=exclude_pk).exists() if exclude_pk else qs.exists()


@transaction.atomic
def create_asset(*, organization, actor, data: dict, request=None) -> Asset:
    try:
        quotas.check(organization, ASSETS_FEATURE, Asset.objects.for_org(organization).count())
    except quotas.QuotaExceeded as exc:
        raise AssetError(_("Your plan allows up to %(limit)s assets.") % {"limit": exc.limit}) \
            from exc
    data = dict(data)
    data["asset_code"] = (data.get("asset_code") or "").strip() or next_asset_code(organization)
    if code_taken(organization, data["asset_code"]):
        raise AssetError(_("Another asset already uses this ID."))
    asset = Asset.objects.create(organization=organization, created_by=actor, **data)
    log(asset, actor, "created")
    record("asset.created", actor=actor, organization=organization, target=asset,
           request=request)
    return asset


def update_asset(*, asset, actor, form, request=None) -> Asset:
    old_status = Asset.objects.filter(pk=asset.pk).values_list("status", flat=True).first()
    changed = list(form.changed_data)
    asset = form.save()
    if "status" in changed:
        log(asset, actor, "status", old=old_status, new=asset.status)
        changed.remove("status")
    if changed:
        log(asset, actor, "updated", fields=changed)
    return asset


def set_status(*, asset, actor, status: str) -> None:
    if status not in Asset.Status.values or status == asset.status:
        return
    old, asset.status = asset.status, status
    asset.save(update_fields=["status", "updated_at"])
    log(asset, actor, "status", old=old, new=status)


@transaction.atomic
def delete_asset(*, asset, actor, request=None) -> None:
    if asset.qr_code_id and asset.qr_code.deleted_at is None and asset.qr_code.status == "active":
        from apps.qr_management import services as qr_services

        qr_services.set_status(qr=asset.qr_code, actor=actor, status="paused", request=request)
    record("asset.deleted", actor=actor, organization=asset.organization, target=asset,
           request=request)
    asset.delete()


def ensure_qr(*, asset, actor, request=None):
    from apps.qr_management import services as qr_services
    from apps.qr_management.engine import QRStyle

    if asset.qr_code_id and asset.qr_code.deleted_at is None:
        return asset.qr_code
    try:
        qr = qr_services.create_qr(
            organization=asset.organization, actor=actor, qr_type="asset", mode="dynamic",
            name=f"{asset.asset_code} · {asset.name}"[:120],
            payload={"asset_token": asset.public_token, "asset_name": asset.name,
                     "asset_code": asset.asset_code},
            style=QRStyle(frame="bottom", cta_text=asset.asset_code[:30]), request=request)
    except qr_services.QRError as exc:
        raise AssetError(str(exc)) from exc
    asset.qr_code = qr
    asset.save(update_fields=["qr_code", "updated_at"])
    log(asset, actor, "qr_created")
    return qr


# ------------------------------------------------------------------ locations
def validate_parent(location: Location | None, parent: Location | None) -> None:
    if parent is None or location is None or location.pk is None:
        return
    if parent.pk in loc_helpers.descendant_ids(location.organization, location.pk):
        raise AssetError(_("A location cannot be placed inside itself."))


# ------------------------------------------------------------------ files
def validate_upload(upload, *, images_only=False) -> tuple[str, str]:
    """Return (kind, content_type) after checking size and real file type."""
    if upload.size > MAX_FILE_MB * 1024 * 1024:
        raise ValidationError(_("The file must be %(mb)s MB or smaller.") % {"mb": MAX_FILE_MB})
    upload.seek(0)
    head = upload.read(8)
    upload.seek(0)
    if not images_only and head.startswith(b"%PDF-"):
        return "document", "application/pdf"
    try:
        with Image.open(upload) as img:
            fmt = img.format
            img.verify()
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(_("Upload a photo (PNG, JPEG, WebP)") if images_only else
                              _("Upload a PDF or a photo (PNG, JPEG, WebP).")) from exc
    finally:
        upload.seek(0)
    if fmt not in IMAGE_TYPES:
        raise ValidationError(_("Upload a PDF or a photo (PNG, JPEG, WebP)."))
    return "image", IMAGE_TYPES[fmt]


def add_document(*, asset, actor, upload) -> AssetDocument:
    kind, content_type = validate_upload(upload)
    doc = AssetDocument.objects.create(
        organization=asset.organization, asset=asset, kind=kind, file=upload,
        original_name=upload.name[:255], content_type=content_type, size=upload.size,
        uploaded_by=actor)
    log(asset, actor, "document_added", name=doc.original_name)
    return doc


def delete_document(*, document, actor) -> None:
    log(document.asset, actor, "document_deleted", name=document.original_name)
    document.file.delete(save=False)
    document.delete()


# ------------------------------------------------------------------ faults
def _fault_recipients(asset):
    if asset.responsible_id:
        return [asset.responsible]
    return [m.user for m in Membership.objects.filter(
        organization=asset.organization, role__in=["owner", "admin", "manager"])
        .select_related("user")]


@transaction.atomic
def report_fault(*, asset, category: str, description: str, priority: str, photo=None,
                 reporter_name="", reporter_contact="", reported_by=None,
                 via_qr=False) -> FaultReport:
    if photo is not None:
        validate_upload(photo, images_only=True)
    path = loc_helpers.paths(asset.organization).get(asset.location_id, "")
    fault = FaultReport.objects.create(
        organization=asset.organization, asset=asset, category=category,
        description=description.strip(), priority=priority, photo=photo or "",
        reporter_name=reporter_name[:120], reporter_contact=reporter_contact[:120],
        reported_by=reported_by if getattr(reported_by, "is_authenticated", False) else None,
        via_qr=via_qr, location_label=path[:300])
    log(asset, reported_by, "fault_reported", fault=fault.pk, priority=priority)
    url = reverse("asset_fault", kwargs={"org_slug": asset.organization.slug, "pk": fault.pk})
    title = _("New fault report: %(asset)s") % {"asset": asset.name}
    for user in _fault_recipients(asset):
        notify(user, kind="assets.fault", organization=asset.organization, title=title,
               body=fault.get_category_display(), url=url)
        if priority in (FaultReport.Priority.HIGH, FaultReport.Priority.URGENT):
            send_templated_email(
                to=user.email, template="assets/email/fault",
                context={"asset": asset, "fault": fault, "location": path,
                         "url": f"{_site()}{url}"}, language=user.language)
    return fault


def _site():
    from django.conf import settings

    return settings.SITE_URL


def update_fault(*, fault, actor, status: str | None = None, assigned_to=False,
                 resolution: str | None = None, request=None) -> FaultReport:
    changes = {}
    if assigned_to is not False and assigned_to != fault.assigned_to:
        fault.assigned_to = assigned_to
        changes["assigned_to"] = assigned_to.email if assigned_to else None
        if assigned_to and fault.status == FaultReport.Status.NEW and status is None:
            status = FaultReport.Status.ASSIGNED
        if assigned_to and assigned_to != actor:
            notify(assigned_to, kind="assets.fault_assigned", organization=fault.organization,
                   title=_("A fault report was assigned to you"), body=fault.asset.name,
                   url=reverse("asset_fault", kwargs={"org_slug": fault.organization.slug,
                                                      "pk": fault.pk}))
    if status and status != fault.status:
        if status not in FaultReport.Status.values:
            raise AssetError(_("Invalid status."))
        changes["status"] = [fault.status, status]
        fault.status = status
        fault.resolved_at = (timezone.now() if status in (FaultReport.Status.COMPLETED,
                                                          FaultReport.Status.CANCELLED) else None)
    if resolution is not None:
        fault.resolution = resolution.strip()
    fault.save()
    if changes:
        log(fault.asset, actor, "fault_updated", fault=fault.pk, **changes)
        record("asset.fault_updated", actor=actor, organization=fault.organization,
               target=fault, changes=changes, request=request)
    return fault


def add_maintenance(*, asset, actor, data: dict) -> MaintenanceRecord:
    rec = MaintenanceRecord.objects.create(organization=asset.organization, asset=asset,
                                           created_by=actor, **data)
    log(asset, actor, "maintenance", kind=rec.kind, record=rec.pk)
    return rec
