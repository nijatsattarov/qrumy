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
    # Assets
    "asset_detail", "asset_edit", "asset_action", "asset_delete", "asset_document_file",
    "asset_fault", "asset_fault_update", "asset_fault_photo", "asset_location_update",
    "asset_location_delete", "asset_category_update", "asset_category_delete",
    # Qrumy Card
    "card_step", "card_photo_add", "card_photo_delete", "card_publish", "card_delete",
    "card_preview",
    # Digital Menu
    "menu_builder", "menu_settings", "menu_share", "menu_publish", "menu_delete",
    "menu_preview", "menu_category_create", "menu_category_update", "menu_category_move",
    "menu_category_delete", "menu_item_create", "menu_item_edit", "menu_item_action",
    # Events
    "event_detail", "event_edit", "event_delete", "event_point_create", "event_point_update",
    "event_point_delete", "event_point_portal", "event_leads", "event_lead_create",
    "event_leads_export", "event_lead", "event_lead_note", "event_lead_followup",
    "event_followup_toggle", "event_lead_delete",
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


def test_foreign_org_owner_actions_blocked(client, two_orgs):
    from apps.organizations.models import Organization

    victim, attacker_org, attacker = two_orgs
    client.force_login(attacker)
    url = reverse("organization_danger", kwargs={"org_slug": victim.slug})
    assert client.post(url, {"action": "delete", "confirm_name": victim.name}).status_code == 404
    assert Organization.objects.filter(pk=victim.pk).exists()


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


@pytest.fixture
def victim_asset(two_orgs, make_asset, jpeg_bytes):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.assets import services
    from apps.assets.models import AssetCategory, Location

    victim, _, _ = two_orgs
    loc = Location.objects.create(organization=victim, name="Secret room")
    cat = AssetCategory.objects.create(organization=victim, name="Secret cat")
    asset = make_asset(victim, name="Victim asset", location=loc, category=cat)
    doc = services.add_document(asset=asset, actor=victim.owner,
                                upload=SimpleUploadedFile("p.jpg", jpeg_bytes))
    fault = services.report_fault(asset=asset, category="other", description="secret fault",
                                  priority="low", photo=SimpleUploadedFile("f.jpg", jpeg_bytes))
    return {"asset": asset, "doc": doc, "fault": fault, "loc": loc, "cat": cat}


ASSET_ROUTES = [
    ("asset_detail", "get", "pk", "asset", {}), ("asset_edit", "get", "pk", "asset", {}),
    ("asset_action", "post", "pk", "asset", {"action": "status", "status": "lost"}),
    ("asset_delete", "post", "pk", "asset", {"confirm_code": "AST-00001"}),
    ("asset_document_file", "get", "doc_id", "doc", {}),
    ("asset_fault", "get", "pk", "fault", {}),
    ("asset_fault_update", "post", "pk", "fault", {"status": "cancelled"}),
    ("asset_fault_photo", "get", "pk", "fault", {}),
    ("asset_location_update", "post", "loc_id", "loc", {"loc-name": "pwned", "loc-kind": "room"}),
    ("asset_location_delete", "post", "loc_id", "loc", {}),
    ("asset_category_update", "post", "cat_id", "cat", {"cat-name": "pwned"}),
    ("asset_category_delete", "post", "cat_id", "cat", {}),
]


@pytest.mark.parametrize("name,method,kwarg,obj,data", ASSET_ROUTES)
def test_cannot_touch_foreign_assets(client, two_orgs, victim_asset, name, method, kwarg, obj,
                                     data):
    from apps.assets.models import Asset, AssetCategory, FaultReport, Location

    _, attacker_org, attacker = two_orgs
    client.force_login(attacker)
    url = reverse(name, kwargs={"org_slug": attacker_org.slug, kwarg: victim_asset[obj].pk})
    resp = client.post(url, data) if method == "post" else client.get(url)
    assert resp.status_code == 404
    asset = Asset.objects.get(pk=victim_asset["asset"].pk)
    assert asset.status == "active"
    assert FaultReport.objects.get(pk=victim_asset["fault"].pk).status == "new"
    assert Location.objects.get(pk=victim_asset["loc"].pk).name == "Secret room"
    assert AssetCategory.objects.get(pk=victim_asset["cat"].pk).name == "Secret cat"


def test_cannot_link_foreign_location_or_document(client, two_orgs, victim_asset, make_asset):
    from apps.assets.models import Asset, AssetDocument

    _, attacker_org, attacker = two_orgs
    own = make_asset(attacker_org, name="Mine")
    client.force_login(attacker)
    client.post(reverse("asset_create", kwargs={"org_slug": attacker_org.slug}), {
        "name": "Sneaky", "status": "active", "currency": "AZN", "public_visibility": "minimal",
        "location": victim_asset["loc"].pk, "category": victim_asset["cat"].pk})
    sneaky = Asset.objects.filter(name="Sneaky").first()
    assert sneaky is None or (sneaky.location_id is None and sneaky.category_id is None)
    client.post(reverse("asset_action", kwargs={"org_slug": attacker_org.slug, "pk": own.pk}),
                {"action": "delete_document", "document": victim_asset["doc"].pk})
    assert AssetDocument.objects.filter(pk=victim_asset["doc"].pk).exists()
    lists = [client.get(reverse(n, kwargs={"org_slug": attacker_org.slug})).content
             for n in ("asset_list", "asset_faults", "asset_setup", "asset_export", "dashboard")]
    for body in lists:
        assert b"Victim asset" not in body and b"secret fault" not in body
        assert b"Secret room" not in body


# ----------------------------------------------------------------------------- Qrumy Card
@pytest.fixture
def victim_card(two_orgs, jpeg_bytes):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.cards import services

    victim, _, _ = two_orgs
    card = services.create_card(organization=victim, actor=victim.owner,
                                data={"name": "Victim card", "kind": "person"})
    photo = services.add_photo(card=card, upload=SimpleUploadedFile("p.jpg", jpeg_bytes))
    return {"card": card, "photo": photo}


CARD_ROUTES = [
    ("card_step", "get", {"step": "design"}, {}),
    ("card_step", "post", {"step": "profile"}, {"name": "pwned", "next": "profile"}),
    ("card_photo_add", "post", {}, {}),
    ("card_photo_delete", "post", {"photo_id": "photo"}, {}),
    ("card_publish", "post", {}, {"publish": "1"}),
    ("card_delete", "post", {}, {"confirm": "Victim card"}),
    ("card_preview", "get", {}, {}),
]


@pytest.mark.parametrize("name,method,extra,data", CARD_ROUTES)
def test_cannot_touch_foreign_cards(client, two_orgs, victim_card, name, method, extra, data):
    from apps.cards.models import Card, CardPhoto

    _, attacker_org, attacker = two_orgs
    client.force_login(attacker)
    kwargs = {"org_slug": attacker_org.slug, "pk": victim_card["card"].pk}
    for k, v in extra.items():
        kwargs[k] = victim_card[v].pk if v == "photo" else v
    url = reverse(name, kwargs=kwargs)
    resp = client.post(url, data) if method == "post" else client.get(url)
    assert resp.status_code == 404
    card = Card.objects.get(pk=victim_card["card"].pk)
    assert card.name == "Victim card" and not card.is_published
    assert CardPhoto.objects.filter(pk=victim_card["photo"].pk).exists()


def test_cannot_delete_foreign_photo_through_own_card(client, two_orgs, victim_card):
    from apps.cards import services
    from apps.cards.models import CardPhoto

    _, attacker_org, attacker = two_orgs
    own = services.create_card(organization=attacker_org, actor=attacker, data={"name": "Mine"})
    client.force_login(attacker)
    url = reverse("card_photo_delete", kwargs={"org_slug": attacker_org.slug, "pk": own.pk,
                                               "photo_id": victim_card["photo"].pk})
    assert client.post(url).status_code == 404
    assert CardPhoto.objects.filter(pk=victim_card["photo"].pk).exists()


# ----------------------------------------------------------------------------- Digital Menu
@pytest.fixture
def victim_menu(two_orgs):
    from apps.menus import services
    from apps.menus.models import MenuItem

    victim, _, _ = two_orgs
    menu = services.create_menu(organization=victim, actor=victim.owner,
                                data={"name": "Victim menu"})
    cat = services.add_category(menu=menu, name="Secret cat")
    item = MenuItem.objects.create(organization=victim, menu=menu, category=cat,
                                   name="Secret item", price=5)
    return {"menu": menu, "cat": cat, "item": item}


MENU_ROUTES = [
    ("menu_builder", "get", {}, {}), ("menu_settings", "get", {}, {}),
    ("menu_settings", "post", {}, {"name": "pwned", "currency": "AZN", "language": "az",
                                   "layout": "list", "accent_color": "#000000"}),
    ("menu_share", "get", {}, {}), ("menu_publish", "post", {}, {"publish": "1"}),
    ("menu_delete", "post", {}, {"confirm": "Victim menu"}), ("menu_preview", "get", {}, {}),
    ("menu_category_create", "post", {}, {"new-name": "pwned"}),
    ("menu_category_update", "post", {"cat_id": "cat"}, {}),
    ("menu_category_move", "post", {"cat_id": "cat"}, {"direction": "down"}),
    ("menu_category_delete", "post", {"cat_id": "cat"}, {}),
    ("menu_item_create", "get", {}, {}),
    ("menu_item_edit", "post", {"item_id": "item"}, {"name": "pwned", "price": "1"}),
    ("menu_item_action", "post", {"item_id": "item"}, {"action": "delete"}),
]


@pytest.mark.parametrize("name,method,extra,data", MENU_ROUTES)
def test_cannot_touch_foreign_menus(client, two_orgs, victim_menu, name, method, extra, data):
    from apps.menus.models import Menu, MenuCategory, MenuItem

    _, attacker_org, attacker = two_orgs
    client.force_login(attacker)
    kwargs = {"org_slug": attacker_org.slug, "pk": victim_menu["menu"].pk}
    for k, v in extra.items():
        kwargs[k] = victim_menu[v].pk
    url = reverse(name, kwargs=kwargs)
    resp = client.post(url, data) if method == "post" else client.get(url)
    assert resp.status_code == 404
    menu = Menu.objects.get(pk=victim_menu["menu"].pk)
    assert menu.name == "Victim menu" and not menu.is_published
    assert MenuCategory.objects.filter(menu=menu).count() == 1
    assert MenuItem.objects.get(pk=victim_menu["item"].pk).name == "Secret item"


def test_cannot_use_foreign_category_or_item_through_own_menu(client, two_orgs, victim_menu):
    from apps.menus import services
    from apps.menus.models import MenuCategory, MenuItem

    _, attacker_org, attacker = two_orgs
    own = services.create_menu(organization=attacker_org, actor=attacker, data={"name": "Mine"})
    services.add_category(menu=own, name="Mine")
    client.force_login(attacker)
    base = {"org_slug": attacker_org.slug, "pk": own.pk}
    assert client.post(reverse("menu_category_delete",
                               kwargs={**base, "cat_id": victim_menu["cat"].pk})).status_code == 404
    assert client.post(reverse("menu_item_action", kwargs={**base, "item_id": victim_menu[
        "item"].pk}), {"action": "delete"}).status_code == 404
    client.post(reverse("menu_item_create", kwargs=base), {
        "category": victim_menu["cat"].pk, "name": "Sneaky", "price": "1",
        "availability": "available"})
    assert not MenuItem.objects.filter(name="Sneaky").exists()
    assert MenuCategory.objects.filter(pk=victim_menu["cat"].pk).exists()


# ----------------------------------------------------------------------------- Events
@pytest.fixture
def victim_event(two_orgs):
    from apps.events import services

    victim, _, _ = two_orgs
    event = services.create_event(organization=victim, actor=victim.owner,
                                  data={"name": "Victim expo"})
    point = services.add_point(event=event, actor=victim.owner, data={"name": "Secret stand"})
    lead = services.add_lead(event=event, actor=victim.owner,
                             data={"full_name": "Secret lead", "email": "s@example.com"})
    followup = services.add_followup(lead=lead, actor=victim.owner, title="Secret task")
    return {"event": event, "point": point, "lead": lead, "followup": followup}


EVENT_ROUTES = [
    ("event_detail", "get", "event", {}, {}), ("event_edit", "get", "event", {}, {}),
    ("event_delete", "post", "event", {}, {"confirm": "Victim expo"}),
    ("event_point_create", "post", "event", {}, {"name": "pwned"}),
    ("event_point_update", "post", "event", {"point_id": "point"}, {"name": "pwned"}),
    ("event_point_delete", "post", "event", {"point_id": "point"}, {}),
    ("event_point_portal", "post", "event", {"point_id": "point"}, {}),
    ("event_leads", "get", "event", {}, {}), ("event_lead_create", "get", "event", {}, {}),
    ("event_leads_export", "get", "event", {}, {}),
    ("event_lead", "post", "lead", {}, {"stage": "lost", "temperature": "cold"}),
    ("event_lead_note", "post", "lead", {}, {"body": "pwned"}),
    ("event_lead_followup", "post", "lead", {}, {"title": "pwned"}),
    ("event_followup_toggle", "post", "lead", {"followup_id": "followup"}, {}),
    ("event_lead_delete", "post", "lead", {}, {}),
]


@pytest.mark.parametrize("name,method,obj,extra,data", EVENT_ROUTES)
def test_cannot_touch_foreign_events(client, two_orgs, victim_event, name, method, obj, extra,
                                     data):
    from apps.events.models import CapturePoint, Event, FollowUp, Lead

    _, attacker_org, attacker = two_orgs
    client.force_login(attacker)
    kwargs = {"org_slug": attacker_org.slug, "pk": victim_event[obj].pk}
    for k, v in extra.items():
        kwargs[k] = victim_event[v].pk
    resp = client.post(reverse(name, kwargs=kwargs), data) if method == "post" else \
        client.get(reverse(name, kwargs=kwargs))
    assert resp.status_code == 404
    assert Event.objects.filter(pk=victim_event["event"].pk).exists()
    point = CapturePoint.objects.get(pk=victim_event["point"].pk)
    assert point.name == "Secret stand" and not point.portal_token_hash
    lead = Lead.objects.get(pk=victim_event["lead"].pk)
    assert lead.stage == "new" and not lead.notes.exists()
    assert FollowUp.objects.get(pk=victim_event["followup"].pk).done_at is None


def test_cannot_move_lead_to_foreign_point(client, two_orgs, victim_event):
    from apps.events import services
    from apps.events.models import Lead

    _, attacker_org, attacker = two_orgs
    own = services.create_event(organization=attacker_org, actor=attacker, data={"name": "Mine"})
    client.force_login(attacker)
    client.post(reverse("event_lead_create", kwargs={"org_slug": attacker_org.slug,
                                                     "pk": own.pk}),
                {"full_name": "Sneaky", "email": "x@example.com", "temperature": "warm",
                 "point": victim_event["point"].pk, "consent": "on"})
    assert not Lead.objects.filter(full_name="Sneaky", point=victim_event["point"]).exists()
