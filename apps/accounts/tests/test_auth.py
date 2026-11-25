import pytest
from django.core import mail
from django.urls import reverse

from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_signup_creates_unverified_user_and_sends_verification(client):
    resp = client.post(reverse("account_signup"), {
        "full_name": "Aysel Məmmədova", "email": "Aysel@Example.com",
        "password1": "a-strong-passphrase-1", "password2": "a-strong-passphrase-1",
        "accept_terms": "on",
    })
    assert resp.status_code == 302
    user = User.objects.get()
    assert user.email == "aysel@example.com"  # normalized
    assert user.full_name == "Aysel Məmmədova"
    assert len(mail.outbox) == 1
    # Mandatory verification: not logged in yet
    assert "_auth_user_id" not in client.session


def test_unverified_user_cannot_sign_in(client, make_user):
    make_user(email="u@example.com", verified=False)
    resp = client.post(reverse("account_login"),
                       {"login": "u@example.com", "password": "correct-horse-battery"})
    assert "_auth_user_id" not in client.session
    assert resp.status_code == 302 and "confirm-email" in resp["Location"]


def test_verified_user_signs_in_case_insensitively(client, make_user):
    make_user(email="u@example.com")
    client.post(reverse("account_login"),
                {"login": "U@Example.COM", "password": "correct-horse-battery"})
    assert "_auth_user_id" in client.session


def test_wrong_password_rejected(client, make_user):
    make_user(email="u@example.com")
    client.post(reverse("account_login"), {"login": "u@example.com", "password": "nope"})
    assert "_auth_user_id" not in client.session


def test_password_reset_sends_email(client, make_user):
    make_user(email="u@example.com")
    client.post(reverse("account_reset_password"), {"email": "u@example.com"})
    assert len(mail.outbox) == 1


def test_password_is_hashed(make_user):
    user = make_user()
    assert user.password != "correct-horse-battery" and user.check_password("correct-horse-battery")


def test_language_switch_persists_on_user(client, make_user):
    user = make_user()
    client.force_login(user)
    client.post(reverse("set_language"), {"language": "az", "next": "/"})
    user.refresh_from_db()
    assert user.language == "az"


def test_app_pages_use_user_language(client, make_user, make_org, add_member):
    user = make_user(language="az")
    org = make_org()
    add_member(org, user)
    client.force_login(user)
    resp = client.get(reverse("dashboard", kwargs={"org_slug": org.slug}))
    assert "Ümumi baxış" in resp.content.decode()


def test_profile_update(client, make_user):
    user = make_user()
    client.force_login(user)
    client.post(reverse("account_profile"), {"full_name": "New Name", "language": "en"})
    user.refresh_from_db()
    assert user.full_name == "New Name"


def test_auth_pages_follow_language_cookie_for_anonymous(client, settings):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "az"
    body = client.get(reverse("account_login")).content.decode()
    assert 'lang="az"' in body


def test_auth_pages_follow_browser_language(client):
    body = client.get(reverse("account_signup"), HTTP_ACCEPT_LANGUAGE="az").content.decode()
    assert 'lang="az"' in body


def test_marketing_root_stays_english_with_az_cookie(client, settings):
    client.cookies[settings.LANGUAGE_COOKIE_NAME] = "az"
    assert 'lang="en"' in client.get("/").content.decode()
