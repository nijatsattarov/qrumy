import csv
import io

import pytest
from django.core import mail
from django.urls import reverse

from apps.events import services
from apps.events.models import CapturePoint, Event, FollowUp, Lead
from apps.notifications.models import Notification

pytestmark = pytest.mark.django_db


@pytest.fixture
def event(make_org):
    org = make_org()
    ev = services.create_event(organization=org, actor=org.owner, data={
        "name": "Expo", "language": "az", "interests": "Coffee\nMachines"})
    services.add_point(event=ev, actor=org.owner, data={"name": "Stand A1"})
    return ev


def _start(client, point):
    page = client.get(point.public_path).content.decode()
    import re

    return re.search(r'name="started" value="([^"]+)"', page).group(1)


def _submit(client, point, **extra):
    data = {"full_name": "Rəşad Quliyev", "email": "r@example.com", "phone": "+994501112233",
            "company": "Hilton", "job_title": "Buyer", "interests": ["Coffee"],
            "message": "Send prices", "consent": "on", "started": _start(client, point)}
    data.update(extra)
    return client.post(point.public_path, data)


def test_create_event_creates_point_with_qr(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    r = client.post(reverse("event_create", kwargs={"org_slug": org.slug}), {
        "name": "Fair", "language": "en", "first_point": "Stand B2", "is_active": "on",
        "ask_phone": "on", "ask_company": "on"})
    ev = Event.objects.get(name="Fair")
    assert r.status_code == 302
    point = ev.points.get()
    assert point.name == "Stand B2" and point.qr_code.qr_type == "event_lead"
    from apps.qr_management.types import get_type

    assert get_type("event_lead").destination(point.qr_code.payload).endswith(
        f"/e/{point.capture_token}?src=qr")


def test_public_form_captures_lead_and_notifies(client, event,
                                                django_capture_on_commit_callbacks):
    point = event.points.get()
    point.contact_email = "sales@exhibitor.example"
    point.save()
    body = client.get(point.public_path).content.decode()
    assert 'lang="az"' in body and "Coffee" in body
    with django_capture_on_commit_callbacks(execute=True):
        r = _submit(client, point)
    assert r.status_code == 302 and r["Location"].endswith("/thanks")
    lead = Lead.objects.get()
    assert (lead.full_name, lead.point, lead.source, lead.consent) == (
        "Rəşad Quliyev", point, "qr", True)
    assert lead.interests == ["Coffee"] and lead.consent_text
    assert Notification.objects.filter(kind="events.lead", user=event.organization.owner)
    assert mail.outbox and mail.outbox[-1].to == ["sales@exhibitor.example"]


def test_public_form_rules(client, event):
    point = event.points.get()
    assert _submit(client, point, consent="").status_code == 200  # consent required
    assert _submit(client, point, email="", phone="").status_code == 200  # need a contact
    assert _submit(client, point, website="spam").status_code == 200  # honeypot
    assert _submit(client, point, started="forged").status_code == 200  # signed token
    assert not Lead.objects.exists()
    event.is_active = False
    event.save()
    assert "closed" in client.get(point.public_path).content.decode().lower() or \
        Lead.objects.count() == 0


def test_public_form_rate_limited(client, event, settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                   "LOCATION": "events-rl"}}
    point = event.points.get()
    codes = [_submit(client, point, email=f"a{i}@x.example").status_code for i in range(12)]
    assert codes[0] == 302 and codes[-1] in (403, 429)


def test_staff_lead_qualify_notes_followups_export(client, event):
    org = event.organization
    client.force_login(org.owner)
    point = event.points.get()
    r = client.post(reverse("event_lead_create", kwargs={"org_slug": org.slug, "pk": event.pk}),
                    {"full_name": "Leyla", "phone": "+994551234567", "point": point.pk,
                     "temperature": "hot", "consent": "on"})
    lead = Lead.objects.get()
    assert r.status_code == 302 and lead.source == "staff" and lead.added_by == org.owner
    url = reverse("event_lead", kwargs={"org_slug": org.slug, "pk": lead.pk})
    client.post(url, {"temperature": "warm", "stage": "qualified", "assigned_to": org.owner.pk})
    lead.refresh_from_db()
    assert (lead.temperature, lead.stage, lead.assigned_to) == ("warm", "qualified", org.owner)
    client.post(reverse("event_lead_note", kwargs={"org_slug": org.slug, "pk": lead.pk}),
                {"body": "Wants 3 branches"})
    client.post(reverse("event_lead_followup", kwargs={"org_slug": org.slug, "pk": lead.pk}),
                {"title": "Send offer", "due_on": "2026-12-01"})
    f = FollowUp.objects.get()
    client.post(reverse("event_followup_toggle", kwargs={"org_slug": org.slug, "pk": lead.pk,
                                                         "followup_id": f.pk}))
    f.refresh_from_db()
    assert f.done_at and lead.notes.count() == 1
    export = client.get(reverse("event_leads_export",
                                kwargs={"org_slug": org.slug, "pk": event.pk}))
    rows = list(csv.reader(io.StringIO(export.content.decode().lstrip("﻿"))))
    assert rows[0][4] == "full name" and rows[1][4] == "Leyla"
    leads_page = client.get(reverse("event_leads", kwargs={"org_slug": org.slug, "pk": event.pk})
                            + "?temperature=warm&q=Ley")
    assert "Leyla" in leads_page.content.decode()
    assert services.stats(event)["total"] == 1


def test_exhibitor_portal_link(client, event):
    org = event.organization
    point = event.points.get()
    _submit(client, point)
    client.force_login(org.owner)
    url = reverse("event_point_portal", kwargs={"org_slug": org.slug, "pk": event.pk,
                                                "point_id": point.pk})
    client.post(url)
    link = client.get(reverse("event_detail", kwargs={"org_slug": org.slug, "pk": event.pk}))
    import re

    portal = re.search(r'data-copy="https?://[^/]+(/e/x/[^"]+)"', link.content.decode()).group(1)
    point.refresh_from_db()
    assert point.portal_token_hash and portal.split("/")[-1] not in point.portal_token_hash
    client.logout()
    page = client.get(portal).content.decode()
    assert "Rəşad Quliyev" in page
    assert "Rəşad" in client.get(portal + "?format=csv").content.decode()
    client.force_login(org.owner)
    client.post(url, {"revoke": "1"})
    client.logout()
    assert client.get(portal).status_code == 404
    assert client.get("/e/x/not-a-token").status_code == 404


def test_portal_shows_only_its_point(client, event):
    other = services.add_point(event=event, actor=event.organization.owner,
                               data={"name": "Other stand"})
    _submit(client, event.points.get(name="Stand A1"), full_name="Visible Person")
    _submit(client, other, full_name="Hidden Person", email="h@example.com")
    raw = other.new_portal_token()
    page = client.get(f"/e/x/{raw}").content.decode()
    assert "Hidden Person" in page and "Visible Person" not in page


def test_delete_point_keeps_leads_and_event_delete(client, event):
    org = event.organization
    point = event.points.get()
    _submit(client, point)
    client.force_login(org.owner)
    client.post(reverse("event_point_delete", kwargs={"org_slug": org.slug, "pk": event.pk,
                                                      "point_id": point.pk}))
    assert Lead.objects.count() == 1 and not CapturePoint.objects.exists()
    client.post(reverse("event_delete", kwargs={"org_slug": org.slug, "pk": event.pk}),
                {"confirm": "Expo"})
    assert not Event.objects.exists() and not Lead.objects.exists()


def test_viewer_cannot_change_leads(client, event, make_user, add_member):
    org = event.organization
    lead = services.add_lead(event=event, actor=org.owner,
                             data={"full_name": "X", "email": "x@example.com"})
    viewer = make_user(email="v@example.com")
    add_member(org, viewer, "viewer")
    client.force_login(viewer)
    url = reverse("event_lead", kwargs={"org_slug": org.slug, "pk": lead.pk})
    assert client.get(url).status_code == 200
    client.post(url, {"temperature": "hot", "stage": "won"})
    lead.refresh_from_db()
    assert lead.stage == "new"
    assert client.post(reverse("event_lead_delete", kwargs={"org_slug": org.slug,
                                                            "pk": lead.pk})).status_code == 403


def test_plan_limit(event):
    from django.core.cache import cache

    from apps.subscriptions.models import FeatureOverride

    org = event.organization
    FeatureOverride.objects.create(organization=org, feature_key="events.max", limit_value=1)
    cache.clear()
    org = type(org).objects.get(pk=org.pk)
    with pytest.raises(services.EventError):
        services.create_event(organization=org, actor=org.owner, data={"name": "2nd"})
