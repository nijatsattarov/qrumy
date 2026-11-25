from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.audit_logs.services import record
from apps.organizations.permissions import require_capability, require_module

from ..forms import FolderForm
from ..models import Folder


@require_module("qr")
@require_capability("content.create")
@require_POST
def folder_create(request, org_slug):
    form = FolderForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                folder = Folder.objects.create(organization=request.organization,
                                               name=form.cleaned_data["name"].strip())
        except IntegrityError:
            messages.error(request, _("A folder with this name already exists."))
        else:
            record("qr.folder_created", actor=request.user, organization=request.organization,
                   target=folder, request=request)
            return redirect(f"/app/{org_slug}/qr/?folder={folder.pk}")
    return redirect("qr_list", org_slug=org_slug)


@require_module("qr")
@require_capability("content.edit")
@require_POST
def folder_rename(request, org_slug, folder_id):
    folder = get_object_or_404(Folder.objects.for_org(request.organization), pk=folder_id)
    form = FolderForm(request.POST)
    if form.is_valid():
        try:
            with transaction.atomic():
                folder.name = form.cleaned_data["name"].strip()
                folder.save(update_fields=["name", "updated_at"])
        except IntegrityError:
            messages.error(request, _("A folder with this name already exists."))
    return redirect(f"/app/{org_slug}/qr/?folder={folder.pk}")


@require_module("qr")
@require_capability("content.delete")
@require_POST
def folder_delete(request, org_slug, folder_id):
    folder = get_object_or_404(Folder.objects.for_org(request.organization), pk=folder_id)
    record("qr.folder_deleted", actor=request.user, organization=request.organization,
           target=folder, request=request)
    folder.delete()  # codes stay, moved to "no folder"
    messages.success(request, _("Folder deleted. Its QR codes were kept."))
    return redirect("qr_list", org_slug=org_slug)
