"""Tenant isolation suite.

1. Every URL that takes ``org_slug`` is requested by a signed-in user of another
   organization → must be 404 (GET and POST).
2. Routes that take object IDs are attacked with *another* org's objects while using the
   attacker's own slug → must be 404 and leave data untouched.
3. Coverage guard: any new org-scoped route with extra URL kwargs must be listed in
   ``OBJECT_ROUTES_COVERED`` (and get an attack test), or this suite fails.
"""

import pytest
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.organizations.models import Invitation, Membership

pytestmark = pytest.mark.django_db

OBJECT_ROUTES_COVERED = {
    "team_member_role", "team_member_remove", "team_invitation_revoke",
    # QR Management
    "qr_detail", "qr_edit", "qr_set_status", "qr_delete", "qr_download", "qr_landing_preview",
    "qr_analytics_export", "qr_folder_rename", "qr_folder_delete",
    "qr_create",  # extra kwarg is a type key, not an object id
    # Surveys
    "survey_builder", "survey_create_qr", "survey_delete", "survey_preview",
    "survey_question_add", "survey_question_delete", "survey_question_move",
    "survey_question_update", "survey_response", "survey_response_action", "survey_responses",
    "survey_responses_export", "survey_results", "survey_settings", "survey_share",
    "survey_status",
}


def _org_routes():
    routes = []

    def walk(patterns, prefix=""):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern) and p.name:
                full = prefix + str(p.pattern)
                if "<slug:org_slug>" in full:
                    routes.append((p.name, full))

    walk(get_resolver().url_patterns)
    return routes


def _extra_kwargs(route: str) -> list[str]:
    import re

    return [k for k in re.findall(r"<(?:\w+:)?(\w+)>", route) if k != "org_slug"]


@pytest.fixture
def two_orgs(make_user, make_org, add_member):
    victim = make_org("Victim")
    attacker_org = make_org("Attacker")
    attacker = attacker_org.owner
    return victim, attacker_org, attacker


def test_routes_were_discovered():
    names = {n for n, _ in _org_routes()}
    assert {"dashboard", "team", "billing", "organization_settings"} <= names


def test_foreign_org_slug_is_404_for_every_route(client, two_orgs):
    victim, _, attacker = two_orgs
    client.force_login(attacker)
    for name, route in _org_routes():
        extra = {k: ("svg" if k == "fmt" else "url" if k == "type_key" else 1)
                 for k in _extra_kwargs(route)}
        kwargs = {"org_slug": victim.slug, **extra}
        url = reverse(name, kwargs=kwargs)
        assert client.get(url).status_code == 404, url
        assert client.post(url, {}).status_code == 404, url


def test_every_object_route_has_an_attack_test():
    uncovered = {n for n, r in _org_routes() if _extra_kwargs(r)} - OBJECT_ROUTES_COVERED
    assert not uncovered, f"Add isolation tests for: {sorted(uncovered)}"


def test_cannot_change_role_of_foreign_member(client, two_orgs, make_user, add_member):
    victim, attacker_org, attacker = two_orgs
    target = add_member(victim, make_user(email="t@example.com"), "member")
    client.force_login(attacker)
    for name, data in (("team_member_role", {"role": "viewer"}), ("team_member_remove", {})):
        url = reverse(name, kwargs={"org_slug": attacker_org.slug, "member_id": target.pk})
        assert client.post(url, data).status_code == 404
    target.refresh_from_db()
    assert target.role == "member"


def test_cannot_revoke_foreign_invitation(client, two_orgs):
    from apps.organizations.services import invite_member

    victim, attacker_org, attacker = two_orgs
    inv, _ = invite_member(organization=victim, email="x@example.com", role="member",
                           actor_membership=Membership.objects.get(organization=victim,
                                                                   role="owner"))
    client.force_login(attacker)
    url = reverse("team_invitation_revoke",
                  kwargs={"org_slug": attacker_org.slug, "invitation_id": inv.pk})
    assert client.post(url).status_code == 404
    assert Invitation.objects.get(pk=inv.pk).revoked_at is None


def test_team_page_lists_only_own_members(client, two_orgs):
    victim, attacker_org, attacker = two_orgs
    client.force_login(attacker)
    body = client.get(reverse("team", kwargs={"org_slug": attacker_org.slug})).content.decode()
    assert victim.owner.email not in body


def test_org_switcher_lists_only_own_orgs(client, two_orgs):
    victim, attacker_org, attacker = two_orgs
    client.force_login(attacker)
    body = client.get(reverse("dashboard", kwargs={"org_slug": attacker_org.slug})).content
    assert b"Victim" not in body


def test_for_org_requires_organization():
    from apps.subscriptions.models import Subscription

    with pytest.raises(ValueError):
        Subscription.objects.for_org(None)


@pytest.fixture
def victim_qr(two_orgs, make_qr):
    victim, _, _ = two_orgs
    return make_qr(victim, name="Victim code")


QR_OBJECT_ROUTES = [
    ("qr_detail", {}, "get"), ("qr_edit", {}, "get"), ("qr_set_status", {}, "post"),
    ("qr_delete", {}, "post"), ("qr_download", {"fmt": "png"}, "get"),
    ("qr_landing_preview", {}, "get"), ("qr_analytics_export", {}, "get"),
]


@pytest.mark.parametrize("name,extra,method", QR_OBJECT_ROUTES)
def test_cannot_touch_foreign_qr_codes(client, two_orgs, victim_qr, name, extra, method):
    _, attacker_org, attacker = two_orgs
    client.force_login(attacker)
    url = reverse(name, kwargs={"org_slug": attacker_org.slug, "pk": victim_qr.pk, **extra})
    resp = getattr(client, method)(url, {"status": "paused"} if method == "post" else None)
    assert resp.status_code == 404
    victim_qr.refresh_from_db()
    assert victim_qr.status == "active" and victim_qr.deleted_at is None


def test_bulk_action_ignores_foreign_ids(client, two_orgs, victim_qr):
    _, attacker_org, attacker = two_orgs
    client.force_login(attacker)
    client.post(reverse("qr_bulk_action", kwargs={"org_slug": attacker_org.slug}),
                {"ids": [victim_qr.pk], "action": "delete"})
    victim_qr.refresh_from_db()
    assert victim_qr.deleted_at is None
    resp = client.post(reverse("qr_bulk_action", kwargs={"org_slug": attacker_org.slug}),
                       {"ids": [victim_qr.pk], "action": "export_png"})
    assert resp["Content-Type"] != "application/zip"


def test_cannot_touch_foreign_folders(client, two_orgs):
    from apps.qr_management.models import Folder

    victim, attacker_org, attacker = two_orgs
    folder = Folder.objects.create(organization=victim, name="Secret")
    client.force_login(attacker)
    for name in ("qr_folder_rename", "qr_folder_delete"):
        url = reverse(name, kwargs={"org_slug": attacker_org.slug, "folder_id": folder.pk})
        assert client.post(url, {"name": "pwned"}).status_code == 404
    folder.refresh_from_db()
    assert folder.name == "Secret"


def test_cannot_file_codes_into_foreign_folder(client, two_orgs):
    from apps.qr_management.models import Folder, QRCode

    victim, attacker_org, attacker = two_orgs
    folder = Folder.objects.create(organization=victim, name="Secret")
    client.force_login(attacker)
    client.post(reverse("qr_create", kwargs={"org_slug": attacker_org.slug, "type_key": "url"}), {
        "c-url": "https://example.com", "meta-name": "x", "meta-mode": "dynamic",
        "meta-folder": folder.pk, "s-fg": "#101B3A", "s-bg": "#FFFFFF",
        "s-eye_color": "#101B3A", "s-module_shape": "square", "s-eye_frame": "square",
        "s-eye_ball": "square", "s-frame": "none", "s-frame_color": "#101B3A"})
    assert not QRCode.objects.filter(folder=folder).exists()


def test_analytics_never_include_foreign_scans(client, two_orgs, victim_qr):
    _, attacker_org, attacker = two_orgs
    client.get(f"/q/{victim_qr.short_code}", HTTP_USER_AGENT="Mozilla/5.0 (iPhone; Mobile)")
    client.force_login(attacker)
    resp = client.get(reverse("analytics_overview", kwargs={"org_slug": attacker_org.slug}))
    assert resp.context["totals"]["scans"] == 0
    csv = client.get(reverse("analytics_export", kwargs={"org_slug": attacker_org.slug}))
    assert b"Victim code" not in csv.content


def test_preview_cannot_read_foreign_logo(client, two_orgs, victim_qr):
    _, attacker_org, attacker = two_orgs
    client.force_login(attacker)
    resp = client.post(reverse("qr_preview", kwargs={"org_slug": attacker_org.slug}), {
        "type": "url", "qr": victim_qr.pk, "s-fg": "#101B3A", "s-bg": "#FFFFFF",
        "s-eye_color": "#101B3A", "s-module_shape": "square", "s-eye_frame": "square",
        "s-eye_ball": "square", "s-frame": "none", "s-frame_color": "#101B3A"})
    assert victim_qr.short_code.encode() not in resp.content


@pytest.fixture
def victim_survey(two_orgs, make_survey):
    from apps.surveys import services

    victim, _, _ = two_orgs
    survey = make_survey(victim, title="Victim survey", qtypes=("longtext",))
    text = survey.questions.get(qtype="longtext")
    nps = survey.questions.get(qtype="nps")
    response = services.submit_response(survey=survey, answers={nps: 3, text: "secret complaint"},
                                        source="link", language="en", duration=5)
    return survey, response


SURVEY_ROUTES = [
    ("survey_builder", "get", {}), ("survey_settings", "get", {}), ("survey_share", "get", {}),
    ("survey_results", "get", {}), ("survey_responses", "get", {}),
    ("survey_responses_export", "get", {}), ("survey_preview", "get", {}),
    ("survey_status", "post", {"action": "close"}), ("survey_create_qr", "post", {}),
    ("survey_delete", "post", {"confirm_title": "Victim survey"}),
    ("survey_question_add", "post", {"qtype": "text"}),
]


@pytest.mark.parametrize("name,method,data", SURVEY_ROUTES)
def test_cannot_touch_foreign_surveys(client, two_orgs, victim_survey, name, method, data):
    from apps.surveys.models import Survey

    _, attacker_org, attacker = two_orgs
    survey, _ = victim_survey
    client.force_login(attacker)
    url = reverse(name, kwargs={"org_slug": attacker_org.slug, "pk": survey.pk})
    resp = client.post(url, data) if method == "post" else client.get(url)
    assert resp.status_code == 404
    survey = Survey.objects.get(pk=survey.pk)
    assert survey.status == "published" and survey.questions.count() == 2
    assert survey.qr_code_id is None


@pytest.mark.parametrize("name,data", [
    ("survey_question_update", {"label": "pwned"}), ("survey_question_move", {"direction": "up"}),
    ("survey_question_delete", {}),
])
def test_cannot_touch_foreign_questions(client, two_orgs, victim_survey, make_survey, name, data):
    _, attacker_org, attacker = two_orgs
    survey, _ = victim_survey
    own = make_survey(attacker_org, title="Mine")
    q = survey.questions.first()
    client.force_login(attacker)
    # foreign question under the attacker's OWN survey id
    url = reverse(name, kwargs={"org_slug": attacker_org.slug, "pk": own.pk, "qid": q.pk})
    assert client.post(url, data).status_code == 404
    q.refresh_from_db()
    assert q.label != "pwned"


def test_cannot_read_or_change_foreign_responses(client, two_orgs, victim_survey, make_survey):
    _, attacker_org, attacker = two_orgs
    survey, response = victim_survey
    own = make_survey(attacker_org, title="Mine")
    client.force_login(attacker)
    for pk in (own.pk, survey.pk):
        detail = reverse("survey_response", kwargs={"org_slug": attacker_org.slug, "pk": pk,
                                                    "rid": response.pk})
        action = reverse("survey_response_action", kwargs={
            "org_slug": attacker_org.slug, "pk": pk, "rid": response.pk})
        assert client.get(detail).status_code == 404
        assert client.post(action, {"action": "resolve"}).status_code == 404
    response.refresh_from_db()
    assert response.status == "open"
    dash = client.get(reverse("dashboard", kwargs={"org_slug": attacker_org.slug}))
    assert b"Victim survey" not in dash.content and b"secret complaint" not in dash.content
