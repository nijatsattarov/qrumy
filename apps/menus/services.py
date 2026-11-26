from datetime import timedelta

from django.db import transaction
from django.db.models import F, Max, Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.audit_logs.services import record
from apps.core import quotas

from .models import Menu, MenuCategory, MenuItem, MenuItemOption, MenuStat

MENUS_FEATURE = "menus.max"
MAX_CATEGORIES = 60
MAX_ITEMS = 600


class MenuError(Exception):
    pass


# ----------------------------------------------------------------------------- menus
def create_menu(*, organization, actor, data: dict, request=None) -> Menu:
    try:
        quotas.check(organization, MENUS_FEATURE, Menu.objects.for_org(organization).count())
    except quotas.QuotaExceeded as exc:
        raise MenuError(_("Your plan allows up to %(limit)s menus.") % {"limit": exc.limit}) \
            from exc
    menu = Menu.objects.create(organization=organization, created_by=actor, **data)
    record("menu.created", actor=actor, organization=organization, target=menu, request=request)
    return menu


def set_published(*, menu, actor, published: bool, request=None) -> None:
    menu.is_published = published
    menu.save(update_fields=["is_published", "updated_at"])
    if published:
        ensure_qr(menu=menu, actor=actor, request=request)
    record("menu.published" if published else "menu.unpublished", actor=actor,
           organization=menu.organization, target=menu, request=request)


def ensure_qr(*, menu, actor, request=None):
    from apps.qr_management import services as qr_services
    from apps.qr_management.engine import QRStyle

    if menu.qr_code_id and menu.qr_code.deleted_at is None:
        return menu.qr_code
    try:
        qr = qr_services.create_qr(
            organization=menu.organization, actor=actor, qr_type="digital_menu",
            mode="dynamic", name=f"{_('Menu')} · {menu.name}"[:120],
            payload={"menu_token": menu.public_token, "menu_name": menu.name},
            style=QRStyle(frame="bottom", cta_text=_("Scan for menu")[:30]), request=request)
    except qr_services.QRError as exc:
        raise MenuError(str(exc)) from exc
    menu.qr_code = qr
    menu.save(update_fields=["qr_code", "updated_at"])
    return qr


def delete_menu(*, menu, actor, request=None) -> None:
    from apps.qr_management import services as qr_services

    if menu.qr_code_id and menu.qr_code.deleted_at is None and menu.qr_code.status == "active":
        qr_services.set_status(qr=menu.qr_code, actor=actor, status="paused", request=request)
    record("menu.deleted", actor=actor, organization=menu.organization,
           changes={"name": menu.name}, request=request)
    for item in menu.items.exclude(image=""):
        item.image.delete(save=False)
    for field in (menu.logo, menu.cover):
        if field:
            field.delete(save=False)
    menu.delete()


# ------------------------------------------------------------------------ categories
def _next_position(qs) -> int:
    return (qs.aggregate(m=Max("position"))["m"] or 0) + 1


def add_category(*, menu, name: str, description: str = "") -> MenuCategory:
    if menu.categories.count() >= MAX_CATEGORIES:
        raise MenuError(_("A menu can have up to %(n)s categories.") % {"n": MAX_CATEGORIES})
    return MenuCategory.objects.create(organization=menu.organization, menu=menu,
                                       name=name.strip()[:80], description=description[:200],
                                       position=_next_position(menu.categories))


@transaction.atomic
def move(obj, siblings, direction: str) -> None:
    """Swap an item/category with its neighbour (direction: "up" | "down")."""
    ordered = list(siblings.order_by("position", "pk"))
    for i, o in enumerate(ordered):  # normalise positions first
        if o.position != i:
            type(o).objects.filter(pk=o.pk).update(position=i)
            o.position = i
    idx = next(i for i, o in enumerate(ordered) if o.pk == obj.pk)
    other = idx - 1 if direction == "up" else idx + 1
    if 0 <= other < len(ordered):
        a, b = ordered[idx], ordered[other]
        type(a).objects.filter(pk=a.pk).update(position=b.position)
        type(b).objects.filter(pk=b.pk).update(position=a.position)


# ----------------------------------------------------------------------------- items
def save_item(*, menu, form, options: list[dict]) -> MenuItem:
    item = form.save(commit=False)
    if item.pk is None:
        if menu.items.count() >= MAX_ITEMS:
            raise MenuError(_("A menu can have up to %(n)s items.") % {"n": MAX_ITEMS})
        item.menu, item.organization = menu, menu.organization
        item.position = _next_position(menu.items.filter(category=item.category))
    item.save()
    item.options.all().delete()
    MenuItemOption.objects.bulk_create([
        MenuItemOption(organization=menu.organization, item=item, kind=o["kind"],
                       name=o["name"], price=o["price"], position=i)
        for i, o in enumerate(options)])
    menu.save(update_fields=["updated_at"])
    return item


def delete_item(*, item) -> None:
    if item.image:
        item.image.delete(save=False)
    item.delete()


# ----------------------------------------------------------------------------- stats
def count(menu, kind: str, object_id: int = 0) -> None:
    today = timezone.localdate()
    updated = MenuStat.objects.filter(menu=menu, day=today, kind=kind,
                                      object_id=object_id).update(count=F("count") + 1)
    if not updated:
        obj, created = MenuStat.objects.get_or_create(menu=menu, day=today, kind=kind,
                                                      object_id=object_id,
                                                      defaults={"count": 1})
        if not created:
            MenuStat.objects.filter(pk=obj.pk).update(count=F("count") + 1)


def report(menu, days: int = 30) -> dict:
    since = timezone.localdate() - timedelta(days=days - 1)
    stats = MenuStat.objects.filter(menu=menu, day__gte=since)
    views = {r["day"]: r["n"] for r in stats.filter(kind="view").values("day")
             .annotate(n=Sum("count"))}
    series = [{"day": since + timedelta(days=i), "views": views.get(since + timedelta(days=i), 0)}
              for i in range(days)]

    def top(kind, model):
        rows = list(stats.filter(kind=kind).values("object_id").annotate(n=Sum("count"))
                    .order_by("-n")[:10])
        names = dict(model.objects.filter(pk__in=[r["object_id"] for r in rows])
                     .values_list("pk", "name"))
        return [{"name": names[r["object_id"]], "count": r["n"]} for r in rows
                if r["object_id"] in names]

    total_views = sum(views.values())
    peak = max(series, key=lambda s: s["views"]) if total_views else None
    return {"series": series, "views": total_views, "peak": peak,
            "top_items": top("item", MenuItem), "top_categories": top("category", MenuCategory),
            "max_views": max([s["views"] for s in series] or [0]),
            "chart_values": [s["views"] for s in series],
            "chart_labels": [s["day"].strftime("%d.%m") for s in series]}
