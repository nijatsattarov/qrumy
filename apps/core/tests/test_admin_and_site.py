import pytest
from allauth.mfa.models import Authenticator
from django.urls import reverse

from apps.audit_logs.models import AuditLog
from apps.organizations.models import Organization

pytestmark = pytest.mark.django_db
ADMIN = "/qadmin/"


def test_admin_hidden_from_anonymous_and_non_staff(client, make_user):
    resp = client.get(ADMIN)
    assert resp.status_code == 302 and resp["Location"].startswith("/accounts/login/")
    client.force_login(make_user())
    assert client.get(ADMIN).status_code == 404


def test_django_admin_login_view_is_never_used(client):
    resp = client.get(ADMIN + "login/")
    assert resp["Location"].startswith("/accounts/login/")


def test_staff_without_mfa_must_enable_it(client, make_user):
    client.force_login(make_user(email="s@example.com", is_staff=True, is_superuser=True))
    resp = client.get(ADMIN)
    assert resp.status_code == 302 and resp["Location"] == reverse("mfa_activate_totp")


def test_staff_with_mfa_can_use_admin_and_suspend_org(client, make_user, make_org):
    staff = make_user(email="s@example.com", is_staff=True, is_superuser=True)
    Authenticator.objects.create(user=staff, type=Authenticator.Type.TOTP, data={})
    client.force_login(staff)
    assert client.get(ADMIN).status_code == 200
    org = make_org()
    client.post(ADMIN + "organizations/organization/",
                {"action": "suspend", "_selected_action": [org.pk]})
    org.refresh_from_db()
    assert org.status == Organization.Status.SUSPENDED
    assert AuditLog.objects.filter(action="admin.organization.suspended",
                                   is_staff_action=True).exists()
    for path in ("accounts/user/", "subscriptions/plan/", "billing/planassignment/add/",
                 "audit_logs/auditlog/"):
        assert client.get(ADMIN + path).status_code == 200, path


def test_marketing_pages_and_seo(client):
    home = client.get("/")
    body = home.content.decode()
    assert home.status_code == 200
    assert 'rel="canonical"' in body and 'hreflang="az"' in body and "og:title" in body
    assert 'name="robots" content="index' in body
    az = client.get("/az/").content.decode()
    assert "Pulsuz başlayın" in az and 'lang="az"' in az
    assert client.get("/pricing/").status_code == 200
    assert "Disallow: /app/" in client.get("/robots.txt").content.decode()
    sitemap = client.get("/sitemap.xml").content.decode()
    assert "/az/pricing/" in sitemap


def test_app_pages_are_noindex(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    body = client.get(reverse("dashboard", kwargs={"org_slug": org.slug})).content.decode()
    assert "noindex" in body


def test_security_headers(client):
    resp = client.get("/")
    assert "default-src 'self'" in resp["Content-Security-Policy"]
    assert resp["X-Frame-Options"] == "DENY"
    assert resp["X-Content-Type-Options"] == "nosniff"


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok", "database": True}


def test_slugify_az():
    from apps.core.utils import slugify_az

    assert slugify_az("Şəki Çay Evi") == "seki-cay-evi"
    assert slugify_az("Gəncə Ağ Şəhər") == "gence-ag-seher"


def test_hash_ip_is_salted_and_not_reversible():
    from datetime import date

    from apps.core.utils import hash_ip

    a = hash_ip("1.2.3.4", date(2026, 1, 1))
    assert a != "1.2.3.4" and a != hash_ip("1.2.3.4", date(2026, 1, 2))


def test_healthz_bypasses_host_validation(client, settings):
    settings.ALLOWED_HOSTS = ["qrumy.com"]
    assert client.get("/healthz", HTTP_HOST="127.0.0.1:8000").status_code == 200


def test_permissions_policy_header(client):
    assert "camera=()" in client.get("/")["Permissions-Policy"]


def test_admin_is_in_azerbaijani(client, make_user):
    staff = make_user(email="az@example.com", is_staff=True, is_superuser=True)
    Authenticator.objects.create(user=staff, type=Authenticator.Type.TOTP, data={})
    client.force_login(staff)
    body = client.get(ADMIN, HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert 'lang="az"' in body
    for text in ("Qeydiyyatdan keçən istifadəçilər", "Nasazlıq bildirişləri",
                 "Planlaşdırılmış tapşırıqlar", "Şərtlərin qəbulları"):
        assert text in body, text
    assert "Axtarmaq üçün yazın" in client.get(ADMIN + "accounts/user/").content.decode()
