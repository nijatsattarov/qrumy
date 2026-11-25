"""Read-side queries over daily rollups (never over raw scans)."""

from dataclasses import dataclass
from datetime import date, timedelta

from django.db.models import Sum

from .models import ScanDaily


@dataclass
class Period:
    start: date
    end: date  # inclusive

    @classmethod
    def last_days(cls, days: int, today: date | None = None) -> "Period":
        today = today or date.today()
        return cls(today - timedelta(days=days - 1), today)

    @property
    def days(self) -> list[date]:
        n = (self.end - self.start).days + 1
        return [self.start + timedelta(days=i) for i in range(n)]


def _base(organization, period: Period, qr_code=None):
    qs = ScanDaily.objects.filter(organization=organization, day__gte=period.start,
                                  day__lte=period.end)
    return qs.filter(qr_code=qr_code) if qr_code is not None else qs


def totals(organization, period: Period, qr_code=None) -> dict:
    agg = _base(organization, period, qr_code).filter(dimension="total").aggregate(
        scans=Sum("scans"), unique=Sum("unique_scans"))
    return {"scans": agg["scans"] or 0, "unique": agg["unique"] or 0}


def timeseries(organization, period: Period, qr_code=None) -> list[dict]:
    rows = dict(_base(organization, period, qr_code).filter(dimension="total")
                .values("day").annotate(n=Sum("scans")).values_list("day", "n"))
    return [{"day": d, "scans": rows.get(d, 0)} for d in period.days]


def breakdown(organization, period: Period, dimension: str, qr_code=None,
              limit: int = 8) -> list[dict]:
    rows = list(_base(organization, period, qr_code).filter(dimension=dimension)
                .values("value").annotate(scans=Sum("scans")).order_by("-scans", "value"))
    total = sum(r["scans"] for r in rows) or 1
    out = [{"value": r["value"], "scans": r["scans"], "pct": round(r["scans"] * 100 / total)}
           for r in rows[:limit]]
    rest = sum(r["scans"] for r in rows[limit:])
    if rest:
        out.append({"value": "", "other": True, "scans": rest, "pct": round(rest * 100 / total)})
    return out


def top_codes(organization, period: Period, limit: int = 5) -> list[dict]:
    return list(_base(organization, period).filter(dimension="total")
                .values("qr_code_id", "qr_code__name").annotate(scans=Sum("scans"))
                .order_by("-scans")[:limit])


def export_rows(organization, period: Period, qr_code=None):
    """Daily rows for CSV export: day, qr, dimension, value, scans, unique."""
    return (_base(organization, period, qr_code).select_related("qr_code")
            .order_by("day", "qr_code_id", "dimension", "value"))
