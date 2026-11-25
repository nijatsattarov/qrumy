import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.accounts.legal import LegalDocument, TermsAcceptance
from apps.accounts.models import User
from apps.audit_logs.models import AuditLog
from apps.organizations.models import Membership, Organization

pytestmark = pytest.mark.django_db


def _publish(kind="terms", language="en", version="1"):
    return LegalDocument.objects.create(kind=kind, language=language, version=version,
                                        title=f"{kind} {language}", body="Para one.\n\nTwo.",
                                        published_at=timezone.now())


def test_legal_pages_hidden_until_published(client):
    assert client.get("/terms/").status_code == 404
    assert b"/terms/" not in client.get("/").content
    LegalDocument.objects.create(kind="terms", language="en", version="0", title="Draft",
                                 body="x")  # draft: not shown
    assert client.get("/terms/").status_code == 404
    _publish()
    assert client.get("/terms/").status_code == 200
    assert b'href="/terms/"' in client.get("/").content


def test_legal_page_language_fallback(client):
    _publish(language="en")
    assert b"terms en" in client.get("/az/terms/").content  # no az version yet → English
    _publish(language="az")
    assert b"terms az" in client.get("/az/terms/").content


def test_signup_requires_terms_once_published(client):
    data = {"full_name": "A", "email": "a@example.com", "password1": "a-strong-passphrase-1",
            "password2": "a-strong-passphrase-1"}
    client.post(reverse("account_signup"), data)
    assert User.objects.count() == 1  # no terms published → no checkbox
    _publish(version="2026-12-01")
    _publish(kind="privacy", version="p1")
    client.post(reverse("account_signup"), {**data, "email": "b@example.com"})
    assert not User.objects.filter(email="b@example.com").exists()
    client.post(reverse("account_signup"), {**data, "email": "c@example.com",
                                            "accept_terms": "on"})
    acc = TermsAcceptance.objects.get(user__email="c@example.com")
    assert (acc.terms_version, acc.privacy_version) == ("2026-12-01", "p1")


def test_branded_html_emails(client):
    client.post(reverse("account_signup"), {
        "full_name": "A", "email": "a@example.com", "password1": "a-strong-passphrase-1",
        "password2": "a-strong-passphrase-1"})
    msg = mail.outbox[-1]
    assert "Hello from Qrumy!" in msg.body
    html = msg.alternatives[0][0]
    assert "Confirm your email address" in html and "localhost" not in msg.subject


def test_delete_account(client, make_user, make_org, add_member):
    org = make_org()
    user = make_user(email="leaver@example.com")
    add_member(org, user, "member")
    client.force_login(user)
    client.post(reverse("account_profile"), {"full_name": "Leaver", "language": "en"})
    client.post(reverse("account_delete"), {"password": "wrong", "confirm": "on"})
    assert User.objects.filter(pk=user.pk).exists()
    client.post(reverse("account_delete"), {"password": "correct-horse-battery",
                                            "confirm": "on"})
    assert not User.objects.filter(pk=user.pk).exists()
    assert not Membership.objects.filter(user_id=user.pk).exists()
    assert not AuditLog.objects.filter(actor_email="leaver@example.com").exists()
    assert "_auth_user_id" not in client.session


def test_owner_cannot_delete_account_before_transfer(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    resp = client.post(reverse("account_delete"), {"password": "correct-horse-battery",
                                                   "confirm": "on"})
    assert org.name.encode() in resp.content
    assert User.objects.filter(pk=org.owner.pk).exists()


def test_transfer_ownership_and_delete_org(client, make_user, make_org, add_member, make_qr):
    org = make_org()
    admin = make_user(email="adm@example.com")
    target = add_member(org, admin, "admin")
    make_qr(org)
    url = reverse("organization_danger", kwargs={"org_slug": org.slug})
    client.force_login(admin)
    assert client.post(url, {"action": "delete", "confirm_name": org.name}).status_code == 403
    client.force_login(org.owner)
    client.post(url, {"action": "transfer", "member": target.pk})
    org.refresh_from_db()
    target.refresh_from_db()
    assert org.owner == admin and target.role == "owner"
    assert Membership.objects.get(organization=org, user__email=org.owner.email).role == "owner"
    client.force_login(admin)
    client.post(url, {"action": "delete", "confirm_name": "wrong"})
    assert Organization.objects.filter(pk=org.pk).exists()
    client.post(url, {"action": "delete", "confirm_name": org.name})
    assert not Organization.objects.filter(pk=org.pk).exists()
    assert AuditLog.objects.filter(action="organization.deleted").exists()
