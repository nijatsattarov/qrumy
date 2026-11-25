"""Free QR generator on the homepage: static codes, no account, nothing stored.

Static codes hold their content directly, so they keep working without Qrumy. Anything
that needs a server (dynamic links, landing pages, surveys, analytics) sends people to
sign up instead.
"""

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from apps.qr_management.engine import contrast_problems, is_scannable, render_png, render_svg
from apps.qr_management.forms import StyleForm
from apps.qr_management.types import STATIC, get_type, payload_from_form

# Order of the tabs on the homepage. Every type here must support static mode.
FREE_TYPES = ("url", "wifi", "text", "phone", "sms", "email", "whatsapp", "location", "vcard")
DEFAULT_TYPE = "url"
SAMPLE_CONTENT = "https://qrumy.com"  # faded example until the fields are filled in

# Advanced products: shown next to the generator, each leads to sign-up.
PRO_FEATURES = [
    {"icon": "edit", "title": gettext_lazy("Dynamic QR code"),
     "text": gettext_lazy("Change the link after printing and see every scan.")},
    {"icon": "user", "title": gettext_lazy("Business card page"),
     "text": gettext_lazy("A mobile contact page with a “save contact” button.")},
    {"icon": "share", "title": gettext_lazy("Multi-link page"),
     "text": gettext_lazy("All your links and social profiles on one page.")},
    {"icon": "file", "title": gettext_lazy("PDF and menu"),
     "text": gettext_lazy("Upload a menu, catalog or brochure and share it.")},
    {"icon": "message", "title": gettext_lazy("Feedback survey"),
     "text": gettext_lazy("Collect reviews, NPS and ratings by QR code.")},
    {"icon": "box", "title": gettext_lazy("Asset label"),
     "text": gettext_lazy("Equipment profile with fault reporting.")},
]


def free_types():
    return [get_type(k) for k in FREE_TYPES]


def _type(key: str):
    if key not in FREE_TYPES:
        raise Http404
    t = get_type(key)
    if STATIC not in t.modes or t.encode is None:  # safety net if a type ever changes
        raise Http404
    return t


def generator_context(request, type_key: str | None = None) -> dict:
    key = type_key if type_key in FREE_TYPES else DEFAULT_TYPE
    t = _type(key)
    return {"gen_types": free_types(), "gen_type": t, "gen_form": t.form(prefix="c"),
            "gen_style": StyleForm(prefix="s"), "pro_features": PRO_FEATURES}


def _build(request):
    """(type, content, style, logo, errors) from a POSTed generator form."""
    t = _type(request.POST.get("type", DEFAULT_TYPE))
    content_form = t.form(request.POST, prefix="c")
    style_form = StyleForm(request.POST, request.FILES, prefix="s")
    ok_content, ok_style = content_form.is_valid(), style_form.is_valid()
    if not (ok_content and ok_style):
        return t, None, None, None, content_form
    logo = None
    if upload := style_form.cleaned_data.get("logo"):
        logo = upload.read()
    return t, t.encode(payload_from_form(content_form)), style_form.style(), logo, None


@require_GET
def generator_fields(request):
    """HTMX: tabs + content fields for another type (design fields stay as they are)."""
    return render(request, "marketing/generator/_content.html",
                  generator_context(request, request.GET.get("type")))


@require_POST
@ratelimit(key="ip", rate="120/m", block=True)
def generator_preview(request):
    t, content, style, logo, errors = _build(request)
    if content is None:
        style_form = StyleForm(request.POST, prefix="s")
        sample = render_svg(SAMPLE_CONTENT, style_form.style()) if style_form.is_valid() else ""
        return render(request, "marketing/generator/_preview.html",
                      {"empty": True, "sample": sample, "gen_type": t})
    problems = contrast_problems(style)
    scannable = not problems and is_scannable(content, style, logo)
    return render(request, "marketing/generator/_preview.html", {
        "svg": render_svg(content, style, logo), "problems": problems,
        "scannable": scannable, "gen_type": t})


@require_POST
@ratelimit(key="ip", rate="30/m", block=True)
def generator_download(request, fmt: str):
    t, content, style, logo, errors = _build(request)
    back = reverse("home") + f"?type={t.key}#generator"
    if content is None:
        messages.error(request, _("Fill in the fields to create your QR code."))
        return redirect(back)
    if contrast_problems(style) or not is_scannable(content, style, logo):
        messages.error(request, _("This design could not be scanned. Try more contrast or a "
                                  "smaller logo."))
        return redirect(back)
    name = f"qrumy-{t.key}"
    if fmt == "svg":
        resp = HttpResponse(render_svg(content, style, logo), content_type="image/svg+xml")
        resp["Content-Disposition"] = f'attachment; filename="{name}.svg"'
    else:
        resp = HttpResponse(render_png(content, style, 1024, logo), content_type="image/png")
        resp["Content-Disposition"] = f'attachment; filename="{name}.png"'
    resp["Cache-Control"] = "no-store"
    return resp
