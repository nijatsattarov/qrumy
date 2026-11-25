from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.organizations.permissions import require_capability, require_module

from .. import locations as loc_helpers
from .. import services
from ..forms import CategoryForm, LocationForm
from ..models import AssetCategory, Location


@require_module("assets")
@require_capability("content.view")
def setup(request, org_slug):
    org = request.organization
    counts = dict(Location.objects.for_org(org).annotate(n=Count("assets"))
                  .values_list("pk", "n"))
    return render(request, "assets/setup.html", {
        "locations": [(pk, label, loc, counts.get(pk, 0))
                      for pk, label, loc in loc_helpers.ordered_choices(org)],
        "location_form": LocationForm(organization=org, prefix="loc"),
        "categories": AssetCategory.objects.for_org(org).annotate(n=Count("assets")),
        "category_form": CategoryForm(prefix="cat"),
    })


@require_module("assets")
@require_capability("content.edit")
@require_POST
def location_save(request, org_slug, loc_id=None):
    org = request.organization
    location = get_object_or_404(Location.objects.for_org(org), pk=loc_id) if loc_id else None
    form = LocationForm(request.POST, organization=org, prefix="loc")
    if form.is_valid():
        d = form.cleaned_data
        try:
            services.validate_parent(location, d["parent"])
        except services.AssetError as exc:
            messages.error(request, str(exc))
            return redirect("asset_setup", org_slug=org_slug)
        if location is None:
            Location.objects.create(organization=org, name=d["name"].strip(), kind=d["kind"],
                                    parent=d["parent"])
            messages.success(request, _("Location added."))
        else:
            location.name, location.kind, location.parent = d["name"].strip(), d["kind"], \
                d["parent"]
            location.save()
            messages.success(request, _("Location saved."))
    else:
        messages.error(request, _("Enter a location name."))
    return redirect("asset_setup", org_slug=org_slug)


@require_module("assets")
@require_capability("content.delete")
@require_POST
def location_delete(request, org_slug, loc_id):
    location = get_object_or_404(Location.objects.for_org(request.organization), pk=loc_id)
    if location.children.exists():
        messages.error(request, _("Move or delete the locations inside “%(name)s” first.")
                       % {"name": location.name})
    else:
        location.delete()  # assets keep existing, without a location
        messages.success(request, _("Location deleted. Its assets now have no location."))
    return redirect("asset_setup", org_slug=org_slug)


@require_module("assets")
@require_capability("content.edit")
@require_POST
def category_save(request, org_slug, cat_id=None):
    org = request.organization
    category = get_object_or_404(AssetCategory.objects.for_org(org), pk=cat_id) if cat_id \
        else None
    form = CategoryForm(request.POST, prefix="cat")
    if form.is_valid():
        try:
            with transaction.atomic():
                if category is None:
                    AssetCategory.objects.create(organization=org,
                                                 name=form.cleaned_data["name"].strip())
                else:
                    category.name = form.cleaned_data["name"].strip()
                    category.save()
        except IntegrityError:
            messages.error(request, _("A category with this name already exists."))
        else:
            messages.success(request, _("Category saved."))
    return redirect("asset_setup", org_slug=org_slug)


@require_module("assets")
@require_capability("content.delete")
@require_POST
def category_delete(request, org_slug, cat_id):
    category = get_object_or_404(AssetCategory.objects.for_org(request.organization), pk=cat_id)
    category.delete()
    messages.success(request, _("Category deleted. Its assets now have no category."))
    return redirect("asset_setup", org_slug=org_slug)
