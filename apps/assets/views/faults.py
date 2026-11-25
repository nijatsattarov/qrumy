from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from PIL import Image

from apps.organizations.permissions import require_capability, require_module

from .. import services
from ..models import FaultReport, MaintenanceRecord
from ..services import IMAGE_TYPES
from .assets import _serve_private


def _faults(request):
    return FaultReport.objects.for_org(request.organization).select_related(
        "asset", "assigned_to")


def _members(request):
    return get_user_model().objects.filter(
        memberships__organization=request.organization).order_by("full_name", "email")


@require_module("assets")
@require_capability("content.view")
def fault_list(request, org_slug):
    qs = _faults(request)
    g = request.GET
    state = g.get("state", "open")
    if state == "open":
        qs = qs.filter(status__in=FaultReport.OPEN_STATUSES)
    elif state in FaultReport.Status.values:
        qs = qs.filter(status=state)
    if (p := g.get("priority")) in FaultReport.Priority.values:
        qs = qs.filter(priority=p)
    if g.get("assigned") == "me":
        qs = qs.filter(assigned_to=request.user)
    elif g.get("assigned") == "none":
        qs = qs.filter(assigned_to__isnull=True)
    page = Paginator(qs, 30).get_page(g.get("page"))
    return render(request, "assets/faults.html", {
        "page": page, "filters": g, "state": state,
        "statuses": FaultReport.Status.choices, "priorities": FaultReport.Priority.choices})


@require_module("assets")
@require_capability("content.view")
def fault_detail(request, org_slug, pk):
    fault = get_object_or_404(_faults(request), pk=pk)
    return render(request, "assets/fault_detail.html", {
        "fault": fault, "members": _members(request), "statuses": FaultReport.Status.choices,
        "maintenance": fault.maintenance.select_related("technician"),
        "kinds": MaintenanceRecord.Kind.choices})


@require_module("assets")
@require_capability("content.edit")
@require_POST
def fault_update(request, org_slug, pk):
    fault = get_object_or_404(_faults(request), pk=pk)
    p = request.POST
    assignee = False
    if "assigned_to" in p:
        uid = p.get("assigned_to")
        assignee = _members(request).filter(pk=uid).first() if uid else None
    status = p.get("status") or None
    try:
        services.update_fault(fault=fault, actor=request.user, status=status,
                              assigned_to=assignee, resolution=p.get("resolution"),
                              request=request)
    except services.AssetError as exc:
        messages.error(request, str(exc))
        return redirect("asset_fault", org_slug=org_slug, pk=pk)
    if status == FaultReport.Status.COMPLETED and p.get("log_maintenance"):
        cost = p.get("cost") or None
        try:
            from decimal import Decimal, InvalidOperation

            cost = Decimal(cost) if cost else None
        except InvalidOperation:
            cost = None
        services.add_maintenance(asset=fault.asset, actor=request.user, data={
            "kind": MaintenanceRecord.Kind.CORRECTIVE, "technician": fault.assigned_to,
            "cost": cost, "notes": p.get("resolution", "")[:2000], "fault": fault})
    if status == FaultReport.Status.COMPLETED and p.get("asset_active"):
        services.set_status(asset=fault.asset, actor=request.user, status="active")
    if status in (FaultReport.Status.IN_PROGRESS,) and p.get("asset_maintenance"):
        services.set_status(asset=fault.asset, actor=request.user, status="maintenance")
    messages.success(request, _("Fault report updated."))
    return redirect("asset_fault", org_slug=org_slug, pk=pk)


@require_module("assets")
@require_capability("content.view")
def fault_photo(request, org_slug, pk):
    fault = get_object_or_404(_faults(request), pk=pk)
    if not fault.photo:
        raise Http404
    with fault.photo.open("rb") as fh, Image.open(fh) as img:
        content_type = IMAGE_TYPES.get(img.format, "application/octet-stream")
    return _serve_private(fault.photo, content_type, "photo")

