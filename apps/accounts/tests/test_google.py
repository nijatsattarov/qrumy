from types import SimpleNamespace

import pytest
from django.test import override_settings

from apps.accounts.legal import TermsAcceptance
from apps.accounts.signals import on_user_signed_up

pytestmark = pytest.mark.django_db

GOOGLE = {"google": {"APPS": [{"client_id": "id.apps.googleusercontent.com",
                               "secret": "s", "key": ""}],
                     "SCOPE": ["profile", "email"]}}


def test_no_google_button_without_keys(client):
    assert "Continue with Google" not in client.get("/accounts/login/").content.decode()


@override_settings(SOCIALACCOUNT_PROVIDERS=GOOGLE)
def test_google_button_on_login_and_signup(client):
    for url in ("/accounts/login/", "/accounts/signup/"):
        body = client.get(url).content.decode()
        assert "Continue with Google" in body and "/accounts/google/login/" in body
    assert "Terms of Service" in client.get("/accounts/login/").content.decode()


def test_google_signup_records_terms_name_and_language(make_user, rf):
    user = make_user(email="g@example.com", full_name="")
    request = rf.get("/")
    request.LANGUAGE_CODE = "az"
    social = SimpleNamespace(account=SimpleNamespace(extra_data={"name": "Leyla Əliyeva"}))
    on_user_signed_up(sender=None, request=request, user=user, sociallogin=social)
    user.refresh_from_db()
    assert user.full_name == "Leyla Əliyeva" and user.language == "az"
    assert TermsAcceptance.objects.get(user=user).terms_version == "2026-11-25"


def test_email_signup_is_not_touched(make_user, rf):
    user = make_user(email="e@example.com")
    on_user_signed_up(sender=None, request=rf.get("/"), user=user)
    assert not TermsAcceptance.objects.filter(user=user).exists()
