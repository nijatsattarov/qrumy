import pytest
from django.urls import reverse

from apps.notifications.models import Notification
from apps.qr_management.models import QRCode
from apps.subscriptions.models import FeatureOverride
from apps.surveys import services
from apps.surveys.models import Question, Response, Survey

pytestmark = pytest.mark.django_db


def u(name, org, **kw):
    return reverse(name, kwargs={"org_slug": org.slug, **kw})


def _respond(survey, nps=9, text="Nice", **kw):
    answers = {}
    for q in survey.questions.all():
        if q.qtype == "nps":
            answers[q] = nps
        elif q.qtype == "longtext":
            answers[q] = text
    return services.submit_response(survey=survey, answers=answers, source="link",
                                    language="en", duration=12, **kw)


def test_create_survey_starts_with_nps(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    resp = client.post(u("survey_create", org), {"title": "Guests", "language": "az"})
    survey = Survey.objects.get()
    assert resp["Location"] == u("survey_builder", org, pk=survey.pk)
    q = survey.questions.get()
    assert q.qtype == "nps" and q.required and "tövsiyə" in q.label  # starter text in az


def test_survey_quota(make_org):
    org = make_org()
    FeatureOverride.objects.create(organization=org, feature_key="surveys.max", limit_value=1)
    services.create_survey(organization=org, actor=org.owner, title="One")
    with pytest.raises(services.SurveyError):
        services.create_survey(organization=org, actor=org.owner, title="Two")


def test_builder_add_update_move_delete(client, make_org, make_survey):
    org = make_org()
    survey = make_survey(org, publish=False, qtypes=())
    client.force_login(org.owner)
    client.post(u("survey_question_add", org, pk=survey.pk), {"qtype": "single"},
                HTTP_HX_REQUEST="true")
    single = survey.questions.get(qtype="single")
    assert single.options == ["Option 1", "Option 2", "Option 3"]
    resp = client.post(u("survey_question_update", org, pk=survey.pk, qid=single.pk), {
        f"q{single.pk}-label": "Where did you hear about us?", f"q{single.pk}-required": "on",
        f"q{single.pk}-options": "Instagram\nFriends\ninstagram\n\n"}, HTTP_HX_REQUEST="true")
    assert b"Saved" in resp.content
    single.refresh_from_db()
    assert single.options == ["Instagram", "Friends"] and single.required
    nps = survey.questions.get(qtype="nps")
    client.post(u("survey_question_move", org, pk=survey.pk, qid=single.pk), {"direction": "up"},
                HTTP_HX_REQUEST="true")
    assert list(survey.questions.values_list("qtype", flat=True)) == ["single", "nps"]
    client.post(u("survey_question_delete", org, pk=survey.pk, qid=nps.pk), HTTP_HX_REQUEST="true")
    assert not Question.objects.filter(pk=nps.pk).exists()
    assert client.post(u("survey_question_add", org, pk=survey.pk),
                       {"qtype": "nope"}).status_code == 404


def test_publish_rules(client, make_org, make_survey):
    org = make_org()
    survey = make_survey(org, publish=False, qtypes=())
    survey.questions.all().delete()
    with pytest.raises(services.SurveyError):
        services.publish(survey=survey, actor=org.owner)
    q = services.add_question(survey=survey, qtype="single")
    q.config = {"options": ["Only one"]}
    q.save()
    with pytest.raises(services.SurveyError):
        services.publish(survey=survey, actor=org.owner)
    q.config = {"options": ["A", "B"]}
    q.save()
    services.publish(survey=survey, actor=org.owner)
    assert Survey.objects.get(pk=survey.pk).status == "published"


def test_settings_validation(client, make_org, make_survey):
    org = make_org()
    survey = make_survey(org)
    client.force_login(org.owner)
    data = {"title": "T", "language": "en", "accent_color": "#123456", "contact_mode": "optional",
            "redirect_url": "javascript:alert(1)"}
    resp = client.post(u("survey_settings", org, pk=survey.pk), data)
    assert resp.status_code == 200  # errors: consent text + unsafe redirect
    survey.refresh_from_db()
    assert survey.title == "Feedback"
    data.update(redirect_url="https://example.com/thanks", consent_text="We may email you")
    client.post(u("survey_settings", org, pk=survey.pk), data)
    survey.refresh_from_db()
    assert survey.redirect_url == "https://example.com/thanks" and survey.contact_mode == "optional"


def test_survey_qr_code_opens_survey(client, make_org, make_survey):
    org = make_org()
    survey = make_survey(org)
    client.force_login(org.owner)
    client.post(u("survey_create_qr", org, pk=survey.pk))
    client.post(u("survey_create_qr", org, pk=survey.pk))  # idempotent
    survey.refresh_from_db()
    assert QRCode.objects.filter(qr_type="survey").count() == 1
    resp = client.get(f"/q/{survey.qr_code.short_code}",
                      HTTP_USER_AGENT="Mozilla/5.0 (iPhone; Mobile)")
    assert resp["Location"].endswith(f"/s/{survey.public_token}?src=qr")
    # the survey QR type is not offered in the generic QR picker
    assert b"Open a feedback survey" not in client.get(u("qr_choose_type", org)).content
    assert client.get(u("qr_create", org, type_key="survey")).status_code == 404


def test_delete_requires_title_and_pauses_qr(client, make_org, make_survey):
    org = make_org()
    survey = make_survey(org)
    qr = services.ensure_qr(survey=survey, actor=org.owner)
    client.force_login(org.owner)
    client.post(u("survey_delete", org, pk=survey.pk), {"confirm_title": "wrong"})
    assert Survey.objects.filter(pk=survey.pk).exists()
    client.post(u("survey_delete", org, pk=survey.pk), {"confirm_title": "Feedback"})
    assert not Survey.objects.filter(pk=survey.pk).exists()
    qr.refresh_from_db()
    assert qr.status == "paused"


def test_response_management(client, make_org, make_survey, make_user, add_member):
    org = make_org()
    survey = make_survey(org)
    r = _respond(survey)
    colleague = make_user(email="c@example.com")
    add_member(org, colleague, "member")
    client.force_login(org.owner)
    url = u("survey_response_action", org, pk=survey.pk, rid=r.pk)
    client.post(url, {"action": "assign", "user": colleague.pk})
    client.post(url, {"action": "note", "body": "Called the guest"})
    client.post(url, {"action": "tags", "tags": "service, Service, wait time"})
    client.post(url, {"action": "resolve"})
    r.refresh_from_db()
    assert r.assigned_to == colleague and r.status == "resolved" and r.resolved_at
    assert r.notes.get().body == "Called the guest"
    assert sorted(t.name.lower() for t in r.tags.all()) == ["service", "wait time"]
    assert Notification.objects.filter(user=colleague, kind="survey.assigned").exists()
    outsider = make_user(email="x@example.com")
    client.post(url, {"action": "assign", "user": outsider.pk})  # not a member → unassigned
    r.refresh_from_db()
    assert r.assigned_to is None


def test_response_filters_and_export(client, make_org, make_survey):
    org = make_org()
    survey = make_survey(org, qtypes=("longtext",))
    _respond(survey, nps=10, text="Lovely tea")
    _respond(survey, nps=3, text="=cmd|' /C calc'!A0")
    client.force_login(org.owner)

    def count(**params):
        return client.get(u("survey_responses", org, pk=survey.pk), params).context[
            "page"].paginator.count

    assert count() == 2 and count(score="promoters") == 1 and count(score="detractors") == 1
    assert count(q="lovely") == 1 and count(assigned="none") == 2 and count(status="resolved") == 0
    body = client.get(u("survey_responses_export", org, pk=survey.pk)).content.decode("utf-8-sig")
    assert "'=cmd" in body and "Lovely tea" in body


def test_results_page(client, make_org, make_survey):
    org = make_org()
    survey = make_survey(org)
    _respond(survey, nps=10)
    _respond(survey, nps=0)
    client.force_login(org.owner)
    resp = client.get(u("survey_results", org, pk=survey.pk), {"days": 0})
    assert resp.context["summary"]["scores"]["nps"]["score"] == 0
    assert resp.context["summary"]["responses"] == 2


def test_permissions(client, make_org, make_survey, make_user, add_member):
    org = make_org()
    survey = make_survey(org)
    r = _respond(survey)
    viewer = make_user(email="v@example.com")
    add_member(org, viewer, "viewer")
    client.force_login(viewer)
    assert client.get(u("survey_responses", org, pk=survey.pk)).status_code == 200
    assert client.get(u("survey_create", org)).status_code == 403
    assert client.post(u("survey_response_action", org, pk=survey.pk, rid=r.pk),
                       {"action": "resolve"}).status_code == 403
    assert client.post(u("survey_question_add", org, pk=survey.pk),
                       {"qtype": "text"}).status_code == 403
    member = make_user(email="m@example.com")
    add_member(org, member, "member")
    client.force_login(member)
    assert client.post(u("survey_delete", org, pk=survey.pk),
                       {"confirm_title": "Feedback"}).status_code == 403


def test_module_gating_and_widget(client, make_org, make_survey):
    org = make_org()
    survey = make_survey(org)
    _respond(survey, nps=10)
    client.force_login(org.owner)
    dash = client.get(u("dashboard", org))
    widget = next(w for w in dash.context["widgets"] if w["key"] == "surveys")
    assert widget["responses_30d"] == 1 and widget["nps"]["score"] == 100
    FeatureOverride.objects.create(organization=org, feature_key="module.surveys", enabled=False)
    assert client.get(u("survey_list", org)).status_code == 404


def test_concurrent_limit_guard(make_org, make_survey):
    survey = make_survey(make_org(), response_limit=1)
    _respond(survey)
    with pytest.raises(services.SurveyError):
        _respond(survey)
    assert Response.objects.count() == 1
