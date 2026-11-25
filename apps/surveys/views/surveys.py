from django.contrib import messages
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.html import escape
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.organizations.permissions import can, require_capability, require_module

from .. import services
from ..forms import QuestionForm, SurveyCreateForm, SurveySettingsForm
from ..models import Question, Survey
from ..qtypes import QTYPES, parse_options


def _surveys(request):
    return Survey.objects.for_org(request.organization)


def _survey(request, pk):
    return get_object_or_404(_surveys(request), pk=pk)


def _question(survey, qid):
    return get_object_or_404(Question, pk=qid, survey=survey)


@require_module("surveys")
@require_capability("content.view")
def survey_list(request, org_slug):
    status = request.GET.get("status", "")
    qs = _surveys(request).annotate(n_questions=Count("questions"),
                                    n_open=Count("responses", filter=Q(responses__status="open")))
    if status in Survey.Status.values:
        qs = qs.filter(status=status)
    return render(request, "surveys/list.html", {"surveys": qs, "status": status,
                                                 "statuses": Survey.Status.choices})


@require_module("surveys")
@require_capability("content.create")
def survey_create(request, org_slug):
    form = SurveyCreateForm(request.POST or None,
                            initial={"language": request.organization.language})
    if request.method == "POST" and form.is_valid():
        try:
            survey = services.create_survey(organization=request.organization,
                                            actor=request.user, request=request,
                                            **form.cleaned_data)
        except services.SurveyError as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("survey_builder", org_slug=org_slug, pk=survey.pk)
    return render(request, "surveys/create.html", {"form": form})


def _builder_ctx(request, survey, focus=None):
    questions = list(survey.questions.all())
    forms = []
    for q in questions:
        initial = {"label": q.label, "help_text": q.help_text, "required": q.required,
                   "options": "\n".join(q.options), "low_label": q.config.get("low_label", ""),
                   "high_label": q.config.get("high_label", "")}
        forms.append((q, QuestionForm(initial=initial, prefix=f"q{q.pk}")))
    return {"survey": survey, "question_forms": forms, "qtypes": QTYPES.values(),
            "focus": focus, "editable": can(request, "content.edit")}


def _questions_response(request, survey, focus=None):
    template = "surveys/builder.html"
    if request.htmx:
        template += "#questions"
    return render(request, template, _builder_ctx(request, survey, focus))


@require_module("surveys")
@require_capability("content.view")
def survey_builder(request, org_slug, pk):
    return render(request, "surveys/builder.html", _builder_ctx(request, _survey(request, pk)))


@require_module("surveys")
@require_capability("content.edit")
@require_POST
def question_add(request, org_slug, pk):
    survey = _survey(request, pk)
    qtype = request.POST.get("qtype", "")
    if qtype not in QTYPES:
        raise Http404
    q = services.add_question(survey=survey, qtype=qtype)
    return _questions_response(request, survey, focus=q.pk)


@require_module("surveys")
@require_capability("content.edit")
@require_POST
def question_update(request, org_slug, pk, qid):
    survey = _survey(request, pk)
    q = _question(survey, qid)
    form = QuestionForm(request.POST, prefix=f"q{q.pk}")
    if form.is_valid():
        d = form.cleaned_data
        services.update_question(question=q, label=d["label"], help_text=d["help_text"],
                                 required=d["required"], options=parse_options(d["options"]),
                                 low_label=d["low_label"], high_label=d["high_label"])
        if not request.htmx:
            messages.success(request, _("Question saved."))
    elif not request.htmx:
        messages.error(request, _("The question needs a title."))
    if request.htmx:
        return render(request, "surveys/_saved.html", {"ok": form.is_valid()})
    return redirect("survey_builder", org_slug=org_slug, pk=pk)


@require_module("surveys")
@require_capability("content.edit")
@require_POST
def question_move(request, org_slug, pk, qid):
    survey = _survey(request, pk)
    services.move_question(question=_question(survey, qid),
                           direction=request.POST.get("direction", "down"))
    return _questions_response(request, survey)


@require_module("surveys")
@require_capability("content.edit")
@require_POST
def question_delete(request, org_slug, pk, qid):
    survey = _survey(request, pk)
    services.delete_question(question=_question(survey, qid))
    return _questions_response(request, survey)


@require_module("surveys")
@require_capability("content.edit")
def survey_settings(request, org_slug, pk):
    survey = _survey(request, pk)
    form = SurveySettingsForm(request.POST or None, request.FILES or None, instance=survey)
    if request.method == "POST" and form.is_valid():
        services.update_settings(survey=survey, actor=request.user, form=form, request=request)
        messages.success(request, _("Survey settings saved."))
        return redirect("survey_settings", org_slug=org_slug, pk=pk)
    return render(request, "surveys/settings.html", {"survey": survey, "form": form})


@require_module("surveys")
@require_capability("content.edit")
@require_POST
def survey_status(request, org_slug, pk):
    survey = _survey(request, pk)
    action = request.POST.get("action")
    try:
        if action == "publish":
            services.publish(survey=survey, actor=request.user, request=request)
            messages.success(request, _("Survey published. Share it from the Share tab."))
        elif action == "close":
            services.close(survey=survey, actor=request.user, request=request)
            messages.success(request, _("Survey closed. It no longer accepts responses."))
    except services.SurveyError as exc:
        messages.error(request, str(exc))
    next_view = request.POST.get("next_view")
    if next_view not in ("survey_builder", "survey_share", "survey_results"):
        next_view = "survey_builder"
    return redirect(next_view, org_slug=org_slug, pk=pk)


@require_module("surveys")
@require_capability("content.delete")
@require_POST
def survey_delete(request, org_slug, pk):
    survey = _survey(request, pk)
    if request.POST.get("confirm_title", "").strip() != survey.title:
        messages.error(request, _("Type the survey title exactly to confirm deletion."))
        return redirect("survey_settings", org_slug=org_slug, pk=pk)
    services.delete_survey(survey=survey, actor=request.user, request=request)
    messages.success(request, _("Survey and its responses were deleted."))
    return redirect("survey_list", org_slug=org_slug)


@require_module("surveys")
@require_capability("content.view")
def survey_share(request, org_slug, pk):
    survey = _survey(request, pk)
    qr = survey.qr_code if survey.qr_code_id and survey.qr_code.deleted_at is None else None
    svg = None
    if qr:
        from apps.qr_management.engine import QRStyle, render_svg

        svg = render_svg(qr.encoded_content, QRStyle.from_dict(qr.style), qr.logo_bytes())
    embed_url = f"{survey.public_url}/embed"
    return render(request, "surveys/share.html", {
        "survey": survey, "qr": qr, "qr_svg": svg, "embed_url": embed_url,
        "embed_code": f'<iframe src="{embed_url}" title="{escape(survey.title)}" width="100%" '
                      f'height="720" style="border:0;max-width:640px" loading="lazy"></iframe>',
        "email_link": f"{survey.public_url}?src=email",
    })


@require_module("surveys")
@require_capability("content.create")
@require_POST
def survey_create_qr(request, org_slug, pk):
    survey = _survey(request, pk)
    try:
        services.ensure_qr(survey=survey, actor=request.user, request=request)
    except services.SurveyError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, _("QR code created. You can change its design in QR Codes."))
    return redirect("survey_share", org_slug=org_slug, pk=pk)
