from django.db.models import F
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.audit_logs.services import record
from apps.core import quotas

from .models import MAX_GALLERY, Card, CardDaily, CardPhoto

CARDS_FEATURE = "cards.max"


class CardError(Exception):
    pass


def create_card(*, organization, actor, data: dict, request=None) -> Card:
    try:
        quotas.check(organization, CARDS_FEATURE, Card.objects.for_org(organization).count())
    except quotas.QuotaExceeded as exc:
        raise CardError(_("Your plan allows up to %(limit)s cards.") % {"limit": exc.limit}) \
            from exc
    card = Card.objects.create(organization=organization, created_by=actor, **data)
    record("card.created", actor=actor, organization=organization, target=card, request=request)
    return card


def save_step(*, card, actor, form, request=None) -> Card:
    card = form.save()
    record("card.updated", actor=actor, organization=card.organization, target=card,
           changes={"fields": sorted(form.changed_data)[:20]}, request=request)
    return card


def set_published(*, card, actor, published: bool, request=None) -> None:
    card.is_published = published
    card.save(update_fields=["is_published", "updated_at"])
    if published:
        ensure_qr(card=card, actor=actor, request=request)
    record("card.published" if published else "card.unpublished", actor=actor,
           organization=card.organization, target=card, request=request)


def ensure_qr(*, card, actor, request=None):
    from apps.qr_management import services as qr_services
    from apps.qr_management.engine import QRStyle

    if card.qr_code_id and card.qr_code.deleted_at is None:
        return card.qr_code
    try:
        qr = qr_services.create_qr(
            organization=card.organization, actor=actor, qr_type="card", mode="dynamic",
            name=f"Qrumy Card · {card.name}"[:120],
            payload={"card_token": card.public_token, "card_name": card.name},
            style=QRStyle(module_shape="rounded", eye_frame="rounded", eye_ball="rounded"),
            request=request)
    except qr_services.QRError as exc:
        raise CardError(str(exc)) from exc
    card.qr_code = qr
    card.save(update_fields=["qr_code", "updated_at"])
    return qr


def delete_card(*, card, actor, request=None) -> None:
    from apps.qr_management import services as qr_services

    if card.qr_code_id and card.qr_code.deleted_at is None and card.qr_code.status == "active":
        qr_services.set_status(qr=card.qr_code, actor=actor, status="paused", request=request)
    record("card.deleted", actor=actor, organization=card.organization,
           changes={"name": card.name}, request=request)
    for photo in card.photos.all():
        photo.image.delete(save=False)
    for field in (card.photo, card.cover):
        if field:
            field.delete(save=False)
    card.delete()


def add_photo(*, card, upload, caption: str = "") -> CardPhoto:
    if card.photos.count() >= MAX_GALLERY:
        raise CardError(_("A card can have up to %(n)s gallery photos.") % {"n": MAX_GALLERY})
    last = card.photos.order_by("-position").values_list("position", flat=True).first() or 0
    return CardPhoto.objects.create(organization=card.organization, card=card, image=upload,
                                    caption=caption[:120], position=last + 1)


def delete_photo(*, photo) -> None:
    photo.image.delete(save=False)
    photo.delete()


def count(card, field: str) -> None:
    """Add one view / save / click to today's counters (atomic upsert)."""
    assert field in ("views", "saves", "clicks")
    today = timezone.localdate()
    updated = CardDaily.objects.filter(card=card, day=today).update(**{field: F(field) + 1})
    if not updated:
        obj, created = CardDaily.objects.get_or_create(card=card, day=today,
                                                       defaults={field: 1})
        if not created:
            CardDaily.objects.filter(pk=obj.pk).update(**{field: F(field) + 1})


def stats(card, days: int = 30) -> dict:
    from django.db.models import Sum

    since = timezone.localdate() - timezone.timedelta(days=days - 1)
    rows = {r.day: r for r in card.daily.filter(day__gte=since)}
    series = []
    for i in range(days):
        d = since + timezone.timedelta(days=i)
        series.append({"day": d, "views": rows[d].views if d in rows else 0})
    totals = card.daily.aggregate(views=Sum("views"), saves=Sum("saves"), clicks=Sum("clicks"))
    recent = card.daily.filter(day__gte=since).aggregate(
        views=Sum("views"), saves=Sum("saves"), clicks=Sum("clicks"))
    return {"series": series, "total": {k: v or 0 for k, v in totals.items()},
            "recent": {k: v or 0 for k, v in recent.items()}}


def vcard(card) -> str:
    """vCard 3.0 for "Save contact"."""
    def esc(value: str) -> str:
        return (value or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,") \
            .replace("\n", "\\n")

    lines = ["BEGIN:VCARD", "VERSION:3.0"]
    if card.kind == Card.Kind.COMPANY:
        lines += [f"FN:{esc(card.name)}", f"ORG:{esc(card.name)}", "N:;;;;"]
    else:
        parts = card.name.split()
        last, first = (parts[-1], " ".join(parts[:-1])) if len(parts) > 1 else ("", card.name)
        lines += [f"FN:{esc(card.name)}", f"N:{esc(last)};{esc(first)};;;"]
        if card.company:
            lines.append(f"ORG:{esc(card.company)}")
    if card.headline:
        lines.append(f"TITLE:{esc(card.headline)}")
    for phone in (card.phone, card.phone_2):
        if phone:
            lines.append(f"TEL;TYPE=CELL:{esc(phone)}")
    if card.email:
        lines.append(f"EMAIL;TYPE=INTERNET:{esc(card.email)}")
    if card.website:
        lines.append(f"URL:{esc(card.website)}")
    lines.append(f"URL;TYPE=Qrumy:{esc(card.public_url)}")
    if card.address:
        lines.append(f"ADR;TYPE=WORK:;;{esc(card.address)};;;;")
    if card.about:
        lines.append(f"NOTE:{esc(card.about[:500])}")
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"
