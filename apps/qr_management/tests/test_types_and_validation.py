import pytest
from django.core.exceptions import ValidationError

from apps.qr_management.models import BlockedDomain
from apps.qr_management.types import TYPES, LinksForm, get_type
from apps.qr_management.validators import validate_destination_url

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("url", [
    "javascript:alert(1)", "data:text/html,hi", "ftp://example.com", "https://user:pw@x.com",
    "http://127.0.0.1/admin", "http://192.168.1.10", "https://qrumy.com/q/abc1234",
    "example", "https://" + "a" * 2100 + ".com",
])
def test_bad_destinations_rejected(url):
    with pytest.raises(ValidationError):
        validate_destination_url(url)


def test_blocked_domains_include_subdomains(settings):
    BlockedDomain.objects.create(domain="Evil.example")
    settings.QRUMY_BLOCKED_DOMAINS = ["phish.test"]
    for url in ("https://evil.example/x", "https://a.b.evil.example", "https://phish.test"):
        with pytest.raises(ValidationError):
            validate_destination_url(url)
    assert validate_destination_url("https://notevil.example") == "https://notevil.example"


def test_static_encoders():
    assert get_type("wifi").encode({"ssid": "Cafe", "password": "p@ss;1", "security": "WPA"}) \
        .startswith("WIFI:")
    assert "WIFI:" in get_type("wifi").encode({"ssid": "Open", "security": "nopass"})
    assert get_type("phone").encode({"phone": "+994501234567"}) == "tel:+994501234567"
    assert get_type("sms").encode({"phone": "+99450", "message": "Salam"}) == "SMSTO:+99450:Salam"
    email = get_type("email").encode({"email": "a@b.az", "subject": "Hi"})
    assert email.startswith("mailto:a@b.az")
    assert get_type("whatsapp").encode({"phone": "+994 50 123", "message": "Salam dünya"}) == \
        "https://wa.me/99450123?text=Salam%20d%C3%BCnya"
    assert "query=40.4%2C49.8" in get_type("location").encode(
        {"latitude": "40.4", "longitude": "49.8"})
    vcard = get_type("vcard").encode({"first_name": "Aysel", "last_name": "Əliyeva",
                                      "phone": "+99450", "email": "a@b.az"})
    assert vcard.startswith("BEGIN:VCARD") and "Əliyeva" in vcard


def test_type_modes():
    assert TYPES["wifi"].modes == ("static",)
    assert "dynamic" in TYPES["url"].modes and "static" in TYPES["url"].modes
    assert TYPES["pdf"].hosted_file == ("application/pdf",)


def test_links_form_parsing():
    form = LinksForm(data={
        "title": "Hi", "accent": "green",
        "link_1_platform": "website", "link_1_value": "https://instagram.com/x",
        "link_2_platform": "telegram", "link_2_value": "@mychannel",
        "link_3_platform": "whatsapp", "link_3_value": "+994 50 123 45 67",
        "link_4_platform": "email", "link_4_value": "hi@example.com",
        "link_5_platform": "website", "link_5_value": "example.com", "link_5_label": "Site",
    })
    assert form.is_valid(), form.errors
    assert form.cleaned_data["links"] == [
        {"platform": "instagram", "url": "https://instagram.com/x", "label": ""},
        {"platform": "telegram", "url": "https://t.me/mychannel", "label": ""},
        {"platform": "whatsapp", "url": "https://wa.me/994501234567", "label": ""},
        {"platform": "email", "url": "mailto:hi@example.com", "label": ""},
        {"platform": "website", "url": "https://example.com", "label": "Site"}]
    assert form.cleaned_data["accent"] == "green"
    assert not any(k.startswith("link_") for k in form.cleaned_data)
    bad = LinksForm(data={"title": "Hi", "link_1_platform": "website",
                          "link_1_value": "javascript:alert(1)"})
    assert not bad.is_valid() and "link_1_value" in bad.errors
    assert not LinksForm(data={"title": "Hi"}).is_valid()


def test_links_initial_from_old_and_new_payloads():
    old = LinksForm.initial_from({"title": "Hi", "links": [
        {"label": "https://youtube.com/@x", "url": "https://youtube.com/@x"}]})
    assert old["link_1_platform"] == "youtube" and old["link_1_label"] == ""
    new = LinksForm.initial_from({"title": "Hi", "links": [
        {"platform": "email", "url": "mailto:a@b.co", "label": "Write"}]})
    assert new["link_1_value"] == "a@b.co" and new["link_1_label"] == "Write"


def test_social_detect_and_build():
    from apps.qr_management import social

    assert social.detect("https://www.instagram.com/x") == "instagram"
    assert social.detect("youtu.be/abc") == "youtube"
    assert social.detect("https://example.com") == "website"
    assert social.build_url("tiktok", "@cafe") == "https://www.tiktok.com/@cafe"
    assert social.build_url("instagram", "instagram.com/cafe") == "instagram.com/cafe"
    assert social.build_url("phone", "+994 (50) 1") == "tel:+994501"
    assert 'fill="#E1306C"' in social.icon_tile("instagram")
    assert social.text_color("snapchat") == "#111111"


def test_phone_validation():
    form = get_type("phone").form(data={"phone": "abc"})
    assert not form.is_valid()
    form = get_type("phone").form(data={"phone": "+994 (50) 123-45-67"})
    assert form.is_valid() and form.cleaned_data["phone"] == "+994501234567"
