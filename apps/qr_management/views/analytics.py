import csv

from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.analytics import reports
from apps.organizations.permissions import require_capability, require_module

from ..models import QRCode
from .codes import BREAKDOWNS, PERIODS


def _days(request) -> int:
    try:
        days = int(request.GET.get("days", 30))
    except ValueError:
        return 30
    return days if days in (7, 30, 90, 365) else 30


@require_module("qr")
@require_capability("analytics.view")
def analytics_overview(request, org_slug):
    org = request.organization
    days = _days(request)
    period = reports.Period.last_days(days)
    return render(request, "qr_management/analytics.html", {
        "days": days, "totals": reports.totals(org, period),
        "series": reports.timeseries(org, period),
        "top": reports.top_codes(org, period, limit=10),
        "breakdowns": [(dim, label, reports.breakdown(org, period, dim))
                       for dim, label in BREAKDOWNS],
        "periods": PERIODS,
        "dynamic_count": QRCode.objects.for_org(org).live().filter(mode="dynamic").count(),
    })


@require_module("qr")
@require_capability("analytics.view")
def analytics_export(request, org_slug, pk=None):
    org = request.organization
    qr = get_object_or_404(QRCode.objects.for_org(org), pk=pk) if pk else None
    period = reports.Period.last_days(_days(request))
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = (
        f'attachment; filename="qrumy-scans-{period.start}-{period.end}.csv"')
    resp.write("﻿")  # Excel-friendly UTF-8
    writer = csv.writer(resp)
    writer.writerow(["date", "qr_code", "short_code", "dimension", "value", "scans",
                     "unique_scans"])
    for row in reports.export_rows(org, period, qr):
        name = row.qr_code.name
        if name[:1] in ("=", "+", "-", "@"):  # CSV formula injection guard
            name = "'" + name
        writer.writerow([row.day.isoformat(), name, row.qr_code.short_code, row.dimension,
                         row.value, row.scans, row.unique_scans])
    return resp
