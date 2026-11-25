from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .ingest import drain_buffer
from .models import Scan


@shared_task
def process_scan_buffer() -> int:
    total = 0
    while True:  # drain everything that arrived since the last run
        n = drain_buffer()
        total += n
        if n == 0:
            return total


@shared_task
def purge_old_scans() -> int:
    """Raw scans are kept for a limited time; daily rollups are kept."""
    cutoff = timezone.now() - timezone.timedelta(days=settings.QRUMY_SCAN_RETENTION_DAYS)
    deleted, _ = Scan.objects.filter(scanned_at__lt=cutoff).delete()
    return deleted
