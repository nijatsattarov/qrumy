"""QR business logic. Views only call these functions."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.audit_logs.services import record
from apps.core import quotas

from .engine import QRStyle, contrast_problems, is_scannable
from .files import validate_hosted_file
from .models import Folder, HostedFile, QRCode, Tag
from .types import DYNAMIC, get_type

DYNAMIC_FEATURE = "qr.dynamic"


class QRError(Exception):
    pass


def dynamic_usage(organization) -> int:
    return QRCode.objects.for_org(organization).live().filter(mode=DYNAMIC).count()


def check_dynamic_quota(organization, increment: int = 1) -> None:
    try:
        quotas.check(organization, DYNAMIC_FEATURE, dynamic_usage(organization), increment)
    except quotas.QuotaExceeded as exc:
        raise QRError(_("Your plan allows %(limit)s dynamic QR codes. Pause is not enough — "
                        "delete unused codes or upgrade your plan.") % {"limit": exc.limit}) \
            from exc


def resolve_tags(organization, names: list[str]) -> list[Tag]:
    tags = []
    for name in {n.strip()[:40] for n in names if n.strip()}:
        tag = Tag.objects.for_org(organization).filter(name__iexact=name).first()
        tags.append(tag or Tag.objects.create(organization=organization, name=name))
    return tags


def check_design(content: str, style: QRStyle, logo: bytes | None) -> None:
    problems = contrast_problems(style)
    if problems:
        raise ValidationError(problems)
    if not is_scannable(content, style, logo):
        raise ValidationError(_("This design cannot be scanned reliably. Increase the contrast, "
                                "make the logo smaller or choose simpler shapes."))


def _attach_file(qr: QRCode, upload, actor) -> None:
    content_type = validate_hosted_file(upload, qr.type_def.hosted_file,
                                        quotas.get_limit(qr.organization, "qr.file_mb"))
    HostedFile.objects.filter(qr_code=qr).delete()
    HostedFile.objects.create(organization=qr.organization, qr_code=qr, file=upload,
                              original_name=upload.name[:255], content_type=content_type,
                              size=upload.size)


@transaction.atomic
def create_qr(*, organization, actor, qr_type: str, mode: str, name: str, payload: dict,
              style: QRStyle, logo_file=None, upload=None, folder: Folder | None = None,
              tags: list[str] = (), expires_at=None, request=None,
              verify: bool = True) -> QRCode:
    type_def = get_type(qr_type)
    if mode not in type_def.modes:
        raise QRError(_("This QR type cannot be %(mode)s.") % {"mode": mode})
    if mode == DYNAMIC:
        check_dynamic_quota(organization)
    if type_def.hosted_file and upload is None:
        raise QRError(_("Upload a file."))
    qr = QRCode(organization=organization, qr_type=qr_type, mode=mode, name=name.strip(),
                payload=payload, style=style.to_dict(), folder=folder, created_by=actor,
                expires_at=expires_at)
    if logo_file:
        qr.logo = logo_file
    qr.save()  # assigns the short code for dynamic codes
    if verify:
        check_design(qr.encoded_content, style, qr.logo_bytes())
    if upload is not None:
        _attach_file(qr, upload, actor)
    qr.tags.set(resolve_tags(organization, list(tags)))
    record("qr.created", actor=actor, organization=organization, target=qr,
           changes={"type": qr_type, "mode": mode}, request=request)
    return qr


@transaction.atomic
def update_qr(*, qr: QRCode, actor, name: str, payload: dict, style: QRStyle, logo_file=None,
              remove_logo=False, upload=None, folder=None, tags=(), expires_at=None,
              request=None) -> QRCode:
    changed_content = payload != qr.payload
    qr.name, qr.payload, qr.style = name.strip(), payload, style.to_dict()
    qr.folder, qr.expires_at = folder, expires_at
    if remove_logo:
        qr.logo = None
    elif logo_file:
        qr.logo = logo_file
    qr.save()
    check_design(qr.encoded_content, style, qr.logo_bytes())
    if upload is not None:
        _attach_file(qr, upload, actor)
    qr.tags.set(resolve_tags(qr.organization, list(tags)))
    from .redirect_cache import invalidate

    invalidate(qr)
    record("qr.updated", actor=actor, organization=qr.organization, target=qr,
           changes={"content_changed": changed_content}, request=request)
    return qr


def set_status(*, qr: QRCode, actor, status: str, request=None) -> None:
    if qr.status == QRCode.Status.SUSPENDED:
        raise QRError(_("This QR code was suspended by Qrumy and cannot be changed."))
    if status not in (QRCode.Status.ACTIVE, QRCode.Status.PAUSED):
        raise QRError(_("Invalid status."))
    if qr.status == status:
        return
    qr.status = status
    qr.save(update_fields=["status", "updated_at"])
    from .redirect_cache import invalidate

    invalidate(qr)
    record(f"qr.{status}", actor=actor, organization=qr.organization, target=qr,
           request=request)


def delete_qr(*, qr: QRCode, actor, request=None) -> None:
    """Soft delete: the short code is retired forever (never reissued)."""
    qr.deleted_at = timezone.now()
    qr.save(update_fields=["deleted_at", "updated_at"])
    from .redirect_cache import invalidate

    invalidate(qr)
    record("qr.deleted", actor=actor, organization=qr.organization, target=qr, request=request)


def suspend_qr(*, qr: QRCode, actor, reason: str, request=None) -> None:
    """Staff action for abusive codes."""
    qr.status = QRCode.Status.SUSPENDED
    qr.suspended_reason = reason[:255]
    qr.save(update_fields=["status", "suspended_reason", "updated_at"])
    from .redirect_cache import invalidate

    invalidate(qr)
    record("admin.qr.suspended", actor=actor, organization=qr.organization, target=qr,
           changes={"reason": reason}, request=request)
