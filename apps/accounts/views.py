from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from django.views.i18n import set_language as django_set_language

from .forms import ProfileForm


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Your profile has been updated."))
        response = redirect("account_profile")
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, request.user.language,
                            samesite="Lax")
        return response
    return render(request, "accounts/profile.html", {"form": form})


def switch_language(request, code):
    """GET /lang/<code>/?next=… — plain link, so it works without JavaScript or a CSRF token.

    Remembers the choice (cookie + signed-in user) and returns to the same page in the
    new language.
    """
    from django.urls import translate_url
    from django.utils.http import url_has_allowed_host_and_scheme

    languages = dict(settings.LANGUAGES)
    if code not in languages:
        code = settings.LANGUAGE_CODE
    nxt = request.GET.get("next") or "/"
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        nxt = "/"
    # translate_url only resolves paths in the active language, so activate the language
    # the "next" page is in (from its /az/ prefix; no prefix means the default language).
    from urllib.parse import urlsplit

    from django.utils import translation

    current = translation.get_language_from_path(urlsplit(nxt).path) or settings.LANGUAGE_CODE
    with translation.override(current):
        target = translate_url(nxt, code)
    response = redirect(target)
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, code, max_age=365 * 24 * 3600,
                        samesite="Lax", secure=request.is_secure())
    if request.user.is_authenticated and request.user.language != code:
        request.user.language = code
        request.user.save(update_fields=["language"])
    return response


@require_POST
def set_language(request):
    """Django's set_language + persist the choice on the signed-in user."""
    response = django_set_language(request)
    lang = request.POST.get("language")
    if request.user.is_authenticated and lang in dict(settings.LANGUAGES):
        request.user.language = lang
        request.user.save(update_fields=["language"])
    return response


@login_required
def delete_account(request):
    user = request.user
    owned = list(user.owned_organizations.all())
    error = None
    if request.method == "POST" and not owned:
        if not user.check_password(request.POST.get("password", "")):
            error = _("The password is not correct.")
        elif request.POST.get("confirm") != "on":
            error = _("Please confirm that you understand this cannot be undone.")
        else:
            from apps.audit_logs.models import AuditLog
            from apps.audit_logs.services import record

            record("account.deleted", actor=user, request=request)
            # Keep the audit trail but drop the personal email of the deleted person.
            AuditLog.objects.filter(actor=user).update(actor_email=f"deleted-user-{user.pk}")
            logout(request)
            user.delete()
            messages.success(request, _("Your account was deleted."))
            return redirect("home")
    return render(request, "accounts/delete.html", {"owned": owned, "error": error})
