import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.qr_management.models import Folder, QRCode
from apps.subscriptions.models import FeatureOverride

pytestmark = pytest.mark.django_db

STYLE = {"s-fg": "#101B3A", "s-bg": "#FFFFFF", "s-eye_color": "#101B3A",
         "s-module_shape": "rounded", "s-eye_frame": "rounded", "s-eye_ball": "circle",
         "s-frame": "bottom", "s-frame_color": "#101B3A", "s-cta_text": "Scan me"}


def u(name, org, **kw):
    return reverse(name, kwargs={"org_slug": org.slug, **kw})


def test_create_dynamic_url_via_form(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    resp = client.post(u("qr_create", org, type_key="url"), {
        "c-url": "example.com/menu", "meta-name": "Menu", "meta-mode": "dynamic",
        "meta-tags": "menu, Tables", **STYLE})
    qr = QRCode.objects.get()
    assert resp["Location"] == u("qr_detail", org, pk=qr.pk)
    assert qr.payload == {"url": "https://example.com/menu"} and qr.created_by == org.owner
    assert sorted(t.name for t in qr.tags.all()) == ["Tables", "menu"]
    assert qr.style["module_shape"] == "rounded"


def test_create_rejects_low_contrast_design(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    resp = client.post(u("qr_create", org, type_key="url"), {
        "c-url": "https://example.com", "meta-name": "x", "meta-mode": "dynamic",
        **STYLE, "s-fg": "#EEEEEE"})
    assert resp.status_code == 200 and not QRCode.objects.exists()
    assert b"contrast" in resp.content


def test_create_rejects_unsafe_url(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    client.post(u("qr_create", org, type_key="url"), {
        "c-url": "javascript:alert(1)", "meta-name": "x", "meta-mode": "dynamic", **STYLE})
    assert not QRCode.objects.exists()


def test_create_hosted_pdf(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    pdf = SimpleUploadedFile("menu.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")
    client.post(u("qr_create", org, type_key="pdf"),
                {"c-file": pdf, "meta-name": "Menu PDF", **STYLE})
    qr = QRCode.objects.get()
    assert qr.mode == "dynamic" and qr.hosted_file.original_name == "menu.pdf"


def test_edit_keeps_short_code(client, make_org, make_qr):
    org = make_org()
    qr = make_qr(org)
    code = qr.short_code
    client.force_login(org.owner)
    client.post(u("qr_edit", org, pk=qr.pk), {
        "c-url": "https://example.com/new", "meta-name": "Renamed", **STYLE})
    qr.refresh_from_db()
    assert qr.short_code == code and qr.name == "Renamed"
    assert qr.payload["url"] == "https://example.com/new"


def test_preview_endpoint(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    resp = client.post(u("qr_preview", org), {"type": "url", "meta-mode": "dynamic", **STYLE},
                       HTTP_HX_REQUEST="true")
    body = resp.content.decode()
    assert resp.status_code == 200 and "<svg" in body and "Test scan passed" in body


def test_list_filters_and_search(client, make_org, make_qr):
    org = make_org()
    folder = Folder.objects.create(organization=org, name="Menus")
    make_qr(org, name="Spring menu", folder=folder, tags=["food"])
    make_qr(org, name="Wifi", qr_type="wifi", mode="static",
            payload={"ssid": "x", "security": "nopass"})
    client.force_login(org.owner)

    def names(**params):
        resp = client.get(u("qr_list", org), params)
        return [q.name for q in resp.context["page"].object_list]

    assert sorted(names()) == ["Spring menu", "Wifi"]
    assert names(q="spring") == ["Spring menu"]
    assert names(type="wifi") == ["Wifi"]
    assert names(mode="dynamic") == ["Spring menu"]
    assert names(folder=folder.pk) == ["Spring menu"]
    assert names(folder="none") == ["Wifi"]
    assert names(tag="food") == ["Spring menu"]
    partial = client.get(u("qr_list", org), {"q": "spring"}, HTTP_HX_REQUEST="true",
                         HTTP_HX_TARGET="qr-results")
    assert b"<html" not in partial.content and b"Spring menu" in partial.content


def test_downloads(client, make_org, make_qr):
    org = make_org()
    qr = make_qr(org, name="Yaz menyusu")
    client.force_login(org.owner)
    png = client.get(u("qr_download", org, pk=qr.pk, fmt="png") + "?size=512")
    assert png["Content-Type"] == "image/png" and png.content.startswith(b"\x89PNG")
    assert "yaz-menyusu-512.png" in png["Content-Disposition"]
    svg = client.get(u("qr_download", org, pk=qr.pk, fmt="svg"))
    assert svg.content.startswith(b"<svg")
    assert client.get(u("qr_download", org, pk=qr.pk, fmt="exe")).status_code == 404


def test_bulk_actions_and_zip_export(client, make_org, make_qr):
    org = make_org()
    a, b = make_qr(org, name="A"), make_qr(org, name="A")
    client.force_login(org.owner)
    resp = client.post(u("qr_bulk_action", org), {"ids": [a.pk, b.pk], "action": "export_svg"})
    names = zipfile.ZipFile(io.BytesIO(resp.content)).namelist()
    assert sorted(names) == ["a-2.svg", "a.svg"]
    client.post(u("qr_bulk_action", org), {"ids": [a.pk, b.pk], "action": "pause"})
    assert set(QRCode.objects.values_list("status", flat=True)) == {"paused"}
    client.post(u("qr_bulk_action", org), {"ids": [a.pk], "action": "delete"})
    assert QRCode.objects.live().count() == 1


def test_bulk_csv_create(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    csv = "name,url,tags\nOne,https://example.com/1,a\nTwo,example.com/2,\"b, c\"\n"
    client.post(u("qr_bulk", org), {"file": SimpleUploadedFile("c.csv", csv.encode())})
    assert sorted(QRCode.objects.values_list("name", flat=True)) == ["One", "Two"]
    assert QRCode.objects.get(name="Two").payload["url"] == "https://example.com/2"


def test_bulk_csv_all_or_nothing(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    csv = "url\nhttps://ok.example\njavascript:alert(1)\n"
    resp = client.post(u("qr_bulk", org), {"file": SimpleUploadedFile("c.csv", csv.encode())})
    assert b"Row 3" in resp.content and not QRCode.objects.exists()


def test_bulk_csv_respects_quota_and_plan(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    FeatureOverride.objects.create(organization=org, feature_key="qr.dynamic", limit_value=1)
    csv = "url\nhttps://a.example\nhttps://b.example\n"
    client.post(u("qr_bulk", org), {"file": SimpleUploadedFile("c.csv", csv.encode())})
    assert not QRCode.objects.exists()
    FeatureOverride.objects.create(organization=org, feature_key="qr.bulk", enabled=False)
    assert b"not included" in client.get(u("qr_bulk", org)).content


def test_analytics_csv_guards_formula_injection(client, make_org, make_qr):
    org = make_org()
    qr = make_qr(org, name="=HYPERLINK(1)")
    client.get(f"/q/{qr.short_code}", HTTP_USER_AGENT="Mozilla/5.0 (iPhone; Mobile)")
    client.force_login(org.owner)
    body = client.get(u("analytics_export", org)).content.decode("utf-8-sig")
    assert "'=HYPERLINK(1)" in body and ",total," in body


def test_analytics_pages(client, make_org, make_qr):
    org = make_org()
    qr = make_qr(org)
    client.get(f"/q/{qr.short_code}", HTTP_USER_AGENT="Mozilla/5.0 (iPhone; Mobile)")
    client.force_login(org.owner)
    resp = client.get(u("analytics_overview", org), {"days": 7})
    assert resp.context["totals"]["scans"] == 1
    detail = client.get(u("qr_detail", org, pk=qr.pk))
    assert detail.context["analytics"]["totals"]["scans"] == 1


def test_role_permissions(client, make_org, make_qr, make_user, add_member):
    org = make_org()
    qr = make_qr(org)
    viewer = make_user(email="v@example.com")
    add_member(org, viewer, "viewer")
    client.force_login(viewer)
    assert client.get(u("qr_list", org)).status_code == 200
    assert client.get(u("qr_detail", org, pk=qr.pk)).status_code == 200
    assert client.get(u("qr_create", org, type_key="url")).status_code == 403
    assert client.post(u("qr_set_status", org, pk=qr.pk), {"status": "paused"}).status_code == 403
    member = make_user(email="m@example.com")
    add_member(org, member, "member")
    client.force_login(member)
    assert client.post(u("qr_delete", org, pk=qr.pk)).status_code == 403
    client.post(u("qr_bulk_action", org), {"ids": [qr.pk], "action": "delete"})
    assert QRCode.objects.live().count() == 1


def test_module_disabled_by_plan(client, make_org):
    org = make_org()
    FeatureOverride.objects.create(organization=org, feature_key="module.qr", enabled=False)
    client.force_login(org.owner)
    assert client.get(u("qr_list", org)).status_code == 404
    assert b"QR Codes" not in client.get(u("dashboard", org)).content


def test_dashboard_widget(client, make_org, make_qr):
    org = make_org()
    make_qr(org)
    client.force_login(org.owner)
    resp = client.get(u("dashboard", org))
    assert resp.context["widgets"][0]["qr_count"] == 1


def test_folder_crud(client, make_org, make_qr):
    org = make_org()
    client.force_login(org.owner)
    client.post(u("qr_folder_create", org), {"name": "Menus"})
    folder = Folder.objects.get()
    qr = make_qr(org, folder=folder)
    client.post(u("qr_folder_rename", org, folder_id=folder.pk), {"name": "Menyular"})
    folder.refresh_from_db()
    assert folder.name == "Menyular"
    client.post(u("qr_folder_delete", org, folder_id=folder.pk))
    qr.refresh_from_db()
    assert qr.folder is None and not qr.deleted_at


def test_admin_can_suspend_qr(client, make_org, make_qr, make_user):
    from allauth.mfa.models import Authenticator

    from apps.audit_logs.models import AuditLog

    org = make_org()
    qr = make_qr(org)
    staff = make_user(email="s@example.com", is_staff=True, is_superuser=True)
    Authenticator.objects.create(user=staff, type=Authenticator.Type.TOTP, data={})
    client.force_login(staff)
    url = "/qadmin/qr_management/qrcode/"
    form = client.post(url, {"action": "suspend", "_selected_action": [qr.pk]})
    assert b"Reason" in form.content
    client.post(url, {"action": "suspend", "_selected_action": [qr.pk], "apply": "1",
                      "reason": "Phishing"})
    qr.refresh_from_db()
    assert qr.status == "suspended" and qr.suspended_reason == "Phishing"
    assert AuditLog.objects.filter(action="admin.qr.suspended").exists()
    assert client.get(f"/q/{qr.short_code}").status_code == 410
