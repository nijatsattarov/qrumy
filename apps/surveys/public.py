"""Public survey pages: /s/<token> (and /embed). Tenant comes only from the token."""

import time

from csp.decorators import csp_replace
from django.core import signing
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.utils import translation
from django.views.decorators.cache import cache_control, never_cache
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from apps.analytics.enrich import is_bot
from apps.organizations.permissions import require_capability, require_module

from . import services
from .forms import PublicSurveyForm
from .models import Response, Survey

SALT = "qrumy.survey.start"
MAX_AGE = 60 * 60 * 24
SOURCES = {c for c, _ in Response.Source.choices}


def _start_token(survey) -> str:
    return signing.dumps({"s": survey.pk, "t": int(time.time())}, salt=SALT)


def _started_at(survey, token: str) -> int | None:
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
    except signing.BadSignature:
        return None
    return data["t"] if data.get("s") == survey.pk else None


def _context(survey, **extra):
    org = survey.organization
    logo = survey.logo.url if survey.logo else (org.logo.url if org.logo else "")
    from apps.core import quotas

    return {"survey": survey, "org": org, "logo": logo,
            "branding": not quotas.is_enabled(org, "branding.remove"), **extra}


def _closed(request, survey, reason, embed):
    return render(request, "surveys/public/closed.html",
                  _context(survey, reason=reason, embed=embed), status=200)


@never_cache
@csrf_exempt  # anonymous form that must also work inside third-party iframes; see checks below
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@ratelimit(key="ip", rate="200/h", method="POST", block=True)
def survey_page(request, token, embed=False):
    survey = get_object_or_404(Survey.objects.select_related("organization"),
                               public_token=token)
    if not survey.organization.is_active:
        raise Http404
    source = "embed" if embed else request.GET.get("src", "link")
    source = source if source in SOURCES else "link"
    with translation.override(survey.language):
        reason = survey.closed_reason()
        if reason == "draft":
            raise Http404
        if reason:
            return _closed(request, survey, reason, embed)
        questions = survey.questions.all()
        started = None
        if request.method == "POST":
            form = PublicSurveyForm(request.POST, survey=survey, questions=questions)
            started = _started_at(survey, request.POST.get("started", ""))
            if started is None:
                form.add_error(None, translation.gettext(
                    "This form expired. Please reload the page and try again."))
            if form.is_valid():
                try:
                    services.submit_response(
                        survey=survey, answers=form.answers(), source=source,
                        language=survey.language, duration=int(time.time()) - started,
                        contact_name=form.cleaned_data.get("contact_name", ""),
                        contact_email=form.cleaned_data.get("contact_email", ""),
                        consent=form.cleaned_data.get("consent", False))
                except services.SurveyError as exc:
                    return _closed(request, survey, str(exc), embed)
                if survey.redirect_url and not embed:
                    return HttpResponseRedirect(survey.redirect_url)
                return render(request, "surveys/public/thanks.html",
                              _context(survey, embed=embed))
            if form.non_field_errors() and "spam" in form.non_field_errors():
                return render(request, "surveys/public/thanks.html",
                              _context(survey, embed=embed))  # don't tell bots
        else:
            form = PublicSurveyForm(initial={"started": _start_token(survey)}, survey=survey,
                                    questions=questions)
            cookie = f"qs_{survey.public_token}"
            if not request.COOKIES.get(cookie) and not is_bot(
                    request.META.get("HTTP_USER_AGENT", ""), request.method):
                services.record_view(survey)
        if form.is_bound and started is None:
            form.data = form.data.copy()
            form.data["started"] = _start_token(survey)  # let the person retry
        response = render(request, "surveys/public/form.html",
                          _context(survey, form=form, embed=embed, source=source))
    if request.method == "GET":
        response.set_cookie(f"qs_{survey.public_token}", "1", max_age=MAX_AGE, samesite="Lax",
                            secure=request.is_secure(), httponly=True)
    return response


@xframe_options_exempt
@csp_replace({"frame-ancestors": ["*"]})
def survey_embed(request, token):
    return survey_page(request, token, embed=True)


@cache_control(max_age=3600, public=True)
def survey_theme(request, token):
    """Per-survey colors as a stylesheet (keeps the page free of inline styles for CSP)."""
    survey = get_object_or_404(Survey, public_token=token)
    color = survey.accent_color
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    on_accent = "#FFFFFF" if luminance < 160 else "#101B3A"
    css = (f":root{{--survey-accent:{color};--survey-on-accent:{on_accent};"
           f"--survey-accent-soft:rgb({r} {g} {b} / 0.10);}}\n")
    return HttpResponse(css, content_type="text/css; charset=utf-8")


@require_module("surveys")
@require_capability("content.view")
def survey_preview(request, org_slug, pk):
    survey = get_object_or_404(Survey.objects.for_org(request.organization), pk=pk)
    with translation.override(survey.language):
        form = PublicSurveyForm(initial={"started": ""}, survey=survey,
                                questions=survey.questions.all())
        return render(request, "surveys/public/form.html",
                      _context(survey, form=form, embed=False, preview=True))
