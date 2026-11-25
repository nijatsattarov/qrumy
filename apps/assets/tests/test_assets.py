import re

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.assets import locations as loc_helpers
from apps.assets import services
from apps.assets.models import Asset, AssetActivity, FaultReport, Location, MaintenanceRecord
from apps.notifications.models import Notification
from apps.qr_management.models import QRCode
from apps.subscriptions.models import FeatureOverride

pytestmark = pytest.mark.django_db
UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Mobile/15E148"


def u(name, org, **kw):
    return reverse(name, kwargs={"org_slug": org.slug, **kw})


# ------------------------------------------------------------------ services
def test_asset_codes_are_generated_and_unique(make_org, make_asset):
    org = make_org()
    a = make_asset(org)
    b = make_asset(org, name="Second")
    assert (a.asset_code, b.asset_code) == ("AST-00001", "AST-00002")
    with pytest.raises(services.AssetError):
        make_asset(org, asset_code="ast-00001")  # case-insensitive
    other = make_org("Other")
    assert make_asset(other).asset_code == "AST-00001"  # per organization
    assert AssetActivity.objects.filter(asset=a, action="created").exists()


def test_asset_quota(make_org, make_asset):
    org = make_org()
    FeatureOverride.objects.create(organization=org, feature_key="assets.max", limit_value=1)
    make_asset(org)
    with pytest.raises(services.AssetError):
        make_asset(org, name="Too many")


def test_location_tree_paths_descendants_and_cycles(make_org):
    org = make_org()
    branch = Location.objects.create(organization=org, name="Baku", kind="branch")
    building = Location.objects.create(organization=org, name="HQ", kind="building",
                                       parent=branch)
    room = Location.objects.create(organization=org, name="Kitchen", parent=building)
    assert loc_helpers.paths(org)[room.pk] == "Baku › HQ › Kitchen"
    assert loc_helpers.descendant_ids(org, branch.pk) == {branch.pk, building.pk, room.pk}
    with pytest.raises(services.AssetError):
        services.validate_parent(branch, room)  # would create a cycle
    labels = [label for _pk, label, _loc in loc_helpers.ordered_choices(org)]
    assert labels == ["Baku", "— HQ", "— — Kitchen"]


def test_asset_qr_profile_redirect(client, make_org, make_asset):
    org = make_org()
    asset = make_asset(org)
    qr = services.ensure_qr(asset=asset, actor=org.owner)
    assert services.ensure_qr(asset=asset, actor=org.owner) == qr  # idempotent
    resp = client.get(f"/q/{qr.short_code}", HTTP_USER_AGENT=UA)
    assert resp["Location"].endswith(f"/a/{asset.public_token}?src=qr")
    assert QRCode.objects.filter(qr_type="asset").count() == 1


def test_file_validation(make_org, make_asset, jpeg_bytes):
    org = make_org()
    asset = make_asset(org)
    doc = services.add_document(asset=asset, actor=org.owner,
                                upload=SimpleUploadedFile("m.pdf", b"%PDF-1.4\n%%EOF"))
    assert doc.kind == "document" and doc.content_type == "application/pdf"
    img = services.add_document(asset=asset, actor=org.owner,
                                upload=SimpleUploadedFile("p.png", jpeg_bytes))
    assert img.content_type == "image/jpeg"  # real type, not the file name
    with pytest.raises(ValidationError):
        services.add_document(asset=asset, actor=org.owner,
                              upload=SimpleUploadedFile("x.pdf", b"<html>evil</html>"))


# ------------------------------------------------------------------ public profile & faults
def _report_page(client, asset):
    return client.get(f"/a/{asset.public_token}/report", HTTP_USER_AGENT=UA)


def _post_report(client, asset, **over):
    token = re.search(r'name="started" value="([^"]+)"',
                      _report_page(client, asset).content.decode()).group(1)
    data = {"started": token, "category": "not_working", "description": "No hot water",
            "priority": "high", **over}
    return client.post(f"/a/{asset.public_token}/report", data, HTTP_USER_AGENT=UA)


@pytest.mark.parametrize("visibility,shown,hidden", [
    ("minimal", [], ["Kitchen", "Warranty"]),
    ("standard", ["Kitchen"], ["Last maintenance"]),
    ("full", ["Kitchen", "Last maintenance"], []),
])
def test_public_profile_visibility(client, make_org, make_asset, visibility, shown, hidden):
    org = make_org()
    room = Location.objects.create(organization=org, name="Kitchen")
    asset = make_asset(org, location=room, public_visibility=visibility,
                       serial_number="SECRET-SN", purchase_price=999)
    body = client.get(f"/a/{asset.public_token}").content.decode()
    assert asset.name in body and "Report a problem" in body
    assert "SECRET-SN" not in body and "999" not in body  # never public
    for text in shown:
        assert text in body
    for text in hidden:
        assert text not in body


def test_public_fault_report_notifies_and_emails(client, make_org, make_asset, make_user,
                                                  add_member, jpeg_bytes):
    from django.core import mail

    org = make_org()
    tech = make_user(email="tech@example.com")
    add_member(org, tech, "member")
    asset = make_asset(org, responsible=tech)
    resp = _post_report(client, asset, photo=SimpleUploadedFile("p.jpg", jpeg_bytes),
                        reporter_name="Aynur")
    assert resp.status_code == 302 and resp["Location"].endswith("/thanks")
    fault = FaultReport.objects.get()
    assert fault.via_qr and fault.reporter_name == "Aynur" and fault.photo
    assert Notification.objects.filter(user=tech, kind="assets.fault").exists()
    assert len(mail.outbox) == 1 and "tech@example.com" in mail.outbox[0].to  # high priority


def test_fault_without_responsible_goes_to_managers(client, make_org, make_asset):
    org = make_org()
    asset = make_asset(org)
    _post_report(client, asset, priority="low")
    assert Notification.objects.filter(user=org.owner, kind="assets.fault").exists()


def test_public_report_rejects_spam_and_bad_tokens(client, make_org, make_asset):
    org = make_org()
    asset = make_asset(org)
    _post_report(client, asset, website="spam")
    client.post(f"/a/{asset.public_token}/report", {
        "started": "forged", "category": "other", "description": "x", "priority": "low"})
    other = make_asset(org, name="Other")
    token = re.search(r'name="started" value="([^"]+)"',
                      _report_page(client, other).content.decode()).group(1)
    client.post(f"/a/{asset.public_token}/report", {
        "started": token, "category": "other", "description": "x", "priority": "low"})
    assert not FaultReport.objects.exists()


def test_public_report_rejects_non_image_photo(client, make_org, make_asset):
    asset = make_asset(make_org())
    resp = _post_report(client, asset, photo=SimpleUploadedFile("x.jpg", b"<svg/>"))
    assert resp.status_code == 200 and not FaultReport.objects.exists()


def test_public_pages_follow_phone_language(client, make_org, make_asset):
    asset = make_asset(make_org())
    body = client.get(f"/a/{asset.public_token}", HTTP_ACCEPT_LANGUAGE="az").content.decode()
    assert 'lang="az"' in body


def test_suspended_org_hides_profile(client, make_org, make_asset):
    org = make_org()
    asset = make_asset(org)
    org.status = "suspended"
    org.save()
    assert client.get(f"/a/{asset.public_token}").status_code == 404


# ------------------------------------------------------------------ management UI
def test_create_asset_via_form_with_qr(client, make_org):
    org = make_org()
    room = Location.objects.create(organization=org, name="Kitchen")
    client.force_login(org.owner)
    resp = client.post(u("asset_create", org), {
        "name": "Espresso", "status": "active", "location": room.pk, "currency": "AZN",
        "public_visibility": "standard", "custom_fields_text": "Voltage: 220 V\nbad line",
        "create_qr": "1"})
    asset = Asset.objects.get()
    assert resp["Location"] == u("asset_detail", org, pk=asset.pk)
    assert asset.location == room and asset.custom_fields == {"Voltage": "220 V"}
    assert asset.qr_code and asset.qr_code.qr_type == "asset"


def test_edit_keeps_code_and_logs_status(client, make_org, make_asset):
    org = make_org()
    asset = make_asset(org)
    client.force_login(org.owner)
    client.post(u("asset_edit", org, pk=asset.pk), {
        "name": "Renamed", "asset_code": "", "status": "broken", "currency": "AZN",
        "public_visibility": "standard"})
    asset.refresh_from_db()
    assert asset.asset_code == "AST-00001" and asset.status == "broken"
    assert AssetActivity.objects.filter(asset=asset, action="status").exists()


def test_fault_workflow_completes_with_repair(client, make_org, make_asset, make_user,
                                              add_member):
    org = make_org()
    tech = make_user(email="t@example.com")
    add_member(org, tech, "member")
    asset = make_asset(org, status="broken")
    fault = services.report_fault(asset=asset, category="damaged", description="Cracked",
                                  priority="normal", reported_by=org.owner)
    client.force_login(org.owner)
    client.post(u("asset_fault_update", org, pk=fault.pk), {"assigned_to": tech.pk,
                                                            "status": ""})
    fault.refresh_from_db()
    assert fault.assigned_to == tech and fault.status == "assigned"
    assert Notification.objects.filter(user=tech, kind="assets.fault_assigned").exists()
    client.post(u("asset_fault_update", org, pk=fault.pk), {
        "assigned_to": tech.pk, "status": "completed", "resolution": "Replaced glass",
        "log_maintenance": "1", "cost": "45.50", "asset_active": "1"})
    fault.refresh_from_db()
    asset.refresh_from_db()
    assert fault.status == "completed" and fault.resolved_at and asset.status == "active"
    rec = MaintenanceRecord.objects.get()
    assert rec.fault == fault and str(rec.cost) == "45.50" and rec.kind == "corrective"


def test_private_files_require_membership(client, make_org, make_asset, make_user, jpeg_bytes):
    org = make_org()
    asset = make_asset(org)
    doc = services.add_document(asset=asset, actor=org.owner,
                                upload=SimpleUploadedFile("p.jpg", jpeg_bytes))
    url = u("asset_document_file", org, doc_id=doc.pk)
    assert client.get(url).status_code == 302  # anonymous → login
    client.force_login(make_user(email="stranger@example.com"))
    assert client.get(url).status_code == 404
    client.force_login(org.owner)
    resp = client.get(url)
    assert resp["Content-Type"] == "image/jpeg" and resp["X-Content-Type-Options"] == "nosniff"


def test_list_filters_include_sub_locations(client, make_org, make_asset):
    org = make_org()
    branch = Location.objects.create(organization=org, name="Baku", kind="branch")
    room = Location.objects.create(organization=org, name="Kitchen", parent=branch)
    make_asset(org, name="In room", location=room)
    make_asset(org, name="Nowhere", status="broken")
    client.force_login(org.owner)

    def names(**params):
        page = client.get(u("asset_list", org), params).context["page"]
        return sorted(a.name for a in page.object_list)

    assert names(location=branch.pk) == ["In room"]
    assert names(status="broken") == ["Nowhere"]
    assert names(q="room") == ["In room"]


def test_location_with_children_cannot_be_deleted(client, make_org):
    org = make_org()
    branch = Location.objects.create(organization=org, name="Baku")
    Location.objects.create(organization=org, name="Kitchen", parent=branch)
    client.force_login(org.owner)
    client.post(u("asset_location_delete", org, loc_id=branch.pk))
    assert Location.objects.filter(pk=branch.pk).exists()


def test_delete_asset_needs_code_and_pauses_qr(client, make_org, make_asset):
    org = make_org()
    asset = make_asset(org)
    qr = services.ensure_qr(asset=asset, actor=org.owner)
    client.force_login(org.owner)
    client.post(u("asset_delete", org, pk=asset.pk), {"confirm_code": "nope"})
    assert Asset.objects.filter(pk=asset.pk).exists()
    client.post(u("asset_delete", org, pk=asset.pk), {"confirm_code": "ast-00001"})
    assert not Asset.objects.filter(pk=asset.pk).exists()
    qr.refresh_from_db()
    assert qr.status == "paused"


def test_export_csv_formula_safe(client, make_org, make_asset):
    org = make_org()
    make_asset(org, name="=HYPERLINK(1)")
    client.force_login(org.owner)
    body = client.get(u("asset_export", org)).content.decode("utf-8-sig")
    assert "'=HYPERLINK(1)" in body


def test_permissions_and_module_gating(client, make_org, make_asset, make_user, add_member):
    org = make_org()
    asset = make_asset(org)
    viewer = make_user(email="v@example.com")
    add_member(org, viewer, "viewer")
    client.force_login(viewer)
    assert client.get(u("asset_detail", org, pk=asset.pk)).status_code == 200
    assert client.get(u("asset_create", org)).status_code == 403
    assert client.post(u("asset_action", org, pk=asset.pk),
                       {"action": "status", "status": "lost"}).status_code == 403
    client.force_login(org.owner)
    FeatureOverride.objects.create(organization=org, feature_key="module.assets", enabled=False)
    assert client.get(u("asset_list", org)).status_code == 404


def test_dashboard_widget(client, make_org, make_asset):
    org = make_org()
    make_asset(org, status="broken")
    client.force_login(org.owner)
    widget = next(w for w in client.get(u("dashboard", org)).context["widgets"]
                  if w["key"] == "assets")
    assert widget["total"] == 1 and widget["attention"] == 1
