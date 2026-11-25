import pytest
from django.urls import reverse

from apps.audit_logs.models import AuditLog
from apps.organizations.models import Membership, Organization
from apps.organizations.services import create_organization
from apps.subscriptions.entitlements import get_entitlements

pytestmark = pytest.mark.django_db


def test_create_organization_sets_owner_plan_and_audit(make_user):
    user = make_user()
    org = create_organization(owner=user, name="Gəncə Hotel")
    assert org.slug == "gence-hotel"
    assert Membership.objects.get(organization=org, user=user).role == "owner"
    assert get_entitlements(org).plan.key == "beta"
    assert AuditLog.objects.filter(organization=org, action="organization.created").exists()


def test_slugs_are_unique(make_user):
    a = create_organization(owner=make_user(email="a@example.com"), name="Same")
    b = create_organization(owner=make_user(email="b@example.com"), name="Same")
    assert a.slug != b.slug


def test_onboarding_flow(client, make_user):
    client.force_login(make_user())
    assert client.get(reverse("app_home"))["Location"] == reverse("organization_create")
    resp = client.post(reverse("organization_create"),
                       {"name": "Acme", "industry": "retail", "country": "AZ",
                        "timezone": "Asia/Baku"})
    org = Organization.objects.get()
    assert resp["Location"] == reverse("dashboard", kwargs={"org_slug": org.slug})
    assert client.get(reverse("app_home"))["Location"] == resp["Location"]


def test_anonymous_redirected_to_login(client, make_org):
    org = make_org()
    resp = client.get(reverse("dashboard", kwargs={"org_slug": org.slug}))
    assert resp.status_code == 302 and "/accounts/login/" in resp["Location"]


def test_viewer_cannot_edit_settings(client, make_user, make_org, add_member):
    org = make_org()
    viewer = make_user(email="v@example.com")
    add_member(org, viewer, "viewer")
    client.force_login(viewer)
    url = reverse("organization_settings", kwargs={"org_slug": org.slug})
    assert client.get(url).status_code == 403
    assert client.post(url, {"name": "Hacked"}).status_code == 403
    org.refresh_from_db()
    assert org.name == "Acme"


def test_admin_can_edit_settings(client, make_user, make_org, add_member):
    org = make_org()
    admin = make_user(email="a@example.com")
    add_member(org, admin, "admin")
    client.force_login(admin)
    client.post(reverse("organization_settings", kwargs={"org_slug": org.slug}),
                {"name": "Acme Ltd", "timezone": "Asia/Baku", "language": "az"})
    org.refresh_from_db()
    assert org.name == "Acme Ltd" and org.language == "az"


def test_logo_rejects_non_images(client, make_org):
    from django.core.files.uploadedfile import SimpleUploadedFile

    org = make_org()
    client.force_login(org.owner)
    fake = SimpleUploadedFile("logo.png", b"<svg onload=alert(1)>", content_type="image/png")
    resp = client.post(reverse("organization_settings", kwargs={"org_slug": org.slug}),
                       {"name": "Acme", "timezone": "Asia/Baku", "language": "en", "logo": fake})
    assert resp.status_code == 200  # form re-rendered with error
    org.refresh_from_db()
    assert not org.logo


def test_suspended_organization_is_blocked(client, make_org):
    org = make_org()
    org.status = Organization.Status.SUSPENDED
    org.save()
    client.force_login(org.owner)
    assert client.get(reverse("dashboard", kwargs={"org_slug": org.slug})).status_code == 403
