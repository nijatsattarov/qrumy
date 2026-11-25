"""Survey business logic. Views call these functions only."""

from django.db import transaction
from django.db.models import F, Max
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from apps.audit_logs.services import record
from apps.core import quotas
from apps.notifications.services import notify
from apps.subscriptions.models import UsageCounter

from .models import Answer, Question, Response, ResponseNote, ResponseTag, Survey, SurveyDailyStat
from .qtypes import DEFAULT_LABELS, get_qtype

SURVEYS_FEATURE = "surveys.max"
RESPONSES_FEATURE = "surveys.responses_month"
RESPONSES_METRIC = "survey.responses"


class SurveyError(Exception):
    pass


def _month() -> str:
    return timezone.now().strftime("%Y-%m")


# ------------------------------------------------------------------ surveys
@transaction.atomic
def create_survey(*, organization, actor, title: str, request=None, **fields) -> Survey:
    try:
        quotas.check(organization, SURVEYS_FEATURE,
                     Survey.objects.for_org(organization).count())
    except quotas.QuotaExceeded as exc:
        raise SurveyError(_("Your plan allows up to %(limit)s surveys.") % {"limit": exc.limit}) \
            from exc
    survey = Survey.objects.create(organization=organization, title=title.strip(),
                                   created_by=actor, **fields)
    # Start with a useful first question so the builder is never empty.
    add_question(survey=survey, qtype="nps")
    record("survey.created", actor=actor, organization=organization, target=survey,
           request=request)
    return survey


def update_settings(*, survey, actor, form, request=None) -> Survey:
    changed = list(form.changed_data)
    survey = form.save()
    if changed:
        record("survey.updated", actor=actor, organization=survey.organization, target=survey,
               changes={"fields": changed}, request=request)
    return survey


def publish(*, survey, actor, request=None) -> None:
    if not survey.questions.exists():
        raise SurveyError(_("Add at least one question before publishing."))
    for q in survey.questions.all():
        if q.type_def.has_options and len(q.options) < 2:
            raise SurveyError(_("“%(q)s” needs at least two options.") % {"q": q.label})
    survey.status = Survey.Status.PUBLISHED
    survey.published_at = survey.published_at or timezone.now()
    survey.save(update_fields=["status", "published_at", "updated_at"])
    record("survey.published", actor=actor, organization=survey.organization, target=survey,
           request=request)


def close(*, survey, actor, request=None) -> None:
    survey.status = Survey.Status.CLOSED
    survey.save(update_fields=["status", "updated_at"])
    record("survey.closed", actor=actor, organization=survey.organization, target=survey,
           request=request)


@transaction.atomic
def delete_survey(*, survey, actor, request=None) -> None:
    if survey.qr_code_id:
        from apps.qr_management import services as qr_services

        qr = survey.qr_code
        if qr.deleted_at is None and qr.status == "active":
            qr_services.set_status(qr=qr, actor=actor, status="paused", request=request)
    record("survey.deleted", actor=actor, organization=survey.organization, target=survey,
           changes={"responses": survey.response_count}, request=request)
    survey.delete()


def ensure_qr(*, survey, actor, request=None):
    """Create (once) the dynamic QR code that opens this survey."""
    from apps.qr_management import services as qr_services
    from apps.qr_management.engine import QRStyle

    if survey.qr_code_id and survey.qr_code.deleted_at is None:
        return survey.qr_code
    try:
        qr = qr_services.create_qr(
            organization=survey.organization, actor=actor, qr_type="survey", mode="dynamic",
            name=(_("Survey: %(title)s") % {"title": survey.title})[:120],
            payload={"survey_token": survey.public_token, "survey_title": survey.title},
            style=QRStyle(frame="bottom", cta_text=_("Share your feedback")[:30]),
            request=request)
    except qr_services.QRError as exc:
        raise SurveyError(str(exc)) from exc
    survey.qr_code = qr
    survey.save(update_fields=["qr_code", "updated_at"])
    return qr


# ------------------------------------------------------------------ questions
def add_question(*, survey, qtype: str) -> Question:
    t = get_qtype(qtype)
    position = (survey.questions.aggregate(m=Max("position"))["m"] or 0) + 1
    # Starter texts are written in the survey's language, not the editor's UI language.
    with translation.override(survey.language):
        config = {}
        if t.has_options:
            config["options"] = [_("Option 1"), _("Option 2"), _("Option 3")]
        label = str(DEFAULT_LABELS.get(qtype, t.label))
    return Question.objects.create(survey=survey, qtype=qtype, position=position, config=config,
                                   label=label, required=qtype in ("nps", "csat", "ces"))


def update_question(*, question, label: str, help_text: str, required: bool,
                    options: list[str] | None = None, low_label: str = "",
                    high_label: str = "") -> Question:
    question.label = label.strip()[:300]
    question.help_text = help_text.strip()[:300]
    question.required = required
    config = dict(question.config)
    if question.type_def.has_options and options is not None:
        config["options"] = options
    if question.type_def.scale:
        config["low_label"], config["high_label"] = low_label[:40], high_label[:40]
    question.config = config
    question.save()
    return question


@transaction.atomic
def move_question(*, question, direction: str) -> None:
    siblings = list(question.survey.questions.order_by("position", "id"))
    i = siblings.index(question)
    j = i - 1 if direction == "up" else i + 1
    if 0 <= j < len(siblings):
        siblings[i], siblings[j] = siblings[j], siblings[i]
    for pos, q in enumerate(siblings, start=1):
        if q.position != pos:
            Question.objects.filter(pk=q.pk).update(position=pos)


def delete_question(*, question) -> None:
    question.delete()


# ------------------------------------------------------------------ public side
def record_view(survey) -> None:
    today = timezone.now().date()
    stat, _created = SurveyDailyStat.objects.get_or_create(survey=survey, day=today)
    SurveyDailyStat.objects.filter(pk=stat.pk).update(views=F("views") + 1)


@transaction.atomic
def submit_response(*, survey: Survey, answers: dict, source: str, language: str,
                    duration: int | None, contact_name="", contact_email="",
                    consent=False) -> Response:
    """Store a complete response. Locks the survey row so limits hold under concurrency."""
    survey = Survey.objects.select_for_update().get(pk=survey.pk)
    if survey.closed_reason():
        raise SurveyError("closed")
    org = survey.organization
    usage, _created = UsageCounter.objects.get_or_create(
        organization=org, metric=RESPONSES_METRIC, period=_month())
    try:
        quotas.check(org, RESPONSES_FEATURE, usage.value)
    except quotas.QuotaExceeded as exc:
        raise SurveyError("quota") from exc

    response = Response.objects.create(
        organization=org, survey=survey, source=source, language=language[:8],
        duration_seconds=duration, contact_name=contact_name[:120],
        contact_email=contact_email, consent=bool(consent),
        consent_text=survey.consent_text if consent else "")
    rows = []
    for question, value in answers.items():
        cols = question.type_def.to_answer(value)
        if not cols:
            continue
        rows.append(Answer(response=response, question=question, **cols))
        if question.qtype == "nps" and response.nps is None:
            response.nps = int(cols["value_number"])
        if question.qtype == "csat" and response.csat is None:
            response.csat = int(cols["value_number"])
    Answer.objects.bulk_create(rows)
    if response.nps is not None or response.csat is not None:
        response.save(update_fields=["nps", "csat"])
    Survey.objects.filter(pk=survey.pk).update(response_count=F("response_count") + 1)
    UsageCounter.objects.filter(pk=usage.pk).update(value=F("value") + 1)
    return response


# ------------------------------------------------------------------ feedback management
def assign(*, response, actor, user, request=None) -> None:
    response.assigned_to = user
    response.save(update_fields=["assigned_to", "updated_at"])
    record("survey.response_assigned", actor=actor, organization=response.organization,
           target=response, changes={"to": user.email if user else None}, request=request)
    if user and user != actor:
        notify(user, kind="survey.assigned", organization=response.organization,
               title=_("A survey response was assigned to you"), body=response.survey.title,
               url=reverse("survey_response", kwargs={
                   "org_slug": response.organization.slug, "pk": response.survey_id,
                   "rid": response.pk}))


def set_status(*, response, actor, status: str, request=None) -> None:
    if status not in Response.Status.values:
        raise SurveyError(_("Invalid status."))
    response.status = status
    response.resolved_at = timezone.now() if status == Response.Status.RESOLVED else None
    response.save(update_fields=["status", "resolved_at", "updated_at"])
    record(f"survey.response_{status}", actor=actor, organization=response.organization,
           target=response, request=request)


def add_note(*, response, actor, body: str) -> ResponseNote:
    return ResponseNote.objects.create(response=response, author=actor, body=body.strip())


def set_tags(*, response, names: list[str]) -> None:
    org = response.organization
    tags = []
    for name in {n.strip()[:40] for n in names if n.strip()}:
        tag = ResponseTag.objects.for_org(org).filter(name__iexact=name).first()
        tags.append(tag or ResponseTag.objects.create(organization=org, name=name))
    response.tags.set(tags)
