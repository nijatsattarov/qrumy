"""Scan analytics.

* ``Scan``      — one row per scan (raw, retention-limited, no raw IP stored)
* ``ScanDaily`` — daily rollups per QR code and dimension; dashboards read only these
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Scan(models.Model):
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE,
                                     related_name="+")
    qr_code = models.ForeignKey("qr_management.QRCode", on_delete=models.CASCADE,
                                related_name="scans")
    scanned_at = models.DateTimeField(db_index=True)
    ip_hash = models.CharField(max_length=32, blank=True)
    device = models.CharField(max_length=16, blank=True)      # mobile | tablet | desktop | other
    os = models.CharField(max_length=40, blank=True)
    browser = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=2, blank=True)
    region = models.CharField(max_length=80, blank=True)
    city = models.CharField(max_length=80, blank=True)
    referrer = models.CharField(max_length=120, blank=True)   # host only
    utm_source = models.CharField(max_length=80, blank=True)
    utm_medium = models.CharField(max_length=80, blank=True)
    utm_campaign = models.CharField(max_length=80, blank=True)
    is_bot = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("scan")
        verbose_name_plural = _("scans")
        indexes = [
            models.Index(fields=["qr_code", "scanned_at"]),
            models.Index(fields=["organization", "scanned_at"]),
        ]

    def __str__(self) -> str:
        return f"scan {self.qr_code_id} @ {self.scanned_at:%Y-%m-%d %H:%M}"


class ScanDaily(models.Model):
    """dimension: total | device | os | browser | country | city | referrer | source | campaign"""

    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE,
                                     related_name="+")
    qr_code = models.ForeignKey("qr_management.QRCode", on_delete=models.CASCADE,
                                related_name="daily_stats")
    day = models.DateField()
    dimension = models.CharField(max_length=16)
    value = models.CharField(max_length=120, blank=True)
    scans = models.PositiveIntegerField(default=0)
    unique_scans = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["qr_code", "day", "dimension", "value"],
                                               name="analytics_scandaily_unique")]
        indexes = [models.Index(fields=["organization", "dimension", "day"])]

    def __str__(self) -> str:
        return f"{self.day} {self.dimension}={self.value}: {self.scans}"
