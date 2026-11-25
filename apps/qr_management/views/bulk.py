from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from apps.core import quotas
from apps.organizations.permissions import require_capability, require_module

from .. import bulk, services
from ..forms import BulkUploadForm


@require_module("qr")
@require_capability("content.create")
def bulk_create(request, org_slug):
    if not quotas.is_enabled(request.organization, "qr.bulk"):
        return render(request, "qr_management/bulk.html", {"not_in_plan": True})
    form = BulkUploadForm(request.POST or None, request.FILES or None,
                          organization=request.organization)
    errors = []
    if request.method == "POST" and form.is_valid():
        rows, errors = bulk.parse_csv(form.cleaned_data["file"])
        if not errors:
            try:
                created = bulk.create_from_rows(
                    organization=request.organization, actor=request.user, rows=rows,
                    folder=form.cleaned_data.get("folder"), request=request)
            except services.QRError as exc:
                errors = [str(exc)]
            else:
                messages.success(request, _("%(n)s QR codes created.") % {"n": len(created)})
                return redirect("qr_list", org_slug=org_slug)
    return render(request, "qr_management/bulk.html", {
        "form": form, "errors": errors, "max_rows": bulk.MAX_ROWS})


@require_module("qr")
@require_capability("content.create")
def bulk_template(request, org_slug):
    if request.method != "GET":
        raise Http404
    resp = HttpResponse(bulk.TEMPLATE, content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="qrumy-bulk-template.csv"'
    return resp
