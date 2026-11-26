"""Public lead form (/e/<token>) and the exhibitor's private lead link."""

import csv
import time

from django.core import signing
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit

from .. import services
from ..forms import PublicLeadForm
from ..models import CapturePoint

SALT = "qrumy.events.lead"


def _point(token):
    point = get_object_or_404(CapturePoint.objects.select_related("event", "organization"),
                              capture_token=token)
    if not point.organization.is_active:
        raise Http404
    return point


@never_cache
@ratelimit(key="ip", rate="10/m", method="POST", block=True)
@ratelimit(key="ip", rate="60/h", method="POST", block=True)
def lead_form(request, token):
    point = _point(token)
    event = point.event
    with translation.override(event.language):
        if not event.is_active:
            return render(request, "events/public/closed.html", {"point": point, "event": event})
        kwargs = {"event": event, "org_name": point.company_name or point.organization.name}
        if request.method == "POST":
            form = PublicLeadForm(request.POST, **kwargs)
            try:
                started = signing.loads(request.POST.get("started", ""), salt=SALT,
                                        max_age=86400)
                valid = started.get("p") == point.pk
            except signing.BadSignature:
                valid = False
            if valid and form.is_valid():
                services.capture_lead(point=point, data=form.lead_data(),
                                      consent_text=form.consent_label)
                return redirect("event_public_thanks", token=token)
            if not valid:
                form.add_error(None, translation.gettext("This form expired. Please try again."))
        else:
            form = PublicLeadForm(**kwargs)
        form.initial["started"] = signing.dumps({"p": point.pk, "t": int(time.time())},
                                                salt=SALT)
        return render(request, "events/public/form.html",
                      {"point": point, "event": event, "form": form})


def lead_thanks(request, token):
    point = _point(token)
    with translation.override(point.event.language):
        return render(request, "events/public/thanks.html",
                      {"point": point, "event": point.event})


@never_cache
@ratelimit(key="ip", rate="30/m", block=True)
def portal(request, token):
    """Read-only leads of one collection point for an exhibitor without a Qrumy account."""
    point = services.point_by_portal_token(token)
    if point is None or not point.organization.is_active:
        raise Http404
    leads = point.leads.order_by("-created_at")
    if request.GET.get("format") == "csv":
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="leads-{point.pk}.csv"'
        resp.write("﻿")
        writer = csv.writer(resp)
        writer.writerow(services.CSV_HEADER)
        for row in services.csv_rows(leads):
            writer.writerow(row)
        return resp
    resp = render(request, "events/public/portal.html",
                  {"point": point, "event": point.event, "leads": leads[:500]})
    resp["Referrer-Policy"] = "no-referrer"
    resp["X-Robots-Tag"] = "noindex, nofollow"
    return resp
