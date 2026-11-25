import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.analytics.models import Scan, ScanDaily
from apps.organizations.models import Organization
from apps.qr_management import services
from apps.qr_management.engine import QRStyle
from apps.qr_management.models import QRCode
from apps.subscriptions.models import FeatureOverride

pytestmark = pytest.mark.django_db
IPHONE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
          "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
ANDROID = ("Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) "
           "Chrome/120.0 Mobile Safari/537.36")


def _scan(client, qr, ua=IPHONE, query="", ip="203.0.113.5", **extra):
    return client.get(f"/q/{qr.short_code}{query}", HTTP_USER_AGENT=ua, REMOTE_ADDR=ip, **extra)


# ---------------------------------------------------------------- services
def test_dynamic_gets_immutable_short_code_static_does_not(make_org, make_qr):
    org = make_org()
    dyn = make_qr(org)
    static = make_qr(org, mode="static")
    assert len(dyn.short_code) == 7 and static.short_code is None
    assert dyn.encoded_content == f"https://qrumy.com/q/{dyn.short_code}"
    assert static.encoded_content == "https://example.com/menu"
    code = dyn.short_code
    dyn.save()
    assert dyn.short_code == code


def test_static_only_type_cannot_be_dynamic(make_org, make_qr):
    with pytest.raises(services.QRError):
        make_qr(make_org(), qr_type="wifi", mode="dynamic",
                payload={"ssid": "x", "security": "nopass"})


def test_dynamic_quota(make_org, make_qr):
    org = make_org()
    FeatureOverride.objects.create(organization=org, feature_key="qr.dynamic", limit_value=1)
    make_qr(org)
    with pytest.raises(services.QRError):
        make_qr(org)
    make_qr(org, mode="static")  # static codes don't count


def test_unscannable_design_is_rejected(make_org, make_qr):
    with pytest.raises(ValidationError):
        make_qr(make_org(), style=QRStyle(fg="#DDDDDD"), verify=True)
    assert not QRCode.objects.exists()


def test_hosted_pdf_validation(make_org, make_qr):
    org = make_org()
    fake = SimpleUploadedFile("menu.pdf", b"<html>not a pdf</html>", "application/pdf")
    with pytest.raises(ValidationError):
        make_qr(org, qr_type="pdf", payload={}, upload=fake)
    real = SimpleUploadedFile("menu.pdf", b"%PDF-1.4\n%%EOF", "application/octet-stream")
    qr = make_qr(org, qr_type="pdf", payload={}, upload=real)
    assert qr.hosted_file.content_type == "application/pdf"


def test_file_size_limit(make_org, make_qr):
    org = make_org()
    FeatureOverride.objects.create(organization=org, feature_key="qr.file_mb", limit_value=1)
    big = SimpleUploadedFile("m.pdf", b"%PDF-" + b"0" * (1024 * 1024 + 10))
    with pytest.raises(ValidationError):
        make_qr(org, qr_type="pdf", payload={}, upload=big)


# ---------------------------------------------------------------- redirect
def test_scan_redirects_and_is_recorded(client, make_org, make_qr):
    qr = make_qr(make_org())
    resp = _scan(client, qr, query="?utm_source=flyer&utm_campaign=spring")
    assert resp.status_code == 302 and resp["Location"] == "https://example.com/menu"
    assert resp["Cache-Control"].startswith("no-store") or "no-store" in resp["Cache-Control"]
    scan = Scan.objects.get()
    assert scan.device == "mobile" and scan.os == "iOS" and scan.utm_source == "flyer"
    assert scan.ip_hash and "203.0.113.5" not in scan.ip_hash
    qr.refresh_from_db()
    assert qr.total_scans == 1 and qr.last_scan_at


def test_unique_counting_and_rollups(client, make_org, make_qr):
    qr = make_qr(make_org())
    _scan(client, qr, ip="203.0.113.5")
    _scan(client, qr, ip="203.0.113.5", ua=ANDROID)
    _scan(client, qr, ip="198.51.100.7")
    total = ScanDaily.objects.get(qr_code=qr, dimension="total")
    assert (total.scans, total.unique_scans) == (3, 2)
    devices = dict(ScanDaily.objects.filter(qr_code=qr, dimension="os")
                   .values_list("value", "scans"))
    assert devices == {"iOS": 2, "Android": 1}


def test_bots_and_head_requests_not_counted(client, make_org, make_qr):
    qr = make_qr(make_org())
    _scan(client, qr, ua="facebookexternalhit/1.1")
    client.head(f"/q/{qr.short_code}", HTTP_USER_AGENT=IPHONE)
    assert Scan.objects.filter(is_bot=True).count() == 2
    assert not ScanDaily.objects.filter(qr_code=qr).exists()
    qr.refresh_from_db()
    assert qr.total_scans == 0


@pytest.mark.parametrize("state,expected", [("paused", 200), ("suspended", 410)])
def test_inactive_codes_show_status_page(client, make_org, make_qr, state, expected):
    qr = make_qr(make_org())
    QRCode.objects.filter(pk=qr.pk).update(status=state)
    resp = _scan(client, qr)
    assert resp.status_code == expected and "Location" not in resp
    assert not Scan.objects.exists()


def test_expired_deleted_unknown_and_org_suspended(client, make_org, make_qr):
    org = make_org()
    expired = make_qr(org, expires_at=timezone.now() - timezone.timedelta(minutes=1))
    assert _scan(client, expired).status_code == 410
    deleted = make_qr(org)
    services.delete_qr(qr=deleted, actor=org.owner)
    assert _scan(client, deleted).status_code == 404
    assert client.get("/q/NOPE123").status_code == 404
    live = make_qr(org)
    Organization.objects.filter(pk=org.pk).update(status="suspended")
    assert _scan(client, live).status_code == 410


def test_edit_takes_effect_immediately_despite_cache(client, make_org, make_qr):
    org = make_org()
    qr = make_qr(org)
    assert _scan(client, qr)["Location"] == "https://example.com/menu"  # cached now
    services.update_qr(qr=qr, actor=org.owner, name=qr.name,
                       payload={"url": "https://example.com/new"}, style=QRStyle())
    assert _scan(client, qr)["Location"] == "https://example.com/new"
    services.set_status(qr=qr, actor=org.owner, status="paused")
    assert _scan(client, qr).status_code == 200


def test_app_type_routes_by_device(client, make_org, make_qr):
    qr = make_qr(make_org(), qr_type="app", payload={
        "app_name": "Demo", "ios_url": "https://apps.apple.com/x",
        "android_url": "https://play.google.com/x"})
    assert _scan(client, qr, ua=IPHONE)["Location"] == "https://apps.apple.com/x"
    assert _scan(client, qr, ua=ANDROID)["Location"] == "https://play.google.com/x"
    resp = _scan(client, qr, ua="Mozilla/5.0 (Windows NT 10.0) Chrome/120")
    assert resp.status_code == 200 and b"App Store" in resp.content


def test_landing_pages_render_escaped(client, make_org, make_qr):
    org = make_org()
    qr = make_qr(org, qr_type="links", payload={
        "title": "<b>Hi</b>", "links": [{"label": "Insta", "url": "https://instagram.com/x"}]})
    body = _scan(client, qr).content.decode()
    assert "&lt;b&gt;Hi&lt;/b&gt;" in body and 'href="https://instagram.com/x"' in body
    assert "Powered by" in body
    card = make_qr(org, qr_type="vcard", payload={"first_name": "Aysel", "phone": "+99450"})
    assert b"Aysel" in _scan(client, card).content
    vcf = client.get(f"/q/{card.short_code}/contact.vcf")
    assert vcf["Content-Type"].startswith("text/vcard") and b"BEGIN:VCARD" in vcf.content


def test_hosted_file_is_served_inline(client, make_org, make_qr):
    qr = make_qr(make_org(), qr_type="menu", payload={},
                 upload=SimpleUploadedFile("m.pdf", b"%PDF-1.4\n%%EOF"))
    resp = _scan(client, qr)
    assert resp.status_code == 200 and resp["Content-Type"] == "application/pdf"
    assert resp["X-Content-Type-Options"] == "nosniff"
    assert b"".join(resp.streaming_content).startswith(b"%PDF")


def test_scan_buffer_via_redis(settings, client, make_org, make_qr):
    redis = pytest.importorskip("redis")
    try:
        redis.Redis.from_url(settings.REDIS_URL).ping()
    except Exception:  # noqa: BLE001
        pytest.skip("Redis not available")
    from apps.analytics.ingest import BUFFER_KEY, _redis
    from apps.analytics.tasks import process_scan_buffer

    _redis().delete(BUFFER_KEY)
    settings.QRUMY_SCAN_BUFFER = "redis"
    qr = make_qr(make_org())
    _scan(client, qr)
    _scan(client, qr)
    assert not Scan.objects.exists()  # buffered, not yet written
    assert process_scan_buffer() == 2
    assert Scan.objects.count() == 2


def test_purge_keeps_rollups(settings, client, make_org, make_qr):
    from apps.analytics.tasks import purge_old_scans

    qr = make_qr(make_org())
    _scan(client, qr)
    Scan.objects.update(scanned_at=timezone.now() - timezone.timedelta(days=400))
    assert purge_old_scans() == 1
    assert ScanDaily.objects.filter(qr_code=qr, dimension="total").exists()


def test_svg_bytes_never_used_as_logo(make_org, make_qr):
    from apps.qr_management.forms import StyleForm

    svg = SimpleUploadedFile("l.png", b"<svg onload='x'/>", "image/png")
    form = StyleForm(data={"s-fg": "#101B3A", "s-bg": "#FFFFFF", "s-eye_color": "#101B3A",
                           "s-module_shape": "square", "s-eye_frame": "square",
                           "s-eye_ball": "square", "s-frame": "none",
                           "s-frame_color": "#101B3A"},
                     files={"s-logo": svg}, prefix="s")
    assert not form.is_valid() and "logo" in form.errors
    assert io  # keep import used


def test_domain_blocked_after_creation_stops_redirect(client, make_org, make_qr):
    from apps.qr_management.models import BlockedDomain

    qr = make_qr(make_org(), payload={"url": "https://phish.example/login"})
    assert _scan(client, qr).status_code == 302  # cached as a redirect
    BlockedDomain.objects.create(domain="phish.example", reason="phishing")
    resp = _scan(client, qr)
    assert resp.status_code == 410 and "Location" not in resp


def test_cached_scan_needs_no_database_queries(settings, client, make_org, make_qr,
                                               django_assert_num_queries):
    """The hot path: cache hit + Redis scan buffer → zero SQL queries per scan."""
    redis = pytest.importorskip("redis")
    try:
        redis.Redis.from_url(settings.REDIS_URL).ping()
    except Exception:  # noqa: BLE001
        pytest.skip("Redis not available")
    from apps.analytics.ingest import BUFFER_KEY, _redis

    settings.QRUMY_SCAN_BUFFER = "redis"
    qr = make_qr(make_org())
    _scan(client, qr)  # warms the code and blocklist caches
    with django_assert_num_queries(0):
        resp = _scan(client, qr)
    assert resp.status_code == 302
    _redis().delete(BUFFER_KEY)


def test_rate_limited_scans_still_redirect_but_are_not_counted(settings, client, make_org,
                                                               make_qr):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                   "LOCATION": "ratelimit-test"}}
    qr = make_qr(make_org())
    for _ in range(305):
        resp = _scan(client, qr)
        assert resp.status_code == 302  # people behind a shared IP are never blocked
    assert Scan.objects.count() == 300
