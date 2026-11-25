"""Survey analytics computed from answers (per survey, optional period)."""

from collections import Counter
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from . import scoring
from .models import Answer, Response, SurveyDailyStat

SCORE_FN = {"nps": scoring.nps, "csat": scoring.csat, "ces": scoring.ces,
            "stars": scoring.average, "rating": scoring.average}


def _period_filter(qs, field: str, days: int | None):
    if not days:
        return qs
    since = timezone.now() - timedelta(days=days - 1)
    return qs.filter(**{f"{field}__date__gte": since.date()})


def summary(survey, days: int | None = None) -> dict:
    responses = _period_filter(Response.objects.filter(survey=survey), "submitted_at", days)
    total = responses.count()
    views_qs = SurveyDailyStat.objects.filter(survey=survey)
    if days:
        views_qs = views_qs.filter(day__gte=(timezone.now() - timedelta(days=days - 1)).date())
    views = views_qs.aggregate(v=Sum("views"))["v"] or 0
    completion = min(100, round(total * 100 / views)) if views else None
    scores = {}
    for q in survey.questions.all():
        if q.qtype in SCORE_FN and q.qtype not in scores:
            scores[q.qtype] = SCORE_FN[q.qtype](_numbers(q, days))
    return {"responses": total, "views": views, "completion": completion, "scores": scores,
            "open": responses.filter(status="open").count()}


def _numbers(question, days):
    qs = _period_filter(Answer.objects.filter(question=question, value_number__isnull=False),
                        "response__submitted_at", days)
    return [int(v) for v in qs.values_list("value_number", flat=True)]


def trend(survey, days: int = 30) -> list[dict]:
    start = (timezone.now() - timedelta(days=days - 1)).date()
    rows = dict(Response.objects.filter(survey=survey, submitted_at__date__gte=start)
                .annotate(day=TruncDate("submitted_at")).values("day")
                .annotate(n=Count("id")).values_list("day", "n"))
    return [{"day": start + timedelta(days=i), "scans": rows.get(start + timedelta(days=i), 0)}
            for i in range(days)]


def question_stats(question, days: int | None = None) -> dict:
    t = question.type_def
    answers = _period_filter(Answer.objects.filter(question=question), "response__submitted_at",
                             days)
    answered = answers.count()
    out = {"question": question, "type": t, "answered": answered, "kind": t.stats}
    if t.stats in ("choice", "multi"):
        counts = Counter()
        for value_text, value_json in answers.values_list("value_text", "value_json"):
            for v in (value_json or [value_text]):
                counts[v] += 1
        options = question.options + [o for o in counts if o not in question.options]
        out["rows"] = [{"label": o, "count": counts.get(o, 0),
                        "pct": round(counts.get(o, 0) * 100 / answered) if answered else 0}
                       for o in options]
    elif t.stats == "scale":
        values = [int(v) for v in answers.exclude(value_number__isnull=True)
                  .values_list("value_number", flat=True)]
        counts = Counter(values)
        lo, hi = t.scale
        peak = max(counts.values()) if counts else 0
        out["rows"] = [{"label": str(i), "count": counts.get(i, 0),
                        "pct": round(counts.get(i, 0) * 100 / len(values)) if values else 0,
                        "bar": round(counts.get(i, 0) * 100 / peak) if peak else 0}
                       for i in range(lo, hi + 1)]
        fn = SCORE_FN.get(question.qtype, scoring.average)
        out["score"] = fn(values)
    elif t.stats == "yesno":
        yes = answers.filter(value_number=1).count()
        out["rows"] = [
            {"label": "yes", "count": yes, "pct": round(yes * 100 / answered) if answered else 0},
            {"label": "no", "count": answered - yes,
             "pct": round((answered - yes) * 100 / answered) if answered else 0}]
    elif t.stats == "text":
        out["latest"] = list(answers.exclude(value_text="").select_related("response")
                             .order_by("-response__submitted_at")[:8])
    return out
