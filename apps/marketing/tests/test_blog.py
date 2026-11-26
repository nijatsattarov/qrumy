from datetime import timedelta

import pytest
from django.utils import timezone

from apps.marketing.models import Post
from apps.marketing.templatetags.legal import content_markup

pytestmark = pytest.mark.django_db


def _post(**kw):
    data = {"language": "en", "title": "Hello", "slug": "hello", "excerpt": "Short",
            "body": "## Head\nText", "published_at": timezone.now()}
    data.update(kw)
    return Post.objects.create(**data)


def test_seeded_posts_listed_per_language(client):
    en = client.get("/blog/").content.decode()
    az = client.get("/az/blog/").content.decode()
    assert "Static vs dynamic QR codes" in en and "Statik və dinamik" not in en
    assert "Statik və dinamik QR kod" in az and "Static vs dynamic" not in az


def test_post_page_seo_and_markup(client):
    body = client.get("/blog/static-vs-dynamic/").content.decode()
    assert "<h2>What is a static QR code?</h2>" in body
    assert '"@type": "BlogPosting"' in body and 'property="og:type" content="article"' in body
    assert 'rel="alternate" hreflang="en"' in body
    assert 'rel="alternate" hreflang="az"' not in body


def test_drafts_and_scheduled_posts_hidden(client):
    _post(slug="draft", published_at=None)
    _post(slug="later", published_at=timezone.now() + timedelta(days=1))
    assert client.get("/blog/draft/").status_code == 404
    assert client.get("/blog/later/").status_code == 404
    assert "/blog/later/" not in client.get("/blog/").content.decode()
    assert "/blog/later/" not in client.get("/sitemap.xml").content.decode()


def test_other_language_slug_redirects_to_blog(client):
    resp = client.get("/az/blog/static-vs-dynamic/")
    assert resp.status_code == 302 and resp["Location"] == "/az/blog/"
    assert client.get("/blog/does-not-exist/").status_code == 404


def test_sitemap_lists_posts(client):
    xml = client.get("/sitemap.xml").content.decode()
    assert "/blog/static-vs-dynamic/" in xml and "/az/blog/statik-ve-dinamik-qr-kod/" in xml


def test_blog_link_in_navigation(client):
    assert 'href="/blog/"' in client.get("/").content.decode()


def test_content_markup_is_safe():
    html = content_markup(
        "Hi <script>x</script> **bold** [ok](https://example.com) [bad](javascript:alert(1))\n"
        "![pic](/media/public/blog/a.png)\n![ext](https://evil.example/a.png)")
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<strong>bold</strong>" in html
    assert '<a href="https://example.com" rel="noopener nofollow">ok</a>' in html
    assert '<a href="javascript' not in html  # only http(s) and site-relative links
    assert '<img src="/media/public/blog/a.png" alt="pic"' in html
    assert html.count("<img") == 1  # images from other hosts are not embedded


def test_admin_dashboard(client, make_user):
    from allauth.mfa.models import Authenticator

    admin = make_user(email="boss@example.com", is_staff=True, is_superuser=True)
    Authenticator.objects.create(user=admin, type=Authenticator.Type.TOTP, data={})
    client.force_login(admin)
    body = client.get("/qadmin/").content.decode()
    assert "Registered users" in body and "QR codes created" in body
    assert "No payments yet" in body and "Sign-in emails" in body
    assert client.get("/qadmin/marketing/post/").status_code == 200
    assert client.get("/qadmin/marketing/post/add/").status_code == 200


def test_starter_posts_have_covers(client):
    body = client.get("/blog/").content.decode()
    assert body.count('src="/media/public/blog/') >= 2


def test_public_media_fallback_serves_only_public_images(tmp_path, settings, client):
    from django.http import Http404
    from django.test import RequestFactory

    from apps.core.views import public_media

    settings.MEDIA_ROOT = str(tmp_path)
    (tmp_path / "public" / "blog").mkdir(parents=True)
    (tmp_path / "public" / "blog" / "a.png").write_bytes(b"\\x89PNG")
    (tmp_path / "private").mkdir()
    (tmp_path / "private" / "secret.png").write_bytes(b"x")
    (tmp_path / "public" / "x.html").write_text("<script>")
    rf = RequestFactory().get("/")
    assert public_media(rf, "blog/a.png")["Content-Type"] == "image/png"
    for bad in ("../private/secret.png", "x.html", "missing.png"):
        with pytest.raises(Http404):
            public_media(rf, bad)
