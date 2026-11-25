"""Super-admin dashboard (Django Admin index): platform-wide numbers for staff.

Lives in core and reaches other modules through ``apps.get_model`` only, so it does not
break the layer rules. Every figure is a cheap aggregate query.
"""

import json
from datetime import timedelta

from django.apps import apps
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import number_format
from django.utils.translation import gettext as _


def _model(label: str):
    try:
        return apps.get_model(label)
    except LookupError:
        return None


def _series(qs, field: str, days: int, value=None) -> tuple[list[str], list[int]]:
    start = timezone.localdate() - timedelta(days=days - 1)
    if value is None:
        rows = (qs.filter(**{f"{field}__date__gte": start}).annotate(d=TruncDate(field))
                .values("d").annotate(n=Count("pk")))
    else:
        rows = qs.filter(**{f"{field}__gte": start}).values(d=F(field)).annotate(n=Sum(value))
    by_day = {r["d"]: r["n"] or 0 for r in rows}
    labels, data = [], []
    for i in range(days):
        d = start + timedelta(days=i)
        labels.append(d.strftime("%d.%m"))
        data.append(by_day.get(d, 0))
    return labels, data


def _chart(labels, data, label) -> str:
    return json.dumps({"labels": labels, "datasets": [{
        "label": label, "data": data, "backgroundColor": "var(--color-primary-600)"}]})


def _admin_url(label: str) -> str:
    app, model = label.lower().split(".")
    try:
        return reverse(f"admin:{app}_{model}_changelist")
    except Exception:  # noqa: BLE001 — model not registered in the admin
        return ""


def _fmt(n) -> str:
    return number_format(n or 0, force_grouping=True)


def dashboard_callback(request, context):
    now = timezone.now()
    d7, d30 = now - timedelta(days=7), now - timedelta(days=30)
    User = _model("accounts.User")
    Org = _model("organizations.Organization")
    QR = _model("qr_management.QRCode")
    ScanDaily = _model("analytics.ScanDaily")
    Survey, Response = _model("surveys.Survey"), _model("surveys.Response")
    Asset, Fault = _model("assets.Asset"), _model("assets.FaultReport")
    Subscription = _model("subscriptions.Subscription")

    users = User.objects.aggregate(
        total=Count("pk"), new7=Count("pk", filter=Q(date_joined__gte=d7)),
        new30=Count("pk", filter=Q(date_joined__gte=d30)))
    orgs = Org.objects.aggregate(total=Count("pk"),
                                 new30=Count("pk", filter=Q(created_at__gte=d30)))
    qrs = QR.objects.filter(deleted_at__isnull=True).aggregate(
        total=Count("pk"), dynamic=Count("pk", filter=Q(mode="dynamic")),
        new30=Count("pk", filter=Q(created_at__gte=d30)))
    totals = ScanDaily.objects.filter(dimension="total")
    scans_all = totals.aggregate(n=Sum("scans"))["n"] or 0
    scans_30 = totals.filter(day__gte=timezone.localdate() - timedelta(days=29)).aggregate(
        n=Sum("scans"))["n"] or 0

    kpis = [
        {"title": _("Registered users"), "value": _fmt(users["total"]),
         "note": _("+%(a)s in 7 days · +%(b)s in 30 days") % {
             "a": _fmt(users["new7"]), "b": _fmt(users["new30"])},
         "href": _admin_url("accounts.User"), "icon": "group"},
        {"title": _("Organizations"), "value": _fmt(orgs["total"]),
         "note": _("+%(n)s in 30 days") % {"n": _fmt(orgs["new30"])},
         "href": _admin_url("organizations.Organization"), "icon": "apartment"},
        {"title": _("QR codes created"), "value": _fmt(qrs["total"]),
         "note": _("%(d)s dynamic · +%(n)s in 30 days") % {
             "d": _fmt(qrs["dynamic"]), "n": _fmt(qrs["new30"])},
         "href": _admin_url("qr_management.QRCode"), "icon": "qr_code_2"},
        {"title": _("QR scans"), "value": _fmt(scans_all),
         "note": _("%(n)s in the last 30 days") % {"n": _fmt(scans_30)},
         "href": "", "icon": "bar_chart"},
    ]
    if Survey is not None:
        kpis.append({"title": _("Surveys"), "value": _fmt(Survey.objects.count()),
                     "note": _("%(n)s responses") % {"n": _fmt(Response.objects.count())},
                     "href": _admin_url("surveys.Survey"), "icon": "forum"})
    if Asset is not None:
        open_faults = Fault.objects.filter(status__in=Fault.OPEN_STATUSES).count()
        kpis.append({"title": _("Assets"), "value": _fmt(Asset.objects.count()),
                     "note": _("%(n)s open fault reports") % {"n": _fmt(open_faults)},
                     "href": _admin_url("assets.Asset"), "icon": "inventory_2"})

    # Revenue. Online payments are not connected yet (free beta): nothing has been charged,
    # so we show paid subscriptions and their expected monthly value instead of inventing
    # payment figures.
    current = Subscription.objects.filter(status__in=Subscription.CURRENT_STATUSES)
    paid = current.exclude(plan__price_monthly_cents=0, plan__price_yearly_cents=0)
    mrr_cents = 0
    for interval, monthly, yearly in paid.values_list(
            "interval", "plan__price_monthly_cents", "plan__price_yearly_cents"):
        mrr_cents += round(yearly / 12) if interval == "year" else monthly
    plans = list(current.values("plan__name").annotate(n=Count("pk")).order_by("-n"))
    revenue = {
        "paid": _fmt(paid.count()),
        "mrr": number_format(mrr_cents / 100, decimal_pos=2, force_grouping=True),
        "plans": plans,
        "payments": _("No payments yet — online payments are not enabled during the free "
                      "beta. Paid plans assigned by staff are counted above."),
    }

    labels, signups = _series(User.objects.all(), "date_joined", 30)
    scans = _series(totals, "day", 30, value="scans")[1]
    recent = [[u.email, u.full_name or "—", u.date_joined.strftime("%d.%m.%Y %H:%M")]
              for u in User.objects.order_by("-date_joined")[:8]]
    top = [[r["organization__name"], r["n"]] for r in
           QR.objects.filter(deleted_at__isnull=True).values("organization__name")
           .annotate(n=Count("pk")).order_by("-n")[:8]]

    context.update({
        "kpis": kpis,
        "revenue": revenue,
        "signup_chart": _chart(labels, signups, _("Sign-ups")),
        "scan_chart": _chart(labels, scans, _("Scans")),
        "recent_users": {"headers": [_("Email"), _("Name"), _("Joined")], "rows": recent},
        "top_orgs": {"headers": [_("Organization"), _("QR codes")], "rows": top},
    })
    return context
