from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import Http404
from django.shortcuts import redirect
from django.utils.translation import gettext as _


def _has_totp(user) -> bool:
    from allauth.mfa.models import Authenticator

    return Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).exists()


class AdminAccessMiddleware:
    """Protect the super-admin.

    * Unauthenticated → allauth login (so MFA applies; Django's admin login is never used).
    * Authenticated non-staff → 404 (the admin's existence is not revealed).
    * Staff without TOTP when MFA is required → sent to set it up first.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.prefix = "/" + settings.QRUMY_ADMIN_PATH.lstrip("/")

    def __call__(self, request):
        if request.path.startswith(self.prefix):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not (user.is_active and user.is_staff):
                raise Http404
            if settings.QRUMY_ADMIN_REQUIRE_MFA and not _has_totp(user):
                messages.warning(
                    request, _("Two-factor authentication is required for the admin panel.")
                )
                return redirect("mfa_activate_totp")
        return self.get_response(request)


class HealthCheckMiddleware:
    """Answer ``/healthz`` before host validation and HTTPS redirects.

    Container health checks call the app directly (Host: 127.0.0.1), which
    ALLOWED_HOSTS and SECURE_SSL_REDIRECT would otherwise reject.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/healthz":
            from .views import healthz

            return healthz(request)
        return self.get_response(request)


class SecurityHeadersMiddleware:
    """Headers Django doesn't set itself. Camera access is not needed by any page
    (photo uploads use the file picker, which doesn't require the permission)."""

    POLICY = ("camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
              "interest-cohort=()")

    PRIVATE = ("/app/", "/accounts/", "/invitations/", "/notifications/", "/lang/",
               "/i18n/", "/qr-generator/", "/az/qr-generator/", "/t/", "/az/t/", "/e/x/")

    def __init__(self, get_response):
        from django.conf import settings

        self.get_response = get_response
        self.private = (*self.PRIVATE, "/" + settings.QRUMY_ADMIN_PATH)

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Permissions-Policy", self.POLICY)
        if request.path.startswith(self.private):
            # Keep the admin, the app and internal endpoints out of search results even if
            # a link to them is found somewhere.
            response.setdefault("X-Robots-Tag", "noindex, nofollow")
        return response
