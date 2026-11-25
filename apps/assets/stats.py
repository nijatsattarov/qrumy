from datetime import timedelta

from django.db.models import Count, Sum
from django.utils import timezone

from .models import Asset, FaultReport, MaintenanceRecord


def overview(organization) -> dict:
    assets = Asset.objects.for_org(organization)
    by_status = dict(assets.values_list("status").annotate(n=Count("id")))
    year_ago = timezone.now().date() - timedelta(days=365)
    faults = FaultReport.objects.for_org(organization)
    since = timezone.now() - timedelta(days=90)
    return {
        "total": assets.count(),
        "by_status": by_status,
        "attention": by_status.get("broken", 0) + by_status.get("maintenance", 0),
        "open_faults": faults.filter(status__in=FaultReport.OPEN_STATUSES).count(),
        "urgent_faults": faults.filter(status__in=FaultReport.OPEN_STATUSES,
                                       priority__in=["high", "urgent"]).count(),
        "cost_12m": MaintenanceRecord.objects.for_org(organization)
        .filter(performed_on__gte=year_ago).aggregate(s=Sum("cost"))["s"] or 0,
        "warranty_soon": assets.filter(warranty_expires_at__gte=timezone.now().date(),
                                       warranty_expires_at__lte=timezone.now().date()
                                       + timedelta(days=60)).count(),
        "top_faulty": list(faults.filter(created_at__gte=since).values(
            "asset_id", "asset__name", "asset__asset_code").annotate(n=Count("id"))
            .order_by("-n")[:5]),
        "fault_categories": list(faults.filter(created_at__gte=since).values("category")
                                 .annotate(n=Count("id")).order_by("-n")),
    }
