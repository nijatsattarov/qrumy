import json
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.menus import services
from apps.menus.models import Menu, MenuItem, MenuStat

pytestmark = pytest.mark.django_db
UA = {"HTTP_USER_AGENT": "Mozilla/5.0 (iPhone)"}


@pytest.fixture
def menu(make_org):
    org = make_org()
    return services.create_menu(organization=org, actor=org.owner,
                                data={"name": "Main", "currency": "AZN", "language": "az"})


def _u(menu, name, **kw):
    return reverse(name, kwargs={"org_slug": menu.organization.slug, "pk": menu.pk, **kw})


def _add_item(client, menu, cat, **extra):
    data = {"category": cat.pk, "name": "Cappuccino", "description": "Milk foam",
            "price": "5.50", "availability": "available"}
    data.update(extra)
    return client.post(_u(menu, "menu_item_create"), data)


def test_create_with_starter_categories_in_menu_language(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    r = client.post(reverse("menu_create", kwargs={"org_slug": org.slug}),
                    {"name": "Bar", "currency": "USD", "language": "az", "starter": "1"})
    menu = Menu.objects.get(name="Bar")
    assert r.status_code == 302 and r["Location"].endswith(f"/menus/{menu.pk}/")
    assert list(menu.categories.values_list("name", flat=True)) == [
        "İsti içkilər", "Əsas yeməklər", "Desertlər"]


def test_category_crud_and_ordering(client, menu):
    client.force_login(menu.organization.owner)
    for name in ("Drinks", "Food", "Sweets"):
        client.post(_u(menu, "menu_category_create"), {"new-name": name, "new-is_visible": "on"})
    cats = list(menu.categories.all())
    assert [c.name for c in cats] == ["Drinks", "Food", "Sweets"]
    client.post(_u(menu, "menu_category_move", cat_id=cats[2].pk), {"direction": "up"})
    assert list(menu.categories.values_list("name", flat=True)) == ["Drinks", "Sweets", "Food"]
    client.post(_u(menu, "menu_category_update", cat_id=cats[0].pk),
                {f"cat{cats[0].pk}-name": "Coffee", f"cat{cats[0].pk}-description": "Hot"})
    cats[0].refresh_from_db()
    assert cats[0].name == "Coffee" and not cats[0].is_visible  # unchecked = hidden
    client.post(_u(menu, "menu_category_delete", cat_id=cats[1].pk))
    assert menu.categories.count() == 2


def test_item_with_variants_addons_discount(client, menu, jpeg_bytes):
    cat = services.add_category(menu=menu, name="Coffee")
    client.force_login(menu.organization.owner)
    r = _add_item(client, menu, cat, discount_price="4.50", unit="300 ml",
                  tags=["popular", "new"],
                  image=SimpleUploadedFile("c.jpg", jpeg_bytes, content_type="image/jpeg"),
                  variant_1_name="Small", variant_1_price="4,00",
                  variant_2_name="Large", variant_2_price="6",
                  addon_1_name="Extra shot", addon_1_price="1")
    assert r.status_code == 302
    item = MenuItem.objects.get()
    assert item.has_discount and item.discount_percent == 18 and item.image
    assert item.tags == ["popular", "new"]
    assert [(o.kind, o.name, o.price) for o in item.options.all()] == [
        ("variant", "Small", Decimal("4.00")), ("variant", "Large", Decimal("6.00")),
        ("addon", "Extra shot", Decimal("1.00"))]
    # editing replaces the options
    client.post(_u(menu, "menu_item_edit", item_id=item.pk), {
        "category": cat.pk, "name": "Cappuccino", "price": "5.50", "availability": "available",
        "addon_1_name": "Oat milk", "addon_1_price": "0.8"})
    assert [o.name for o in item.options.all()] == ["Oat milk"]


def test_item_validation(client, menu):
    cat = services.add_category(menu=menu, name="Coffee")
    client.force_login(menu.organization.owner)
    r = _add_item(client, menu, cat, discount_price="9")
    assert r.status_code == 200 and "lower than the price" in r.content.decode()
    r = _add_item(client, menu, cat, variant_1_name="Big", variant_1_price="abc")
    assert r.status_code == 200 and MenuItem.objects.count() == 0
    r = _add_item(client, menu, cat, variant_1_price="3")
    assert r.status_code == 200 and "needs a name" in r.content.decode()


def test_cannot_put_item_in_other_menus_category(client, menu, make_org):
    other = services.create_menu(organization=menu.organization, actor=menu.organization.owner,
                                 data={"name": "Other"})
    foreign_cat = services.add_category(menu=other, name="Elsewhere")
    services.add_category(menu=menu, name="Mine")
    client.force_login(menu.organization.owner)
    r = _add_item(client, menu, foreign_cat)
    assert r.status_code == 200 and MenuItem.objects.count() == 0


def test_public_page_availability_and_stats(client, menu):
    cat = services.add_category(menu=menu, name="Coffee")
    hidden_cat = services.add_category(menu=menu, name="Secret")
    hidden_cat.is_visible = False
    hidden_cat.save()
    for name, availability, c in (("Latte", "available", cat), ("Mocha", "sold_out", cat),
                                  ("Ghost", "hidden", cat), ("Secret dish", "available",
                                                             hidden_cat)):
        MenuItem.objects.create(organization=menu.organization, menu=menu, category=c,
                                name=name, price=Decimal("3"), availability=availability)
    assert client.get(menu.public_path).status_code == 404  # not published
    services.set_published(menu=menu, actor=menu.organization.owner, published=True)
    body = client.get(menu.public_path, **UA).content.decode()
    assert "Latte" in body and "Mocha" in body and "Ghost" not in body
    assert "Secret dish" not in body and 'lang="az"' in body and "Menyuda axtarın" in body
    assert MenuStat.objects.get(menu=menu, kind="view").count == 1
    latte = MenuItem.objects.get(name="Latte")
    url = reverse("menu_event", kwargs={"token": menu.public_token})
    for _ in range(2):
        client.post(url, json.dumps({"t": "item", "id": latte.pk}),
                    content_type="application/json", **UA)
    client.post(url, json.dumps({"t": "category", "id": cat.pk}),
                content_type="application/json", **UA)
    assert MenuStat.objects.get(kind="item", object_id=latte.pk).count == 2
    assert client.post(url, json.dumps({"t": "item", "id": 999999}),
                       content_type="application/json", **UA).status_code == 400
    report = services.report(menu)
    assert report["views"] == 1 and report["top_items"][0] == {"name": "Latte", "count": 2}
    assert report["top_categories"][0]["name"] == "Coffee"


def test_events_for_other_menus_items_rejected(client, menu):
    services.set_published(menu=menu, actor=menu.organization.owner, published=True)
    other = services.create_menu(organization=menu.organization, actor=menu.organization.owner,
                                 data={"name": "Other"})
    cat = services.add_category(menu=other, name="X")
    item = MenuItem.objects.create(organization=menu.organization, menu=other, category=cat,
                                   name="Y", price=1)
    url = reverse("menu_event", kwargs={"token": menu.public_token})
    assert client.post(url, json.dumps({"t": "item", "id": item.pk}),
                       content_type="application/json", **UA).status_code == 400


def test_publish_creates_qr_and_picker_tiles(client, menu):
    from apps.qr_management.types import TYPES, get_type, listed_types

    client.force_login(menu.organization.owner)
    client.post(_u(menu, "menu_publish"), {"publish": "1"})
    menu.refresh_from_db()
    assert menu.qr_code.qr_type == "digital_menu"
    assert get_type("digital_menu").destination(menu.qr_code.payload).endswith(
        f"/m/{menu.public_token}?src=qr")
    assert "menu" in TYPES and "menu" not in [t.key for t in listed_types()]
    picker = client.get(reverse("qr_choose_type", kwargs={"org_slug": menu.organization.slug}))
    body = picker.content.decode()
    assert f"/app/{menu.organization.slug}/menus/new/" in body
    assert f"/app/{menu.organization.slug}/cards/new/" in body
    for tab in ("menu_builder", "menu_settings", "menu_share", "menu_preview"):
        assert client.get(_u(menu, tab)).status_code == 200


def test_settings_theme_and_delete(client, menu):
    client.force_login(menu.organization.owner)
    r = client.post(_u(menu, "menu_settings"), {
        "name": "Main", "currency": "EUR", "language": "en", "layout": "grid",
        "accent_color": "#b54708", "hours": "9-23"})
    assert r.status_code == 302
    menu.refresh_from_db()
    assert (menu.currency, menu.layout, menu.accent_color) == ("EUR", "grid", "#B54708")
    css = client.get(f"{menu.public_path}/theme.css").content.decode()
    assert "--menu-accent:#B54708" in css
    services.set_published(menu=menu, actor=menu.organization.owner, published=True)
    qr_id = menu.qr_code_id
    client.post(_u(menu, "menu_delete"), {"confirm": "nope"})
    assert Menu.objects.filter(pk=menu.pk).exists()
    client.post(_u(menu, "menu_delete"), {"confirm": "Main"})
    assert not Menu.objects.filter(pk=menu.pk).exists()
    from apps.qr_management.models import QRCode

    assert QRCode.objects.get(pk=qr_id).status == "paused"


def test_quick_availability_and_viewer_rights(client, menu, make_user, add_member):
    cat = services.add_category(menu=menu, name="Coffee")
    item = MenuItem.objects.create(organization=menu.organization, menu=menu, category=cat,
                                   name="Latte", price=3)
    client.force_login(menu.organization.owner)
    client.post(_u(menu, "menu_item_action", item_id=item.pk), {"action": "sold_out"})
    item.refresh_from_db()
    assert item.availability == "sold_out"
    viewer = make_user(email="v@example.com")
    add_member(menu.organization, viewer, "viewer")
    client.force_login(viewer)
    assert client.get(_u(menu, "menu_builder")).status_code == 200
    assert client.post(_u(menu, "menu_item_action", item_id=item.pk),
                       {"action": "available"}).status_code == 403


def test_plan_limit(menu):
    from django.core.cache import cache

    from apps.subscriptions.models import FeatureOverride

    org = menu.organization
    FeatureOverride.objects.create(organization=org, feature_key="menus.max", limit_value=1)
    cache.clear()
    org = type(org).objects.get(pk=org.pk)
    with pytest.raises(services.MenuError):
        services.create_menu(organization=org, actor=org.owner, data={"name": "2nd"})
