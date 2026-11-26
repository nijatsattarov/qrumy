import io

import pytest
import zxingcpp
from PIL import Image

from apps.qr_management.models import QRCode

pytestmark = pytest.mark.django_db

STYLE = {"s-fg": "#101B3A", "s-bg": "#FFFFFF", "s-eye_color": "#101B3A",
         "s-module_shape": "dots", "s-eye_frame": "circle", "s-eye_ball": "rounded",
         "s-frame": "pill", "s-frame_color": "#101B3A", "s-cta_text": "Scan me"}


def _decode(png: bytes) -> str:
    return zxingcpp.read_barcodes(Image.open(io.BytesIO(png)))[0].text


def test_homepage_shows_generator_without_login(client):
    body = client.get("/").content.decode()
    assert 'id="gen-form"' in body and 'name="c-url"' in body
    for t in ("wifi", "phone", "email", "whatsapp", "vcard"):
        assert f"?type={t}#generator" in body
    assert 'href="/accounts/signup/"' in body  # advanced products lead to sign-up


def test_type_tabs_render_fields(client):
    body = client.get("/qr-generator/fields/?type=wifi").content.decode()
    assert 'name="c-ssid"' in body and 'value="wifi"' in body
    assert client.get("/?type=wifi").content.decode().count('name="c-ssid"') == 1


def test_only_static_types_allowed(client):
    for t in ("links", "pdf", "coupon", "survey", "asset"):
        fields = client.get(f"/qr-generator/fields/?type={t}").content.decode()
        assert 'value="url"' in fields  # unknown types fall back to a website code
        assert client.post("/qr-generator/preview/", {"type": t, **STYLE}).status_code == 404


def test_preview_and_download_png_svg(client):
    data = {"type": "wifi", "c-ssid": "Cafe", "c-security": "WPA", "c-password": "secret12",
            **STYLE}
    preview = client.post("/qr-generator/preview/", data).content.decode()
    assert "<svg" in preview and "Test scan passed" in preview
    png = client.post("/qr-generator/download/png/", data)
    assert png["Content-Type"] == "image/png" and "attachment" in png["Content-Disposition"]
    assert _decode(png.content).startswith("WIFI:")
    svg = client.post("/qr-generator/download/svg/", data)
    assert svg["Content-Type"] == "image/svg+xml" and b"<svg" in svg.content
    assert QRCode.objects.count() == 0  # nothing is stored


def test_url_code_encodes_destination_directly(client):
    png = client.post("/qr-generator/download/png/",
                      {"type": "url", "c-url": "https://example.com/menu", **STYLE})
    assert _decode(png.content) == "https://example.com/menu"


def test_invalid_input_shows_sample_and_blocks_download(client):
    preview = client.post("/qr-generator/preview/", {"type": "url", "c-url": "", **STYLE})
    assert "Fill in the fields" in preview.content.decode()
    resp = client.post("/qr-generator/download/png/", {"type": "url", "c-url": "", **STYLE})
    assert resp.status_code == 302 and resp["Location"].endswith("?type=url#generator")


def test_unscannable_design_cannot_be_downloaded(client):
    data = {"type": "text", "c-text": "hello", **STYLE, "s-fg": "#FFFFFF",
            "s-eye_color": "#FFFFFF"}
    resp = client.post("/qr-generator/download/png/", data)
    assert resp.status_code == 302


def test_unsafe_url_rejected(client):
    resp = client.post("/qr-generator/download/png/",
                       {"type": "url", "c-url": "javascript:alert(1)", **STYLE})
    assert resp.status_code == 302


def test_generator_is_rate_limited(client, settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                   "LOCATION": "gen-ratelimit"}}
    data = {"type": "text", "c-text": "hi", **STYLE}
    codes = [client.post("/qr-generator/download/svg/", data).status_code for _ in range(32)]
    assert codes[0] == 200 and codes[-1] in (403, 429)


def test_bare_domain_is_accepted(client):
    data = {"type": "url", "c-url": "example.com", **STYLE}
    assert "Test scan passed" in client.post("/qr-generator/preview/", data).content.decode()
    png = client.post("/qr-generator/download/png/", data)
    assert _decode(png.content) == "https://example.com"


def test_url_input_is_not_type_url(client):
    body = client.get("/").content.decode()
    assert 'name="c-url"' in body and 'type="url"' not in body and 'inputmode="url"' in body
