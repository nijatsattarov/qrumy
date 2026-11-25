"""Public QR profile of an asset (/a/<token>) and fault reporting."""

import time

from django.core import signing
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django_ratelimit.decorators import ratelimit

from apps.core import quotas
from apps.organizations.models import Membership

from . import locations as loc_helpers
from . import services
from .forms import PublicFaultForm
from .models import Asset

SALT = "qrumy.asset.fault"


def _asset(token):
    asset = get_object_or_404(Asset.objects.select_related("organization", "category"),
                              public_token=token)
    if not asset.organization.is_active:
        raise Http404
    return asset


def _ctx(request, asset, **extra):
    org = asset.organization
    member = (request.user.is_authenticated and
              Membership.objects.filter(user=request.user, organization=org).exists())
    last = asset.maintenance.order_by("-performed_on").first()
    return {"asset": asset, "org": org, "member": member,
            "location": loc_helpers.paths(org).get(asset.location_id, ""),
            "last_maintenance": last,
            "branding": not quotas.is_enabled(org, "branding.remove"), **extra}


@never_cache
def profile(request, token):
    asset = _asset(token)
    return render(request, "assets/public/profile.html", _ctx(request, asset))


@never_cache
@ratelimit(key="ip", rate="10/m", method="POST", block=True)
@ratelimit(key="ip", rate="60/h", method="POST", block=True)
def report(request, token):
    asset = _asset(token)
    if request.method == "POST":
        form = PublicFaultForm(request.POST, request.FILES)
        try:
            started = signing.loads(request.POST.get("started", ""), salt=SALT, max_age=86400)
            valid_token = started.get("a") == asset.pk
        except signing.BadSignature:
            valid_token = False
        if not valid_token:
            form.add_error(None, "expired")
        if form.is_valid():
            d = form.cleaned_data
            try:
                services.report_fault(
                    asset=asset, category=d["category"], description=d["description"],
                    priority=d["priority"], photo=d.get("photo"),
                    reporter_name=d.get("reporter_name", ""),
                    reporter_contact=d.get("reporter_contact", ""),
                    reported_by=request.user, via_qr=True)
            except ValidationError as exc:
                form.add_error("photo", exc.messages[0])
            else:
                return redirect("asset_public_thanks", token=token)
        elif "spam" in form.non_field_errors():
            return redirect("asset_public_thanks", token=token)
    else:
        form = PublicFaultForm(initial={
            "started": signing.dumps({"a": asset.pk, "t": int(time.time())}, salt=SALT)})
    if form.is_bound and "expired" in form.non_field_errors():
        form.data = form.data.copy()
        form.data["started"] = signing.dumps({"a": asset.pk, "t": int(time.time())}, salt=SALT)
    return render(request, "assets/public/report.html", _ctx(request, asset, form=form))


def thanks(request, token):
    return render(request, "assets/public/thanks.html", _ctx(request, _asset(token)))
