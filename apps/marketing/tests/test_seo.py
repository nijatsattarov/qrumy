import json
import re

import pytest
from django.urls import reverse

from apps.marketing.models import SeoPage, SeoSettings, SiteEvent
from apps.marketing.seo_tools import TOOLS

pytestmark = pytest.mark.django_db
UA = {"HTTP_USER_AGENT": "Mozilla/5.0 (Windows NT 10.0; Win64) Chrome/130.0 Safari/537.36"}
STYLE = {"s-fg": "#101B3A", "s-bg": "#FFFFFF", "s-eye_color": "#101B3A",
         "s-module_shape": "square", "s-eye_frame": "square", "s-eye_ball": "square",
         "s-frame": "none", "s-frame_color": "#101B3A"}


def _head(body):
    title = re.search(r"<title>(.*?)</title>", body, re.S).group(1).strip()
    desc = re.search(r'name="description" content="([^"]*)"', body).group(1)
    h1 = re.findall(r"<h1[\s>].*?</h1>", body, re.S)
    return title, desc, h1


def _ld(body):
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', body, re.S)
    data = [json.loads(b) for b in blocks]
    types = []
    for d in data:
        types += [n["@type"] for n in d.get("@graph", [])] or [d.get("@type")]
    return data, types


def test_homepage_targets_free_qr_code_generator(client):
    body = client.get("/").content.decode()
    title, desc, h1 = _head(body)
    assert title.startswith("Free QR Code Generator") and "Qrumy" in title
    assert "No signup required" in desc and len(h1) == 1 and "Free QR Code Generator" in h1[0]
    _, types = _ld(body)
    assert {"Organization", "WebSite", "WebApplication", "FAQPage"} <= set(types)
    assert 'property="og:image" content="' in body and "og-default.png" in body
    for t in TOOLS:  # internal links to every tool page
        assert f'href="{reverse(t.url_name)}"' in body
    az = client.get("/az/").content.decode()
    assert _head(az)[0].startswith("Pulsuz QR Kod Generatoru")


@pytest.mark.parametrize("lang", ["en", "az"])
def test_tool_pages_unique_and_complete(client, lang):
    titles, descs, h1s = set(), set(), set()
    prefix = "" if lang == "en" else "/az"
    for tool in TOOLS:
        url = f"{prefix}/{tool.slug}/"
        r = client.get(url)
        assert r.status_code == 200, url
        body = r.content.decode()
        title, desc, h1 = _head(body)
        assert len(h1) == 1 and 'id="gen-form"' in body  # the free generator is on the page
        assert f'name="type" value="{tool.type_key}"' in body
        assert f'rel="canonical" href="http://localhost:8000{url}"' in body
        for code in ("en", "az", "x-default"):
            assert f'hreflang="{code}"' in body
        _, types = _ld(body)
        assert {"WebApplication", "BreadcrumbList", "FAQPage"} <= set(types)
        assert "/accounts/signup/" in body  # a CTA for advanced features, never a wall
        titles.add(title), descs.add(desc), h1s.add(h1[0])
        assert 30 <= len(title) <= 70 and 110 <= len(desc) <= 165, (url, title, desc)
    assert len(titles) == len(descs) == len(h1s) == len(TOOLS)


def test_tool_page_generates_and_downloads_without_login(client):
    r = client.post("/qr-generator/download/png/",
                    {"type": "wifi", "c-ssid": "Cafe", "c-security": "WPA",
                     "c-password": "secret123", "next": "/wifi-qr-code-generator/", **STYLE})
    assert r.status_code == 200 and r["Content-Type"] == "image/png"
    r = client.post("/qr-generator/download/png/", {"type": "wifi", "c-ssid": "",
                                                    "next": "/wifi-qr-code-generator/", **STYLE})
    assert r.status_code == 302 and r["Location"].startswith("/wifi-qr-code-generator/?type=")
    r = client.post("/qr-generator/download/png/", {"type": "wifi", "c-ssid": "",
                                                    "next": "https://evil.example/", **STYLE})
    assert r["Location"].startswith("/?type=")  # no open redirect


def test_robots_and_sitemap_use_canonical_domain(client, settings):
    settings.SITE_URL = "https://qrumy.com"
    robots = client.get("/robots.txt").content.decode()
    assert "Sitemap: https://qrumy.com/sitemap.xml" in robots
    for path in ("/app/", "/accounts/", "/qr-generator/", "/q/"):
        assert f"Disallow: {path}" in robots
    assert settings.QRUMY_ADMIN_PATH not in robots  # never reveal the admin path
    xml = client.get("/sitemap.xml", HTTP_HOST="127.0.0.1").content.decode()
    assert "http://127.0.0.1" not in xml and "<loc>https://qrumy.com/</loc>" in xml
    for tool in TOOLS:
        assert f"https://qrumy.com/{tool.slug}/" in xml
        assert f"https://qrumy.com/az/{tool.slug}/" in xml
    assert "https://qrumy.com/contact/" in xml and "/blog/static-vs-dynamic/" in xml
    assert "/accounts/" not in xml and "/app/" not in xml
    assert "<lastmod>" in xml


def test_private_pages_not_indexed(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    r = client.get(f"/app/{org.slug}/")
    assert r["X-Robots-Tag"] == "noindex, nofollow"
    assert 'content="noindex, nofollow"' in r.content.decode()
    assert client.get("/qadmin/")["X-Robots-Tag"] == "noindex, nofollow"
    assert "X-Robots-Tag" not in client.get("/")


def test_404_page(client, settings):
    settings.DEBUG = False
    r = client.get("/no-such-page/")
    body = r.content.decode()
    assert r.status_code == 404 and "noindex" in body
    assert reverse("tool_wifi_qr_code_generator") in body and "#generator" in body


def test_admin_overrides_and_settings(client):
    row = SeoPage.objects.get(page="tool:wifi-qr-code-generator", language="en")
    row.title, row.h1 = "WiFi QR Code — custom", "Custom H1"
    row.meta_description = "Custom description."
    row.keywords, row.noindex = "wifi qr, guest wifi", True
    row.save()
    s = SeoSettings.load()
    s.google_site_verification = "abc123token"
    s.save()
    body = client.get("/wifi-qr-code-generator/").content.decode()
    title, desc, h1 = _head(body)
    assert title == "WiFi QR Code — custom | Qrumy" and desc == "Custom description."
    assert "Custom H1" in h1[0] and 'name="keywords" content="wifi qr, guest wifi"' in body
    assert 'content="noindex, follow"' in body
    assert '<meta name="google-site-verification" content="abc123token">' in body
    az = client.get("/az/wifi-qr-code-generator/").content.decode()
    assert "noindex" not in re.search(r'name="robots" content="([^"]+)"', az).group(1)


def test_blog_post_seo(client):
    from apps.marketing.models import Post

    post = Post.objects.get(slug="static-vs-dynamic")
    post.seo_title, post.meta_description = "Static vs Dynamic QR Codes Guide", "Short desc."
    post.save()
    body = client.get("/blog/static-vs-dynamic/").content.decode()
    title, desc, _ = _head(body)
    assert title == "Static vs Dynamic QR Codes Guide | Qrumy" and desc == "Short desc."
    data, types = _ld(body)
    assert {"BlogPosting", "BreadcrumbList", "Organization"} <= set(types)
    posting = next(n for n in data[0]["@graph"] if n["@type"] == "BlogPosting")
    assert posting["image"].endswith(".jpg") and posting["dateModified"]
    assert 'property="og:type" content="article"' in body
    assert 'property="article:published_time"' in body
    assert reverse("tool_qr_code_generator") in body  # contextual tool links


def test_funnel_events(client, django_capture_on_commit_callbacks):
    client.get("/wifi-qr-code-generator/", HTTP_REFERER="https://www.google.com/", **UA)
    client.get("/qr-generator/fields/?type=sms", **UA)
    data = {"type": "text", "c-text": "hi", "page": "tool:text-qr-code-generator", **STYLE}
    client.post("/qr-generator/preview/", data, **UA)
    client.post("/qr-generator/preview/", {**data, "counted": "1"}, **UA)  # same view: once
    client.post("/qr-generator/download/svg/", data, **UA)
    client.post("/qr-generator/download/png/", data, **UA)
    client.get("/pricing/", **UA)
    client.post("/t/", json.dumps({"e": "cta_dynamic_click", "p": "home"}),
                content_type="application/json", **UA)
    client.post("/t/", json.dumps({"e": "signup_completed"}), content_type="application/json",
                **UA)  # not accepted from the browser
    client.get("/", HTTP_USER_AGENT="Googlebot/2.1")  # bots are ignored
    counts = {e.name: e.count for e in SiteEvent.objects.all()}
    assert counts["tool_view"] == 1 and counts["qr_type_selected"] == 1
    assert counts["qr_generated"] == 1 and counts["qr_download_svg"] == 1
    assert counts["qr_download_png"] == 1 and counts["pricing_view"] == 1
    assert counts["cta_dynamic_click"] == 1 and "signup_completed" not in counts
    assert SiteEvent.objects.get(name="tool_view").source == "search"


def test_signup_and_subscription_events(client, make_org):
    from apps.subscriptions.models import Plan
    from apps.subscriptions.services import change_plan

    client.post(reverse("account_signup"), {
        "full_name": "A", "email": "new@example.com", "password1": "a-strong-passphrase-1",
        "password2": "a-strong-passphrase-1", "accept_terms": "on"})
    assert SiteEvent.objects.get(name="signup_completed").count == 1
    org = make_org()
    change_plan(organization=org, plan=Plan.objects.get(key="growth"), gateway="manual")
    assert SiteEvent.objects.get(name="subscription_started").page == "plan:growth"


def test_seo_admin(client, make_user):
    from allauth.mfa.models import Authenticator

    staff = make_user(email="s@example.com", is_staff=True, is_superuser=True)
    Authenticator.objects.create(user=staff, type=Authenticator.Type.TOTP, data={})
    client.force_login(staff)
    assert SeoPage.objects.count() == 32
    body = client.get("/qadmin/marketing/seopage/").content.decode()
    assert "WiFi QR Code Generator" in body
    row = SeoPage.objects.get(page="home", language="az")
    page = client.get(f"/qadmin/marketing/seopage/{row.pk}/change/").content.decode()
    assert "Pulsuz QR Kod Generatoru" in page  # built-in text shown
    assert client.get("/qadmin/marketing/seosettings/").status_code == 200
    assert "Müştəri cəlbi qıfı" in client.get("/qadmin/").content.decode()
