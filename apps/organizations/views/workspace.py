from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.audit_logs.models import AuditLog
from apps.core import quotas, widgets

from .. import services
from ..forms import OrganizationCreateForm, OrganizationSettingsForm
from ..middleware import SESSION_KEY
from ..models import Invitation, Membership
from ..permissions import can, require_capability


@login_required
def app_home(request):
    """Entry point after login: last used organization, else the first, else onboarding."""
    memberships = Membership.objects.filter(user=request.user).select_related("organization")
    if not memberships:
        return redirect("organization_create")
    last = request.session.get(SESSION_KEY)
    chosen = next((m for m in memberships if m.organization.slug == last), memberships[0])
    return redirect("dashboard", org_slug=chosen.organization.slug)


@login_required
def organization_create(request):
    form = OrganizationCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        org = services.create_organization(owner=request.user, request=request,
                                           **form.cleaned_data)
        messages.success(request, _("Welcome to Qrumy! Your organization is ready."))
        return redirect("dashboard", org_slug=org.slug)
    has_orgs = Membership.objects.filter(user=request.user).exists()
    return render(request, "organizations/create.html", {"form": form, "has_orgs": has_orgs})


def dashboard(request, org_slug):
    org = request.organization
    members = org.memberships.count()
    pending = Invitation.objects.filter(organization=org, accepted_at__isnull=True,
                                        revoked_at__isnull=True,
                                        expires_at__gt=timezone.now()).count()
    activity = (AuditLog.objects.filter(organization=org).select_related("actor")[:8]
                if can(request, "audit.view") else [])
    steps = [
        {"label": _("Create your organization"), "done": True, "url": None},
        {"label": _("Complete your organization profile"),
         "done": bool(org.logo and org.website and org.contact_email),
         "url": "organization_settings" if can(request, "org.settings.edit") else None},
        {"label": _("Invite a teammate"), "done": members > 1 or pending > 0,
         "url": "team" if can(request, "team.invite") else None},
    ]
    return render(request, "organizations/dashboard.html", {
        "members_count": members, "pending_count": pending, "activity": activity,
        "steps": steps, "steps_done": sum(s["done"] for s in steps),
        "plan_name": quotas.plan_name(org),
        "widgets": widgets.for_request(request),
    })


@require_capability("org.settings.edit")
def organization_settings(request, org_slug):
    org = request.organization
    form = OrganizationSettingsForm(request.POST or None, request.FILES or None, instance=org)
    if request.method == "POST" and form.is_valid():
        services.update_organization(organization=org, actor=request.user, form=form,
                                     request=request)
        messages.success(request, _("Organization settings saved."))
        return redirect("organization_settings", org_slug=org.slug)
    return render(request, "organizations/settings.html", {
        "form": form,
        "transfer_candidates": org.memberships.exclude(user=request.user).select_related("user"),
    })


@require_capability("org.delete")
def organization_danger(request, org_slug):
    org = request.organization
    if request.method != "POST":
        return redirect("organization_settings", org_slug=org_slug)
    action = request.POST.get("action")
    if action == "transfer":
        target = org.memberships.filter(pk=request.POST.get("member")).first()
        try:
            if target is None:
                raise services.OrganizationError(_("Choose another member of this organization."))
            services.transfer_ownership(organization=org, actor_membership=request.membership,
                                        target_membership=target, request=request)
        except services.OrganizationError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, _("Ownership transferred. You are now an admin."))
        return redirect("organization_settings", org_slug=org_slug)
    if action == "delete":
        if request.POST.get("confirm_name", "").strip() != org.name:
            messages.error(request, _("Type the organization name exactly to confirm."))
            return redirect("organization_settings", org_slug=org_slug)
        name = org.name
        services.delete_organization(organization=org, actor=request.user, request=request)
        request.session.pop("current_org", None)
        messages.success(request, _("%(org)s and all its data were deleted.") % {"org": name})
        return redirect("app_home")
    return redirect("organization_settings", org_slug=org_slug)
