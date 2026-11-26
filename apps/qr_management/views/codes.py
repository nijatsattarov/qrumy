import io
import zipfile

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from apps.analytics import reports
from apps.organizations.permissions import can, require_capability, require_module

from .. import services
from ..engine import QRStyle, contrast_problems, is_scannable, render_png, render_svg
from ..forms import SORTS, STATUS_FILTERS, QRMetaForm, StyleForm
from ..models import SHORT_CODE_LENGTH, Folder, HostedFile, QRCode, Tag
from ..types import DYNAMIC, TYPES, listed_types, payload_from_form

PER_PAGE = 24


def _codes(request):
    return QRCode.objects.for_org(request.organization).live()


def _get_code(request, pk):
    return get_object_or_404(_codes(request).select_related("folder"), pk=pk)


def _type_or_404(key, *, creatable=False):
    if key not in TYPES or (creatable and not TYPES[key].listed):
        raise Http404
    return TYPES[key]


# --------------------------------------------------------------------------- list
@require_module("qr")
@require_capability("content.view")
def qr_list(request, org_slug):
    qs = _codes(request).select_related("folder").prefetch_related("tags")
    g = request.GET
    if q := g.get("q", "").strip():
        qs = qs.filter(Q(name__icontains=q) | Q(short_code=q) | Q(tags__name__iexact=q)).distinct()
    if (t := g.get("type")) in TYPES:
        qs = qs.filter(qr_type=t)
    if (m := g.get("mode")) in ("static", "dynamic"):
        qs = qs.filter(mode=m)
    status = g.get("status")
    now = timezone.now()
    if status == "expired":
        qs = qs.filter(status="active", expires_at__lte=now)
    elif status == "active":
        qs = qs.filter(status="active").exclude(expires_at__lte=now)
    elif status in ("paused", "suspended"):
        qs = qs.filter(status=status)
    folder = g.get("folder", "")
    if folder == "none":
        qs = qs.filter(folder__isnull=True)
    elif folder.isdigit():
        qs = qs.filter(folder_id=int(folder))
    if tag := g.get("tag"):
        qs = qs.filter(tags__name__iexact=tag)
    sort = g.get("sort") if g.get("sort") in dict(SORTS) else "-created_at"
    qs = qs.order_by(sort, "-id") if sort != "-last_scan_at" else qs.order_by(
        "-last_scan_at", "-id").exclude(last_scan_at__isnull=True)
    page = Paginator(qs, PER_PAGE).get_page(g.get("page"))
    folders = Folder.objects.for_org(request.organization).order_by("name")
    ctx = {
        "page": page, "folders": folders, "types": TYPES.values(),
        "status_filters": STATUS_FILTERS, "sorts": SORTS, "filters": g,
        "tags": Tag.objects.for_org(request.organization).order_by("name")[:50],
        "dynamic_used": services.dynamic_usage(request.organization),
        "filtered": any(g.get(k) for k in ("q", "type", "mode", "status", "folder", "tag")),
    }
    template = "qr_management/list.html"
    if request.htmx and request.htmx.target == "qr-results":
        template += "#results"
    return render(request, template, ctx)


# --------------------------------------------------------------------------- create / edit
@require_module("qr")
@require_capability("content.create")
def qr_choose_type(request, org_slug):
    from apps.core.qr_products import tiles_for

    return render(request, "qr_management/choose_type.html",
                  {"types": listed_types(), "products": tiles_for(request)})


def _forms(request, type_def, qr=None):
    data = request.POST or None
    files = request.FILES or None
    meta_initial, payload_initial, style_initial = {}, {}, StyleForm.initial_from({})
    if qr is not None:
        meta_initial = {"name": qr.name, "mode": qr.mode, "folder": qr.folder_id,
                        "tags": ", ".join(t.name for t in qr.tags.all()),
                        "expires_at": qr.expires_at}
        payload_initial = type_def.initial(qr.payload)
        style_initial = StyleForm.initial_from(qr.style)
    meta = QRMetaForm(data, organization=request.organization, type_def=type_def,
                      locked_mode=qr.mode if qr else None, initial=meta_initial, prefix="meta")
    payload = type_def.form(data, files, initial=payload_initial, prefix="c")
    style = StyleForm(data, files, initial=style_initial, prefix="s")
    return meta, payload, style


def _apply_errors(exc: ValidationError, form):
    for message in exc.messages:
        form.add_error(None, message)


@require_module("qr")
@require_capability("content.create")
@ratelimit(key="user", rate="120/h", method="POST", block=True)
def qr_create(request, org_slug, type_key):
    type_def = _type_or_404(type_key, creatable=True)
    meta, payload, style = _forms(request, type_def)
    if request.method == "POST" and meta.is_valid() and payload.is_valid() and style.is_valid():
        upload = payload.cleaned_data.get("file") if type_def.hosted_file else None
        mode = meta.cleaned_data["mode"]
        try:
            qr = services.create_qr(
                organization=request.organization, actor=request.user, qr_type=type_key,
                mode=mode, name=meta.cleaned_data["name"], payload=payload_from_form(payload),
                style=style.style(), logo_file=style.cleaned_data.get("logo"), upload=upload,
                folder=meta.cleaned_data.get("folder"), tags=meta.tag_list(),
                expires_at=meta.cleaned_data.get("expires_at"), request=request)
        except services.QRError as exc:
            meta.add_error(None, str(exc))
        except ValidationError as exc:
            target = payload if type_def.hosted_file and "file" in str(exc).lower() else style
            _apply_errors(exc, target)
        else:
            messages.success(request, _("QR code created."))
            return redirect("qr_detail", org_slug=org_slug, pk=qr.pk)
    return render(request, "qr_management/form.html", {
        "type_def": type_def, "meta": meta, "payload": payload, "style": style, "qr": None,
        "dynamic_used": services.dynamic_usage(request.organization)})


@require_module("qr")
@require_capability("content.edit")
def qr_edit(request, org_slug, pk):
    qr = _get_code(request, pk)
    if qr.status == QRCode.Status.SUSPENDED:
        messages.error(request, _("This QR code was suspended by Qrumy and cannot be edited."))
        return redirect("qr_detail", org_slug=org_slug, pk=pk)
    type_def = qr.type_def
    meta, payload, style = _forms(request, type_def, qr)
    if request.method == "POST" and meta.is_valid() and payload.is_valid() and style.is_valid():
        upload = payload.cleaned_data.get("file") if type_def.hosted_file else None
        try:
            services.update_qr(
                qr=qr, actor=request.user, name=meta.cleaned_data["name"],
                payload=payload_from_form(payload), style=style.style(),
                logo_file=style.cleaned_data.get("logo"),
                remove_logo=style.cleaned_data.get("remove_logo"), upload=upload,
                folder=meta.cleaned_data.get("folder"), tags=meta.tag_list(),
                expires_at=meta.cleaned_data.get("expires_at"), request=request)
        except ValidationError as exc:
            _apply_errors(exc, style)
        else:
            messages.success(request, _("Changes saved."))
            return redirect("qr_detail", org_slug=org_slug, pk=pk)
    return render(request, "qr_management/form.html", {
        "type_def": type_def, "meta": meta, "payload": payload, "style": style, "qr": qr})


@require_module("qr")
@require_capability("content.create")
@require_POST
def qr_preview(request, org_slug):
    """Live design preview (HTMX). Returns an SVG plus scannability feedback."""
    type_key = request.POST.get("type", "")
    type_def = _type_or_404(type_key)
    qr = None
    if pk := request.POST.get("qr"):
        qr = _codes(request).filter(pk=pk).first()
    style_form = StyleForm(request.POST, request.FILES, prefix="s")
    if not style_form.is_valid():
        return render(request, "qr_management/_preview.html", {"error": True})
    style = style_form.style()
    mode = qr.mode if qr else request.POST.get("meta-mode", type_def.default_mode)
    if mode == DYNAMIC:
        content = qr.short_url if qr else (
            f"{_base_url()}{'x' * SHORT_CODE_LENGTH}")
    else:
        pf = type_def.form(request.POST, prefix="c")
        content = type_def.encode(payload_from_form(pf)) if pf.is_valid() else "https://qrumy.com"
    logo = None
    if upload := style_form.cleaned_data.get("logo"):
        logo = upload.read()
    elif qr and not style_form.cleaned_data.get("remove_logo"):
        logo = qr.logo_bytes()
    problems = contrast_problems(style)
    scannable = not problems and is_scannable(content, style, logo)
    return render(request, "qr_management/_preview.html", {
        "svg": render_svg(content, style, logo), "problems": problems, "scannable": scannable})


def _base_url():
    from django.conf import settings

    return settings.QRUMY_QR_BASE_URL


# --------------------------------------------------------------------------- detail
@require_module("qr")
@require_capability("content.view")
def qr_detail(request, org_slug, pk):
    qr = _get_code(request, pk)
    try:
        days = int(request.GET.get("days", 30))
    except ValueError:
        days = 30
    days = days if days in (7, 30, 90, 365) else 30
    period = reports.Period.last_days(days)
    org = request.organization
    analytics = None
    if qr.is_dynamic and can(request, "analytics.view"):
        analytics = {
            "days": days, "totals": reports.totals(org, period, qr),
            "series": reports.timeseries(org, period, qr),
            "breakdowns": [(dim, label, reports.breakdown(org, period, dim, qr))
                           for dim, label in BREAKDOWNS],
        }
    return render(request, "qr_management/detail.html", {
        "qr": qr, "svg": render_svg(qr.encoded_content, QRStyle.from_dict(qr.style),
                                    qr.logo_bytes()),
        "analytics": analytics, "png_sizes": (512, 1024, 2048, 4096),
        "hosted_file": HostedFile.objects.filter(qr_code=qr).first()
        if qr.type_def.hosted_file else None,
        "periods": PERIODS,
    })


PERIODS = [(7, gettext_lazy("7 days")), (30, gettext_lazy("30 days")),
           (90, gettext_lazy("90 days")), (365, gettext_lazy("12 months"))]

BREAKDOWNS = [("device", gettext_lazy("Devices")), ("os", gettext_lazy("Operating systems")),
              ("browser", gettext_lazy("Browsers")), ("country", gettext_lazy("Countries")),
              ("city", gettext_lazy("Cities")), ("referrer", gettext_lazy("Referrers")),
              ("source", gettext_lazy("UTM sources")), ("campaign", gettext_lazy("Campaigns"))]


@require_module("qr")
@require_capability("content.view")
def qr_download(request, org_slug, pk, fmt):
    qr = _get_code(request, pk)
    style = QRStyle.from_dict(qr.style)
    name = slugify(qr.name) or "qr-code"
    if fmt == "svg":
        resp = HttpResponse(render_svg(qr.encoded_content, style, qr.logo_bytes()),
                            content_type="image/svg+xml")
        resp["Content-Disposition"] = f'attachment; filename="{name}.svg"'
        return resp
    if fmt == "png":
        try:
            size = int(request.GET.get("size", 1024))
        except ValueError:
            size = 1024
        resp = HttpResponse(render_png(qr.encoded_content, style, size, qr.logo_bytes()),
                            content_type="image/png")
        resp["Content-Disposition"] = f'attachment; filename="{name}-{size}.png"'
        return resp
    raise Http404


# --------------------------------------------------------------------------- actions
@require_module("qr")
@require_capability("content.edit")
@require_POST
def qr_set_status(request, org_slug, pk):
    qr = _get_code(request, pk)
    try:
        services.set_status(qr=qr, actor=request.user, status=request.POST.get("status", ""),
                            request=request)
        messages.success(request, _("QR code activated.") if qr.status == "active"
                         else _("QR code paused. Scans now show an 'inactive' page."))
    except services.QRError as exc:
        messages.error(request, str(exc))
    return redirect("qr_detail", org_slug=org_slug, pk=pk)


@require_module("qr")
@require_capability("content.delete")
@require_POST
def qr_delete(request, org_slug, pk):
    qr = _get_code(request, pk)
    services.delete_qr(qr=qr, actor=request.user, request=request)
    messages.success(request, _("QR code deleted."))
    return redirect("qr_list", org_slug=org_slug)


MAX_EXPORT = 200


@require_module("qr")
@require_capability("content.view")
@require_POST
def qr_bulk_action(request, org_slug):
    ids = [int(i) for i in request.POST.getlist("ids") if i.isdigit()]
    codes = list(_codes(request).filter(pk__in=ids))
    action = request.POST.get("action")
    if not codes:
        messages.error(request, _("Select at least one QR code."))
        return redirect("qr_list", org_slug=org_slug)
    if action in ("export_png", "export_svg"):
        if len(codes) > MAX_EXPORT:
            messages.error(request, _("Export up to %(n)s codes at a time.") % {"n": MAX_EXPORT})
            return redirect("qr_list", org_slug=org_slug)
        return _zip_export(codes, action.removeprefix("export_"))
    if action in ("pause", "activate"):
        if not can(request, "content.edit"):
            raise Http404
        for qr in codes:
            if qr.status != QRCode.Status.SUSPENDED:
                services.set_status(qr=qr, actor=request.user,
                                    status="paused" if action == "pause" else "active",
                                    request=request)
        messages.success(request, _("%(n)s QR codes updated.") % {"n": len(codes)})
    elif action == "move":
        if not can(request, "content.edit"):
            raise Http404
        folder_id = request.POST.get("folder")
        folder = (Folder.objects.for_org(request.organization).filter(pk=folder_id).first()
                  if folder_id and folder_id.isdigit() else None)
        QRCode.objects.filter(pk__in=[c.pk for c in codes]).update(folder=folder)
        messages.success(request, _("%(n)s QR codes moved.") % {"n": len(codes)})
    elif action == "delete":
        if not can(request, "content.delete"):
            raise Http404
        for qr in codes:
            services.delete_qr(qr=qr, actor=request.user, request=request)
        messages.success(request, _("%(n)s QR codes deleted.") % {"n": len(codes)})
    return redirect(_safe_next(request, org_slug))


def _safe_next(request, org_slug):
    from django.urls import reverse
    from django.utils.http import url_has_allowed_host_and_scheme

    nxt = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return reverse("qr_list", kwargs={"org_slug": org_slug})


def _zip_export(codes, fmt):
    buf = io.BytesIO()
    used = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for qr in codes:
            style = QRStyle.from_dict(qr.style)
            base = slugify(qr.name) or "qr-code"
            name, n = base, 2
            while name in used:
                name, n = f"{base}-{n}", n + 1
            used.add(name)
            if fmt == "svg":
                zf.writestr(f"{name}.svg", render_svg(qr.encoded_content, style, qr.logo_bytes()))
            else:
                zf.writestr(f"{name}.png",
                            render_png(qr.encoded_content, style, 1024, qr.logo_bytes()))
    resp = HttpResponse(buf.getvalue(), content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="qrumy-codes-{fmt}.zip"'
    return resp
