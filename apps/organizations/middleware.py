from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.shortcuts import render

from .models import Membership

SESSION_KEY = "current_org"


class OrganizationMiddleware:
    """Resolve ``/app/<org_slug>/…`` to an organization the user belongs to.

    A slug the user is not a member of returns 404 — the same response as a slug
    that does not exist, so other tenants' organizations cannot be discovered.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.organization = None
        request.membership = None
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        slug = view_kwargs.get("org_slug")
        if slug is None:
            return None
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        membership = (Membership.objects.select_related("organization")
                      .filter(user=request.user, organization__slug=slug).first())
        if membership is None:
            raise Http404
        organization = membership.organization
        if not organization.is_active:
            return render(request, "organizations/suspended.html",
                          {"organization": organization}, status=403)
        request.organization = organization
        request.membership = membership
        if request.session.get(SESSION_KEY) != slug:
            request.session[SESSION_KEY] = slug
        return None
