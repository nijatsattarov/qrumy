import re

import pytest
from django.utils import timezone

from apps.subscriptions.models import FeatureOverride, UsageCounter
from apps.surveys.models import Answer, Response, Survey, SurveyDailyStat

pytestmark = pytest.mark.django_db
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148"


def _get(client, survey, query=""):
    return client.get(f"/s/{survey.public_token}{query}", HTTP_USER_AGENT=UA)


def _token(resp):
    return re.search(r'name="started" value="([^"]+)"', resp.content.decode()).group(1)


def _answers(survey, **over):
    data = {}
    for q in survey.questions.all():
        if q.qtype == "nps":
            data[f"q_{q.pk}"] = "9"
        elif q.qtype == "csat":
            data[f"q_{q.pk}"] = "4"
        elif q.qtype == "single":
            data[f"q_{q.pk}"] = q.options[0]
        elif q.qtype == "longtext":
            data[f"q_{q.pk}"] = "Great tea"
    data.update(over)
    return data


def _submit(client, survey, query="", **over):
    token = _token(_get(client, survey, query))
    return client.post(f"/s/{survey.public_token}{query}",
                       {"started": token, **_answers(survey, **over)}, HTTP_USER_AGENT=UA)


def test_full_submission_stores_answers_and_scores(client, make_org, make_survey):
    survey = make_survey(make_org())
    resp = _submit(client, survey, query="?src=qr")
    assert resp.status_code == 200 and b"Thank you" in resp.content
    r = Response.objects.get()
    assert r.source == "qr" and r.nps == 9 and r.csat == 4 and r.duration_seconds is not None
    assert Answer.objects.filter(response=r).count() == 4
    survey.refresh_from_db()
    assert survey.response_count == 1
    assert UsageCounter.objects.get(metric="survey.responses").value == 1


def test_required_questions_validated(client, make_org, make_survey):
    survey = make_survey(make_org())
    nps = survey.questions.get(qtype="nps")
    resp = _submit(client, survey, **{f"q_{nps.pk}": ""})
    assert resp.status_code == 200 and not Response.objects.exists()
    assert b"form-error" in resp.content


def test_invalid_choice_and_scale_rejected(client, make_org, make_survey):
    survey = make_survey(make_org())
    single = survey.questions.get(qtype="single")
    nps = survey.questions.get(qtype="nps")
    _submit(client, survey, **{f"q_{single.pk}": "Hacked option"})
    _submit(client, survey, **{f"q_{nps.pk}": "11"})
    assert not Response.objects.exists()


def test_missing_or_forged_start_token_rejected(client, make_org, make_survey):
    survey = make_survey(make_org())
    client.post(f"/s/{survey.public_token}", _answers(survey), HTTP_USER_AGENT=UA)
    client.post(f"/s/{survey.public_token}", {"started": "forged", **_answers(survey)})
    other = make_survey(survey.organization, title="Other")
    token_for_other = _token(_get(client, other))
    client.post(f"/s/{survey.public_token}", {"started": token_for_other, **_answers(survey)})
    assert not Response.objects.exists()


def test_honeypot_silently_discards(client, make_org, make_survey):
    survey = make_survey(make_org())
    resp = _submit(client, survey, website="http://spam.example")
    assert b"Thank you" in resp.content and not Response.objects.exists()


def test_draft_is_404_and_closed_states(client, make_org, make_survey):
    org = make_org()
    draft = make_survey(org, publish=False)
    assert _get(client, draft).status_code == 404
    survey = make_survey(org, response_limit=1)
    _submit(client, survey)
    assert b"all the responses it needs" in _get(client, survey).content
    ended = make_survey(org, closes_at=timezone.now() - timezone.timedelta(minutes=1))
    assert b"has ended" in _get(client, ended).content
    Survey.objects.filter(pk=ended.pk).update(closes_at=None, status="closed")
    assert b"has ended" in _get(client, ended).content


def test_limit_enforced_on_submit_not_only_on_page(client, make_org, make_survey):
    survey = make_survey(make_org(), response_limit=1)
    token = _token(_get(client, survey))
    _submit(client, survey)
    client.post(f"/s/{survey.public_token}", {"started": token, **_answers(survey)})
    assert Response.objects.count() == 1


def test_monthly_response_quota(client, make_org, make_survey):
    org = make_org()
    FeatureOverride.objects.create(organization=org, feature_key="surveys.responses_month",
                                   limit_value=1)
    survey = make_survey(org)
    _submit(client, survey)
    resp = _submit(client, survey)
    assert Response.objects.count() == 1 and b"accepting responses" in resp.content


def test_contact_requires_consent(client, make_org, make_survey):
    survey = make_survey(make_org(), contact_mode="optional", consent_text="You may contact me")
    _submit(client, survey, contact_email="a@b.az")
    assert not Response.objects.exists()
    _submit(client, survey, contact_email="a@b.az", consent="on")
    r = Response.objects.get()
    assert r.consent and r.consent_text == "You may contact me" and r.contact_email == "a@b.az"


def test_views_counted_once_per_visitor_and_not_for_bots(client, make_org, make_survey):
    survey = make_survey(make_org())
    _get(client, survey)
    _get(client, survey)  # same browser (cookie)
    client.get(f"/s/{survey.public_token}", HTTP_USER_AGENT="Googlebot/2.1")
    assert SurveyDailyStat.objects.get(survey=survey).views == 1


def test_public_page_in_survey_language(client, make_org, make_survey):
    survey = make_survey(make_org(), language="az")
    body = _get(client, survey).content.decode()
    assert 'lang="az"' in body and "Göndər" in body


def test_embed_can_be_framed_and_theme_css(client, make_org, make_survey):
    survey = make_survey(make_org(), accent_color="#FFCC00")
    resp = client.get(f"/s/{survey.public_token}/embed")
    assert resp.status_code == 200 and "X-Frame-Options" not in resp
    assert "frame-ancestors *" in resp["Content-Security-Policy"]
    normal = _get(client, survey)
    assert normal["X-Frame-Options"] == "DENY"
    css = client.get(f"/s/{survey.public_token}/theme.css")
    assert css["Content-Type"].startswith("text/css") and "#FFCC00" in css.content.decode()
    assert "--survey-on-accent:#101B3A" in css.content.decode()  # dark text on yellow


def test_embed_submission_is_tagged(client, make_org, make_survey):
    survey = make_survey(make_org())
    token = _token(client.get(f"/s/{survey.public_token}/embed"))
    client.post(f"/s/{survey.public_token}/embed", {"started": token, **_answers(survey)})
    assert Response.objects.get().source == "embed"


def test_answers_are_escaped_in_admin_views(client, make_org, make_survey):
    org = make_org()
    survey = make_survey(org)
    text = survey.questions.get(qtype="longtext")
    _submit(client, survey, **{f"q_{text.pk}": "<script>alert(1)</script>"})
    client.force_login(org.owner)
    r = Response.objects.get()
    body = client.get(f"/app/{org.slug}/surveys/{survey.pk}/responses/{r.pk}/").content
    assert b"<script>alert(1)</script>" not in body and b"&lt;script&gt;" in body
