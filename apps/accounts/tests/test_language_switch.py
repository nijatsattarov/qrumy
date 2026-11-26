import pytest

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("cookie,url,expected", [
    ("az", "/lang/en/?next=/az/blog/", "/blog/"),
    ("en", "/lang/az/?next=/blog/", "/az/blog/"),
    ("az", "/lang/en/?next=/az/%3Ftype%3Dwifi", "/?type=wifi"),
    ("en", "/lang/az/?next=/app/x/", "/app/x/"),
    ("az", "/lang/en/?next=https://evil.example/", "/"),
    ("en", "/lang/xx/?next=/pricing/", "/pricing/"),
])
def test_switch_language_returns_to_the_same_page(client, cookie, url, expected):
    client.cookies["django_language"] = cookie
    resp = client.get(url)
    assert resp.status_code == 302 and resp["Location"] == expected


def test_switch_language_sets_cookie_and_user_preference(client, make_user):
    user = make_user()
    client.force_login(user)
    resp = client.get("/lang/az/?next=/")
    assert resp.cookies["django_language"].value == "az"
    user.refresh_from_db()
    assert user.language == "az"


def test_switcher_is_plain_links(client):
    body = client.get("/blog/").content.decode()
    assert 'href="/lang/az/?next=/blog/"' in body and "data-autosubmit" not in body


def test_marketing_language_is_remembered_for_signup(client):
    client.get("/az/")
    assert client.cookies["django_language"].value == "az"
    page = client.get("/accounts/signup/")
    assert page.content.decode().count('lang="az"') >= 1


def test_language_switch_in_app_user_menu(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    body = client.get(f"/app/{org.slug}/").content.decode()
    assert "/lang/az/?next=" in body
