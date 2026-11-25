from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django_ratelimit.decorators import ratelimit

from .. import services


@ratelimit(key="ip", rate="30/m", block=True)
def invitation_accept(request, token):
    invitation = services.get_invitation_by_token(token)
    if invitation is None or not invitation.is_pending:
        return render(request, "organizations/invitation_invalid.html", status=404)
    error = None
    if request.method == "POST" and request.user.is_authenticated:
        try:
            services.accept_invitation(invitation=invitation, user=request.user, request=request)
        except services.OrganizationError as exc:
            error = str(exc)
        else:
            messages.success(request, _("You joined %(org)s.")
                             % {"org": invitation.organization.name})
            return redirect("dashboard", org_slug=invitation.organization.slug)
    email_matches = (request.user.is_authenticated
                     and request.user.email.lower() == invitation.email.lower())
    return render(request, "organizations/invitation_accept.html", {
        "invitation": invitation, "error": error, "email_matches": email_matches,
    })
