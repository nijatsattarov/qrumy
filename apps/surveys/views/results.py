from django.shortcuts import get_object_or_404, render

from apps.organizations.permissions import require_capability, require_module

from .. import stats
from ..models import Survey

PERIODS = [(7, "7"), (30, "30"), (90, "90"), (0, "all")]


@require_module("surveys")
@require_capability("analytics.view")
def survey_results(request, org_slug, pk):
    survey = get_object_or_404(Survey.objects.for_org(request.organization), pk=pk)
    try:
        days = int(request.GET.get("days", 30))
    except ValueError:
        days = 30
    days = days if days in (7, 30, 90, 0) else 30
    period = days or None
    return render(request, "surveys/results.html", {
        "survey": survey, "days": days,
        "summary": stats.summary(survey, period),
        "trend": stats.trend(survey, days or 90),
        "questions": [stats.question_stats(q, period) for q in survey.questions.all()],
    })
