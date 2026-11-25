"""Public endpoints behind printed codes: /q/<code>.

Tenant is resolved only from the unguessable short code — never from a session.
"""

from datetime import datetime

from csp.decorators import csp_exempt
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django_ratelimit.decorators import ratelimit

from apps.analytics.ingest import record_scan
from apps.core import quotas
from apps.core.utils import client_ip
from apps.organizations.permissions import require_capability, require_module

from . import redirect_cache
from .models import HostedFile, QRCode
from .types import get_type


def _build_info(qr: QRCode) -> dict:
    t = get_type(qr.qr_type)
    if t.hosted_file:
        kind = "file"
    elif qr.qr_type == "app":
        kind = "app"
    elif t.landing:
        kind = "landing"
    else:
        kind = "redirect"
    org = qr.organization
    status = qr.status
    if qr.deleted_at:
        status = "deleted"
    elif not org.is_active:
        status = QRCode.Status.SUSPENDED
    return {
        "id": qr.pk, "org": org.pk, "status": status, "kind": kind, "type": qr.qr_type,
        "expires_at": qr.expires_at.isoformat() if qr.expires_at else None,
        "dest": t.destination(qr.payload) if kind == "redirect" else "",
        "payload": qr.payload, "name": qr.name,
        "org_name": org.name, "org_logo": org.logo.url if org.logo else "",
        "branding": not quotas.is_enabled(org, "branding.remove"),
    }


def _load(code: str) -> dict:
    info = redirect_cache.get(code)
    if info is None:
        qr = QRCode.objects.select_related("organization").filter(short_code=code).first()
        if qr is None or not qr.is_dynamic:
            raise Http404
        info = _build_info(qr)
        redirect_cache.put(code, info)
    return info


def _status_page(request, info, state: str, status: int):
    return render(request, "qr_management/public/status.html",
                  {"state": state, "info": info}, status=status)


def _no_store(response):
    response["Cache-Control"] = "no-store"
    response["X-Robots-Tag"] = "noindex"
    return response


def _choose_app_url(payload: dict, user_agent: str) -> str:
    ua = (user_agent or "").lower()
    if any(k in ua for k in ("iphone", "ipad", "ipod")) and payload.get("ios_url"):
        return payload["ios_url"]
    if "android" in ua and payload.get("android_url"):
        return payload["android_url"]
    return payload.get("fallback_url", "")


@never_cache
@require_http_methods(["GET", "HEAD"])
@ratelimit(key="ip", rate="120/m", block=True)
def scan(request, code):
    try:
        info = _load(code)
    except Http404:
        return _status_page(request, None, "missing", 404)

    state = info["status"]
    if state == "deleted":
        return _status_page(request, info, "missing", 404)
    if state == QRCode.Status.SUSPENDED:
        return _status_page(request, info, "suspended", 410)
    if state == QRCode.Status.PAUSED:
        return _status_page(request, info, "paused", 200)
    if info["expires_at"] and datetime.fromisoformat(info["expires_at"]) <= timezone.now():
        return _status_page(request, info, "expired", 410)

    record_scan(qr_code_id=info["id"], organization_id=info["org"], ip=client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                referrer=request.META.get("HTTP_REFERER", ""), query=request.GET,
                method=request.method,
                country_header=request.META.get(settings.QRUMY_COUNTRY_HEADER, "")
                if settings.QRUMY_COUNTRY_HEADER else "")

    kind = info["kind"]
    if kind == "redirect":
        return _no_store(HttpResponseRedirect(info["dest"]))
    if kind == "app":
        url = _choose_app_url(info["payload"], request.META.get("HTTP_USER_AGENT", ""))
        if url:
            return _no_store(HttpResponseRedirect(url))
        return _no_store(render(request, "qr_management/public/app.html", {"info": info}))
    if kind == "file":
        return _serve_file(request, info)
    template = f"qr_management/public/{info['type']}.html"
    return _no_store(render(request, template, {"info": info, "p": info["payload"],
                                                "code": code}))


@csp_exempt()  # browsers' built-in PDF viewers break under a strict CSP
def _serve_file(request, info):
    hosted = HostedFile.objects.filter(qr_code_id=info["id"]).first()
    if hosted is None:
        return _status_page(request, info, "missing", 404)
    if settings.QRUMY_SERVE_FILES_WITH_X_ACCEL:
        response = HttpResponse()
        response["X-Accel-Redirect"] = "/protected/" + hosted.file.name
    else:
        response = FileResponse(hosted.file.open("rb"))
    response["Content-Type"] = hosted.content_type
    response["Content-Disposition"] = "inline"
    response["X-Content-Type-Options"] = "nosniff"
    return _no_store(response)


@never_cache
def vcard_download(request, code):
    """Download the contact card behind a dynamic vCard code (not counted as a scan)."""
    info = _load(code)
    if info["type"] != "vcard" or info["status"] != QRCode.Status.ACTIVE:
        raise Http404
    from .types import _vcard

    response = HttpResponse(_vcard(info["payload"]), content_type="text/vcard; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="contact.vcf"'
    return response


@require_module("qr")
@require_capability("content.view")
def preview_landing(request, org_slug, pk):
    """Owner preview of a landing page without counting a scan."""
    qr = get_object_or_404(QRCode.objects.for_org(request.organization).live(), pk=pk)
    info = _build_info(qr)
    if info["kind"] != "landing":
        raise Http404
    return render(request, f"qr_management/public/{qr.qr_type}.html",
                  {"info": info, "p": qr.payload, "code": qr.short_code, "preview": True})
