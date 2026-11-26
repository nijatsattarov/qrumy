import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.cards import services
from apps.cards.models import Card, CardDaily
from apps.qr_management.models import QRCode

pytestmark = pytest.mark.django_db


@pytest.fixture
def card(make_org):
    org = make_org()
    return services.create_card(organization=org, actor=org.owner,
                                data={"name": "Aysel Məmmədova", "kind": "person",
                                      "template": "modern"})


def _url(card, name, **kw):
    return reverse(name, kwargs={"org_slug": card.organization.slug, "pk": card.pk, **kw})


def test_wizard_steps_save_and_continue(client, card, jpeg_bytes):
    client.force_login(card.organization.owner)
    r = client.post(_url(card, "card_step", step="profile"), {
        "name": "Aysel M", "headline": "Sales", "company": "Aroma", "about": "Hi",
        "photo": SimpleUploadedFile("a.jpg", jpeg_bytes, content_type="image/jpeg"),
        "next": "contact"})
    assert r.status_code == 302 and r["Location"].endswith("/edit/contact/")
    r = client.post(_url(card, "card_step", step="contact"), {
        "phone": "+994 50 123 45 67", "email": "a@example.com", "website": "example.com",
        "address": "Baku", "next": "social"})
    assert r.status_code == 302
    r = client.post(_url(card, "card_step", step="social"), {
        "link_1_platform": "website", "link_1_value": "instagram.com/aroma",
        "link_2_platform": "whatsapp", "link_2_value": "+994501234567", "next": "gallery"})
    assert r.status_code == 302
    r = client.post(_url(card, "card_step", step="design"), {
        "kind": "person", "template": "bold", "accent_color": "#dd2590", "next": "design"})
    card.refresh_from_db()
    assert card.name == "Aysel M" and card.photo and card.website == "https://example.com"
    assert [link["platform"] for link in card.links] == ["instagram", "whatsapp"]
    assert card.template == "bold" and card.accent_color == "#DD2590"
    for step in ("design", "profile", "contact", "social", "gallery", "share"):
        assert client.get(_url(card, "card_step", step=step)).status_code == 200


def test_bad_color_rejected(client, card):
    client.force_login(card.organization.owner)
    r = client.post(_url(card, "card_step", step="design"),
                    {"kind": "person", "template": "classic", "accent_color": "red"})
    assert r.status_code == 200 and "valid color" in r.content.decode()


def test_publish_creates_qr_and_public_page(client, card):
    assert client.get(card.public_path).status_code == 404  # draft
    client.force_login(card.organization.owner)
    client.post(_url(card, "card_publish"), {"publish": "1"})
    card.refresh_from_db()
    assert card.is_published and card.qr_code.qr_type == "card"
    from apps.qr_management.types import get_type

    dest = get_type("card").destination(card.qr_code.payload)
    assert dest.endswith(f"/c/{card.public_token}?src=qr")
    client.logout()
    body = client.get(card.public_path, HTTP_USER_AGENT="Mozilla/5.0 (iPhone)").content.decode()
    assert "Aysel Məmmədova" in body and "contact.vcf" in body
    assert CardDaily.objects.get(card=card).views == 1
    client.get(card.public_path, HTTP_USER_AGENT="Googlebot/2.1")
    assert CardDaily.objects.get(card=card).views == 1  # bots are not counted


def test_unpublish_hides_and_pauses_nothing_else(client, card):
    services.set_published(card=card, actor=card.organization.owner, published=True)
    services.set_published(card=card, actor=card.organization.owner, published=False)
    assert client.get(card.public_path).status_code == 404


def test_vcard_and_link_click(client, card):
    card.phone, card.email, card.company = "+994501234567", "a@b.co", "Aroma; MMC"
    card.links = [{"platform": "instagram", "url": "https://instagram.com/x", "label": ""},
                  {"platform": "x", "url": "javascript:alert(1)", "label": ""}]
    card.is_published = True
    card.save()
    ua = {"HTTP_USER_AGENT": "Mozilla/5.0 (iPhone)"}
    vcf = client.get(f"{card.public_path}/contact.vcf", **ua)
    text = vcf.content.decode()
    assert vcf["Content-Type"].startswith("text/vcard")
    assert "FN:Aysel Məmmədova" in text and r"ORG:Aroma\; MMC" in text
    assert "TEL;TYPE=CELL:+994501234567" in text
    r = client.get(f"{card.public_path}/go/0", **ua)
    assert r.status_code == 302 and r["Location"] == "https://instagram.com/x"
    assert client.get(f"{card.public_path}/go/1").status_code == 404  # unsafe scheme
    assert client.get(f"{card.public_path}/go/9").status_code == 404
    daily = CardDaily.objects.get(card=card)
    assert (daily.saves, daily.clicks) == (1, 1)


def test_theme_css(client, card):
    card.accent_color = "#FFFC00"
    card.save()
    css = client.get(f"{card.public_path}/theme.css").content.decode()
    assert "--card-accent:#FFFC00" in css and "--card-on-accent:#101B3A" in css


def test_gallery_limit_and_delete(client, card, jpeg_bytes):
    client.force_login(card.organization.owner)
    for _ in range(13):
        client.post(_url(card, "card_photo_add"),
                    {"image": SimpleUploadedFile("p.jpg", jpeg_bytes, content_type="image/jpeg")})
    assert card.photos.count() == 12
    photo = card.photos.first()
    client.post(_url(card, "card_photo_delete", photo_id=photo.pk))
    assert card.photos.count() == 11


def test_delete_requires_name_and_pauses_qr(client, card):
    services.set_published(card=card, actor=card.organization.owner, published=True)
    qr_id = card.qr_code_id
    client.force_login(card.organization.owner)
    client.post(_url(card, "card_delete"), {"confirm": "wrong"})
    assert Card.objects.filter(pk=card.pk).exists()
    client.post(_url(card, "card_delete"), {"confirm": "Aysel Məmmədova"})
    assert not Card.objects.filter(pk=card.pk).exists()
    assert QRCode.objects.get(pk=qr_id).status == "paused"


def test_viewer_cannot_edit(client, card, make_user, add_member):
    viewer = make_user(email="v@example.com")
    add_member(card.organization, viewer, "viewer")
    client.force_login(viewer)
    assert client.get(_url(card, "card_step", step="profile")).status_code == 200
    client.post(_url(card, "card_step", step="profile"), {"name": "Hacked", "next": "profile"})
    card.refresh_from_db()
    assert card.name == "Aysel Məmmədova"
    assert client.post(_url(card, "card_publish"), {"publish": "1"}).status_code == 403


def test_plan_limit(card, settings):
    from apps.subscriptions.models import FeatureOverride

    org = card.organization
    from django.core.cache import cache

    FeatureOverride.objects.create(organization=org, feature_key="cards.max", limit_value=1,
                                   enabled=True)
    cache.clear()
    org = type(org).objects.get(pk=org.pk)  # entitlements are cached on the instance
    with pytest.raises(services.CardError):
        services.create_card(organization=org, actor=org.owner, data={"name": "Second"})


def test_card_list_and_nav(client, card):
    client.force_login(card.organization.owner)
    body = client.get(reverse("card_list", kwargs={"org_slug": card.organization.slug}))
    assert "Aysel Məmmədova" in body.content.decode()
    assert "/cards/" in client.get(
        reverse("dashboard", kwargs={"org_slug": card.organization.slug})).content.decode()
