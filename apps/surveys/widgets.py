from datetime import timedelta

from django.utils import timezone

from apps.core.widgets import Widget
from apps.core.widgets import register as register_widget
from apps.organizations.permissions import can, module_enabled

from . import scoring
from .models import Response, Survey


def _context(request):
    org = request.organization
    since = timezone.now() - timedelta(days=30)
    recent = Response.objects.for_org(org).filter(submitted_at__gte=since)
    nps_values = list(recent.exclude(nps__isnull=True).values_list("nps", flat=True))
    return {
        "survey_count": Survey.objects.for_org(org).count(),
        "responses_30d": recent.count(),
        "open_count": Response.objects.for_org(org).filter(status="open").count(),
        "nps": scoring.nps(nps_values),
        "latest": Response.objects.for_org(org).select_related("survey")[:4],
    }


def register() -> None:
    register_widget(Widget("surveys", "surveys/widgets/overview.html", _context, order=20,
                           visible=lambda r: module_enabled(r, "surveys")
                           and can(r, "content.view")))
