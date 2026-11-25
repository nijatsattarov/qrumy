import csv

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.organizations.permissions import require_capability, require_module

from .. import locations as loc_helpers
from .. import services, stats
from ..forms import AssetForm, DocumentForm, InternalFaultForm, MaintenanceForm
from ..models import Asset, AssetCategory, AssetDocument, FaultReport


def _assets(request):
    return Asset.objects.for_org(request.organization)


def _asset(request, pk):
    return get_object_or_404(_assets(request).select_related("category", "location",
                                                             "responsible", "qr_code"), pk=pk)


def _filtered(request):
    org = request.organization
    qs = (_assets(request).select_related("category", "location", "responsible")
          .annotate(open_faults=Count("faults", filter=Q(
              faults__status__in=FaultReport.OPEN_STATUSES))))
    g = request.GET
    if q := g.get("q", "").strip():
        qs = qs.filter(Q(name__icontains=q) | Q(asset_code__icontains=q) |
                       Q(serial_number__icontains=q) | Q(brand__icontains=q) |
                       Q(model_name__icontains=q))
    if (s := g.get("status")) in Asset.Status.values:
        qs = qs.filter(status=s)
    if (c := g.get("category", "")).isdigit():
        qs = qs.filter(category_id=int(c))
    if (loc := g.get("location", "")).isdigit():
        qs = qs.filter(location_id__in=loc_helpers.descendant_ids(org, int(loc)))
    if g.get("responsible") == "me":
        qs = qs.filter(responsible=request.user)
    if g.get("faults") == "open":
        qs = qs.filter(open_faults__gt=0)
    return qs


@require_module("assets")
@require_capability("content.view")
def asset_list(request, org_slug):
    org = request.organization
    page = Paginator(_filtered(request), 30).get_page(request.GET.get("page"))
    paths = loc_helpers.paths(org)
    for a in page.object_list:
        a.location_path = paths.get(a.location_id, "")
    ctx = {"page": page, "filters": request.GET, "statuses": Asset.Status.choices,
           "categories": AssetCategory.objects.for_org(org),
           "location_choices": loc_helpers.ordered_choices(org),
           "summary": stats.overview(org),
           "filtered": any(request.GET.get(k) for k in
                           ("q", "status", "category", "location", "responsible", "faults"))}
    template = "assets/list.html"
    if request.htmx and request.htmx.target == "asset-results":
        template += "#results"
    return render(request, template, ctx)


@require_module("assets")
@require_capability("content.create")
def asset_create(request, org_slug):
    org = request.organization
    form = AssetForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        try:
            asset = services.create_asset(organization=org, actor=request.user,
                                          data=form.create_data(), request=request)
        except services.AssetError as exc:
            form.add_error(None, str(exc))
        else:
            if request.POST.get("create_qr"):
                try:
                    services.ensure_qr(asset=asset, actor=request.user, request=request)
                except services.AssetError as exc:
                    messages.warning(request, str(exc))
            messages.success(request, _("Asset added."))
            return redirect("asset_detail", org_slug=org_slug, pk=asset.pk)
    return render(request, "assets/form.html", {"form": form, "asset": None})


@require_module("assets")
@require_capability("content.edit")
def asset_edit(request, org_slug, pk):
    asset = _asset(request, pk)
    form = AssetForm(request.POST or None, instance=asset, organization=request.organization)
    if request.method == "POST" and form.is_valid():
        services.update_asset(asset=asset, actor=request.user, form=form, request=request)
        messages.success(request, _("Changes saved."))
        return redirect("asset_detail", org_slug=org_slug, pk=pk)
    return render(request, "assets/form.html", {"form": form, "asset": asset})


@require_module("assets")
@require_capability("content.view")
def asset_detail(request, org_slug, pk):
    asset = _asset(request, pk)
    org = request.organization
    qr_svg = None
    qr = asset.qr_code if asset.qr_code_id and asset.qr_code.deleted_at is None else None
    if qr:
        from apps.qr_management.engine import QRStyle, render_svg

        qr_svg = render_svg(qr.encoded_content, QRStyle.from_dict(qr.style), qr.logo_bytes())
    maintenance = asset.maintenance.select_related("technician", "fault")
    return render(request, "assets/detail.html", {
        "asset": asset, "qr": qr, "qr_svg": qr_svg,
        "location": loc_helpers.paths(org).get(asset.location_id, ""),
        "documents": asset.documents.all(),
        "faults": asset.faults.select_related("assigned_to")[:20],
        "maintenance": maintenance[:20],
        "maintenance_total": sum((m.cost or 0) for m in maintenance),
        "activity": asset.activity.select_related("actor")[:15],
        "statuses": Asset.Status.choices,
        "maintenance_form": MaintenanceForm(organization=org, prefix="m"),
        "fault_form": InternalFaultForm(prefix="f"),
        "document_form": DocumentForm(prefix="d"),
    })


@require_module("assets")
@require_capability("content.edit")
@require_POST
def asset_action(request, org_slug, pk):
    asset = _asset(request, pk)
    org = request.organization
    action = request.POST.get("action")
    try:
        if action == "status":
            services.set_status(asset=asset, actor=request.user,
                                status=request.POST.get("status", ""))
            messages.success(request, _("Status updated."))
        elif action == "qr":
            services.ensure_qr(asset=asset, actor=request.user, request=request)
            messages.success(request, _("QR code created. Print it and stick it on the asset."))
        elif action == "maintenance":
            form = MaintenanceForm(request.POST, organization=org, prefix="m")
            if form.is_valid():
                services.add_maintenance(asset=asset, actor=request.user,
                                         data=form.cleaned_data)
                messages.success(request, _("Maintenance logged."))
            else:
                messages.error(request, _("Check the maintenance form."))
        elif action == "fault":
            form = InternalFaultForm(request.POST, prefix="f")
            if form.is_valid():
                fault = services.report_fault(asset=asset, reported_by=request.user,
                                              reporter_name=request.user.display_name,
                                              **form.cleaned_data)
                messages.success(request, _("Fault reported."))
                return redirect("asset_fault", org_slug=org_slug, pk=fault.pk)
            messages.error(request, _("Describe the problem."))
        elif action == "document":
            form = DocumentForm(request.POST, request.FILES, prefix="d")
            if form.is_valid():
                services.add_document(asset=asset, actor=request.user,
                                      upload=form.cleaned_data["file"])
                messages.success(request, _("File uploaded."))
            else:
                messages.error(request, _("Choose a file to upload."))
        elif action == "delete_document":
            doc = get_object_or_404(AssetDocument, pk=request.POST.get("document"),
                                    asset=asset, organization=org)
            services.delete_document(document=doc, actor=request.user)
            messages.success(request, _("File deleted."))
    except (services.AssetError, ValidationError) as exc:
        messages.error(request, getattr(exc, "messages", [str(exc)])[0])
    return redirect("asset_detail", org_slug=org_slug, pk=pk)


@require_module("assets")
@require_capability("content.delete")
@require_POST
def asset_delete(request, org_slug, pk):
    asset = _asset(request, pk)
    if request.POST.get("confirm_code", "").strip().lower() != asset.asset_code.lower():
        messages.error(request, _("Type the asset ID exactly to confirm deletion."))
        return redirect("asset_edit", org_slug=org_slug, pk=pk)
    services.delete_asset(asset=asset, actor=request.user, request=request)
    messages.success(request, _("Asset deleted."))
    return redirect("asset_list", org_slug=org_slug)


def _serve_private(file, content_type, name):
    if settings.QRUMY_SERVE_FILES_WITH_X_ACCEL:
        resp = HttpResponse()
        resp["X-Accel-Redirect"] = "/protected/" + file.name
    else:
        resp = FileResponse(file.open("rb"))
    resp["Content-Type"] = content_type
    resp["Content-Disposition"] = f'inline; filename="{name}"'
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Cache-Control"] = "private, no-store"
    return resp


@require_module("assets")
@require_capability("content.view")
def document_file(request, org_slug, doc_id):
    doc = get_object_or_404(AssetDocument.objects.for_org(request.organization), pk=doc_id)
    safe = "".join(c for c in doc.original_name if c.isalnum() or c in "._- ")[:100] or "file"
    return _serve_private(doc.file, doc.content_type, safe)


@require_module("assets")
@require_capability("content.view")
def asset_export(request, org_slug):
    org = request.organization
    paths = loc_helpers.paths(org)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="qrumy-assets.csv"'
    resp.write("﻿")
    w = csv.writer(resp)
    w.writerow(["asset_id", "name", "status", "category", "brand", "model", "serial_number",
                "location", "department", "responsible", "purchase_date", "warranty_until",
                "purchase_price", "currency", "supplier", "open_faults"])

    def cell(v):
        v = "" if v is None else str(v)
        return "'" + v if v[:1] in ("=", "+", "-", "@") else v

    for a in _filtered(request):
        w.writerow([cell(x) for x in [
            a.asset_code, a.name, a.status, a.category.name if a.category else "", a.brand,
            a.model_name, a.serial_number, paths.get(a.location_id, ""), a.department,
            a.responsible.email if a.responsible else "", a.purchase_date,
            a.warranty_expires_at, a.purchase_price, a.currency, a.supplier, a.open_faults]])
    return resp

