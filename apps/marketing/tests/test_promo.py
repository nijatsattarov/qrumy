from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.marketing.models import Promo

pytestmark = pytest.mark.django_db


def _promo(**kw):
    data = {"name": "Sale", "title": "Big sale", "message": "30% off", "button_label": "See",
            "button_url": "/pricing/", "coupon_code": "SALE30", "placement": "public"}
    data.update(kw)
    return Promo.objects.create(**data)


def test_promo_shown_on_public_pages(client):
    _promo()
    for url in ("/", "/pricing/", "/blog/"):
        body = client.get(url).content.decode()
        assert 'x-data="promo"' in body and "Big sale" in body and "SALE30" in body


def test_home_only_promo(client):
    _promo(placement="home")
    assert "Big sale" in client.get("/").content.decode()
    assert "Big sale" not in client.get("/pricing/").content.decode()


def test_schedule_inactive_and_language(client):
    _promo(name="old", title="Old offer", ends_at=timezone.now() - timedelta(hours=1))
    _promo(name="soon", title="Future offer", starts_at=timezone.now() + timedelta(days=1))
    _promo(name="off", title="Off offer", is_active=False)
    _promo(name="az", title="Endirim", language="az")
    en = client.get("/").content.decode()
    assert not any(t in en for t in ("Old offer", "Future offer", "Off offer", "Endirim"))
    assert "Endirim" in client.get("/az/").content.decode()


def test_audience_and_dashboard(client, make_org):
    _promo(title="Guests only", audience="guests")
    _promo(name="app", title="Upgrade inside", placement="app", audience="users", priority=5)
    assert "Guests only" in client.get("/").content.decode()
    org = make_org()
    client.force_login(org.owner)
    assert "Guests only" not in client.get("/").content.decode()
    assert "Upgrade inside" in client.get(f"/app/{org.slug}/").content.decode()


def test_highest_priority_wins(client):
    _promo(name="a", title="Low", priority=1)
    _promo(name="b", title="High", priority=9)
    body = client.get("/").content.decode()
    assert "High" in body and ">Low<" not in body


def test_button_url_must_be_safe():
    for bad in ("javascript:alert(1)", "//evil.example", "http://plain.example"):
        with pytest.raises(ValidationError):
            Promo(name="x", title="x", message="x", button_url=bad).full_clean()
    Promo(name="x", title="x", message="x", button_url="https://qrumy.com/x").full_clean()


def test_admin_lists_promos(client, make_user):
    from allauth.mfa.models import Authenticator

    staff = make_user(email="s@example.com", is_staff=True, is_superuser=True)
    Authenticator.objects.create(user=staff, type=Authenticator.Type.TOTP, data={})
    client.force_login(staff)
    _promo()
    assert client.get("/qadmin/marketing/promo/").status_code == 200
    assert client.get("/qadmin/marketing/promo/add/").status_code == 200
