from django.conf import settings
from django.contrib import messages
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


@require_POST
def set_language(request):
    """Django's set_language + persist the choice on the signed-in user."""
    response = django_set_language(request)
    lang = request.POST.get("language")
    if request.user.is_authenticated and lang in dict(settings.LANGUAGES):
        request.user.language = lang
        request.user.save(update_fields=["language"])
    return response
