import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.organizations.permissions import require_capability, require_module

from .. import services
from ..forms import ResponseFilterForm
from ..models import Response, ResponseTag, Survey


def _survey(request, pk):
    return get_object_or_404(Survey.objects.for_org(request.organization), pk=pk)


def _response(request, survey, rid):
    return get_object_or_404(Response.objects.for_org(request.organization), pk=rid,
                             survey=survey)


def _members(request):
    return get_user_model().objects.filter(
        memberships__organization=request.organization).order_by("full_name", "email")


def _filtered(request, survey):
    qs = (Response.objects.for_org(request.organization).filter(survey=survey)
          .select_related("assigned_to").prefetch_related("tags"))
    form = ResponseFilterForm(request.GET)
    if not form.is_valid():
        return qs, form
    d = form.cleaned_data
    if d["q"]:
        qs = qs.filter(Q(answers__value_text__icontains=d["q"]) |
                       Q(notes__body__icontains=d["q"]) |
                       Q(contact_email__icontains=d["q"]) |
                       Q(contact_name__icontains=d["q"])).distinct()
    if d["status"]:
        qs = qs.filter(status=d["status"])
    score = d["score"]
    if score == "promoters":
        qs = qs.filter(nps__gte=9)
    elif score == "passives":
        qs = qs.filter(nps__gte=7, nps__lte=8)
    elif score == "detractors":
        qs = qs.filter(nps__lte=6)
    elif score == "unsatisfied":
        qs = qs.filter(csat__lte=2)
    if d["assigned"] == "me":
        qs = qs.filter(assigned_to=request.user)
    elif d["assigned"] == "none":
        qs = qs.filter(assigned_to__isnull=True)
    if d["tag"]:
        qs = qs.filter(tags__name__iexact=d["tag"])
    if d["days"]:
        qs = qs.filter(submitted_at__gte=timezone.now() - timedelta(days=d["days"]))
    return qs, form


@require_module("surveys")
@require_capability("content.view")
def response_list(request, org_slug, pk):
    survey = _survey(request, pk)
    qs, form = _filtered(request, survey)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    first_text = next((q for q in survey.questions.all() if q.type_def.stats == "text"), None)
    previews = {}
    if first_text:
        for a in first_text.answers.filter(response__in=page.object_list):
            previews[a.response_id] = a.value_text
    for r in page.object_list:
        r.preview = previews.get(r.pk, "")
    template = "surveys/responses.html"
    if request.htmx and request.htmx.target == "response-results":
        template += "#results"
    return render(request, template, {
        "survey": survey, "page": page, "filters": request.GET, "form": form,
        "tags": ResponseTag.objects.for_org(request.organization)[:50]})


@require_module("surveys")
@require_capability("content.view")
def response_detail(request, org_slug, pk, rid):
    survey = _survey(request, pk)
    r = _response(request, survey, rid)
    answers = {a.question_id: a for a in r.answers.all()}
    rows = [(q, answers.get(q.pk)) for q in survey.questions.all()]
    ids = list(Response.objects.filter(survey=survey).values_list("pk", flat=True))
    i = ids.index(r.pk)
    return render(request, "surveys/response_detail.html", {
        "survey": survey, "r": r, "rows": rows, "notes": r.notes.select_related("author"),
        "members": _members(request), "tag_names": ", ".join(t.name for t in r.tags.all()),
        "newer": ids[i - 1] if i > 0 else None, "older": ids[i + 1] if i + 1 < len(ids) else None,
    })


@require_module("surveys")
@require_capability("content.edit")
@require_POST
def response_action(request, org_slug, pk, rid):
    survey = _survey(request, pk)
    r = _response(request, survey, rid)
    action = request.POST.get("action")
    if action == "assign":
        uid = request.POST.get("user")
        user = _members(request).filter(pk=uid).first() if uid else None
        services.assign(response=r, actor=request.user, user=user, request=request)
        messages.success(request, _("Assignment updated."))
    elif action in ("resolve", "reopen"):
        services.set_status(response=r, actor=request.user,
                            status="resolved" if action == "resolve" else "open",
                            request=request)
        messages.success(request, _("Response marked as resolved.") if action == "resolve"
                         else _("Response reopened."))
    elif action == "note":
        body = request.POST.get("body", "").strip()
        if body:
            services.add_note(response=r, actor=request.user, body=body[:2000])
            messages.success(request, _("Note added."))
    elif action == "tags":
        services.set_tags(response=r, names=request.POST.get("tags", "").split(","))
        messages.success(request, _("Tags saved."))
    return redirect("survey_response", org_slug=org_slug, pk=pk, rid=rid)


def _cell(value) -> str:
    value = "" if value is None else str(value)
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


@require_module("surveys")
@require_capability("content.view")
def response_export(request, org_slug, pk):
    survey = _survey(request, pk)
    qs, _form = _filtered(request, survey)
    questions = list(survey.questions.all())
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="survey-{survey.pk}-responses.csv"'
    resp.write("﻿")
    w = csv.writer(resp)
    w.writerow(["submitted_at", "source", "status", "assigned_to", "contact_name",
                "contact_email", "tags", *[q.label for q in questions]])
    for r in qs.prefetch_related("answers"):
        answers = {a.question_id: a.display for a in r.answers.all()}
        w.writerow([r.submitted_at.isoformat(), r.source, r.status,
                    r.assigned_to.email if r.assigned_to else "", _cell(r.contact_name),
                    r.contact_email, _cell(", ".join(t.name for t in r.tags.all())),
                    *[_cell(answers.get(q.pk, "")) for q in questions]])
    return resp
