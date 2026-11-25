from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from .. import services
from ..forms import InviteForm, RoleForm
from ..models import Invitation, Membership
from ..permissions import can, require_capability
from ..roles import ROLE_DESCRIPTIONS, assignable_roles, rank


def _team_context(request, invite_form=None):
    org, me = request.organization, request.membership
    members = list(org.memberships.select_related("user").order_by("created_at"))
    for m in members:
        m.manageable = (can(request, "team.manage") and m.role != "owner"
                        and rank(me.role) > rank(m.role))
        m.is_me = m.user_id == request.user.id
    invitations = (Invitation.objects.filter(organization=org, accepted_at__isnull=True,
                                             revoked_at__isnull=True,
                                             expires_at__gt=timezone.now())
                   .select_related("invited_by") if can(request, "team.view") else [])
    return {
        "members": members,
        "invitations": invitations,
        "invite_form": invite_form or (InviteForm(actor_role=me.role)
                                       if can(request, "team.invite") else None),
        "assignable_roles": assignable_roles(me.role),
        "role_descriptions": ROLE_DESCRIPTIONS,
        "team_usage": services.team_usage(org),
    }


def _panel_response(request, invite_form=None):
    template = "organizations/team.html"
    if request.htmx:
        template += "#team-panel"
    return render(request, template, _team_context(request, invite_form))


@require_capability("team.view")
def team(request, org_slug):
    return render(request, "organizations/team.html", _team_context(request))


@require_POST
@require_capability("team.invite")
def team_invite(request, org_slug):
    form = InviteForm(request.POST, actor_role=request.membership.role)
    if form.is_valid():
        try:
            services.invite_member(organization=request.organization,
                                   actor_membership=request.membership,
                                   email=form.cleaned_data["email"],
                                   role=form.cleaned_data["role"], request=request)
        except services.OrganizationError as exc:
            form.add_error("email", str(exc))
        else:
            messages.success(request, _("Invitation sent to %(email)s.")
                             % {"email": form.cleaned_data["email"]})
            if not request.htmx:
                return redirect("team", org_slug=org_slug)
            form = None
    return _panel_response(request, invite_form=form)


@require_POST
@require_capability("team.manage")
def member_role(request, org_slug, member_id):
    target = get_object_or_404(Membership, pk=member_id, organization=request.organization)
    form = RoleForm(request.POST, actor_role=request.membership.role)
    try:
        if not form.is_valid():
            raise services.OrganizationError(_("You cannot assign this role."))
        services.change_role(actor_membership=request.membership, target_membership=target,
                             new_role=form.cleaned_data["role"], request=request)
        messages.success(request, _("Role updated."))
    except services.OrganizationError as exc:
        messages.error(request, str(exc))
    return redirect("team", org_slug=org_slug) if not request.htmx else _panel_response(request)


@require_POST
@require_capability("team.manage")
def member_remove(request, org_slug, member_id):
    target = get_object_or_404(Membership, pk=member_id, organization=request.organization)
    try:
        services.remove_member(actor_membership=request.membership, target_membership=target,
                               request=request)
        messages.success(request, _("Member removed."))
    except services.OrganizationError as exc:
        messages.error(request, str(exc))
    return redirect("team", org_slug=org_slug) if not request.htmx else _panel_response(request)


@require_POST
@require_capability("team.invite")
def invitation_revoke(request, org_slug, invitation_id):
    invitation = get_object_or_404(Invitation, pk=invitation_id,
                                   organization=request.organization)
    services.revoke_invitation(invitation=invitation, actor_membership=request.membership,
                               request=request)
    messages.success(request, _("Invitation revoked."))
    return redirect("team", org_slug=org_slug) if not request.htmx else _panel_response(request)


@require_POST
def leave(request, org_slug):
    try:
        services.leave_organization(membership=request.membership, request=request)
    except services.OrganizationError as exc:
        messages.error(request, str(exc))
        return redirect("team", org_slug=org_slug)
    messages.success(request, _("You left %(org)s.") % {"org": request.organization.name})
    return redirect("app_home")
