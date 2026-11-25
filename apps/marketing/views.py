import json

from django.conf import settings
from django.shortcuts import render
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from apps.subscriptions.features import FEATURES
from apps.subscriptions.models import Plan

PRODUCTS = [
    {"key": "qr", "icon": "qr", "name": _("QR Management"),
     "summary": _("Create static and dynamic QR codes, brand them, change destinations "
                  "after printing and see where every scan comes from."),
     "points": [_("Dynamic codes you can edit anytime"), _("Custom colors, logo and frames"),
                _("Scan analytics by date, device and country")]},
    {"key": "surveys", "icon": "message", "name": _("Surveys & Feedback"),
     "summary": _("Collect customer feedback with QR-powered surveys and track NPS, CSAT and "
                  "CES over time."),
     "points": [_("Builder with 14 question types"), _("NPS, CSAT and CES scoring"),
                _("Assign, tag and resolve responses")]},
    {"key": "events", "icon": "calendar", "name": _("Event Lead Capture"),
     "summary": _("Turn trade-show and event conversations into qualified leads, then follow "
                  "up before they go cold."),
     "points": [_("Exhibitor lead capture by QR"), _("Hot / warm / cold qualification"),
                _("Pipeline, tasks and follow-up templates")]},
    {"key": "assets", "icon": "box", "name": _("Asset Management"),
     "summary": _("Give every machine and tool a QR profile. Staff scan to see its history "
                  "or report a fault in seconds."),
     "points": [_("QR profile for every asset"), _("Fault reporting from a scan"),
                _("Maintenance history and locations")]},
    {"key": "ai", "icon": "sparkles", "name": _("Qrumy Intelligence"),
     "summary": _("AI summaries and recommendations across feedback, leads and assets."),
     "points": [_("Feedback themes and sentiment"), _("Lead summaries"),
                _("Natural-language reports")]},
    {"key": "agency", "icon": "briefcase", "name": _("Qrumy Agency"),
     "summary": _("Manage many client organizations from one workspace with client reports."),
     "points": [_("Client workspaces"), _("Client reporting"), _("White-label options")]},
]


def _plans():
    plans = list(Plan.objects.filter(is_public=True, is_active=True)
                 .prefetch_related("features"))
    for plan in plans:
        feats = {f.feature_key: f for f in plan.features.all()}
        plan.display_features = []
        for key, feature in FEATURES.items():
            pf = feats.get(key)
            if pf is None or not pf.enabled:
                continue
            if feature.kind == "limit":
                value = pf.limit_value if pf.limit_value is not None else _("Unlimited")
                plan.display_features.append(f"{feature.label}: {value}")
            else:
                plan.display_features.append(str(feature.label))
    return plans


FAQ = [
    (_("What is Qrumy?"),
     _("Qrumy is one platform for QR-powered business tools: QR code management, customer "
       "surveys, asset and equipment tracking, and event lead capture, with shared teams, "
       "permissions and analytics.")),
    (_("Is Qrumy really free?"),
     _("Yes. During the beta every released feature is free, with fair-use limits. Paid plans "
       "will come later and existing users will be informed well in advance.")),
    (_("Which products are available today?"),
     _("Qrumy is released step by step. QR Management, Surveys & Feedback and Asset "
       "Management are available now; Event Lead Capture comes next. Each product is marked "
       "as available on this page once it is released.")),
    (_("What is a dynamic QR code?"),
     _("A dynamic QR code points to a short Qrumy link, so you can change where it leads after "
       "printing and see scan statistics. A static QR code stores the content directly and "
       "cannot be changed or tracked.")),
    (_("Can I use Qrumy with my team?"),
     _("Yes. Invite colleagues to your organization and give each person a role — Owner, Admin, "
       "Manager, Member or Viewer. Each organization's data is private to that organization.")),
    (_("Is Qrumy available in Azerbaijani?"),
     _("Yes. Qrumy is available in English and Azerbaijani. You can switch the language at any "
       "time.")),
]


def home(request):
    available = set(settings.QRUMY_AVAILABLE_MODULES)
    products = [{**p, "available": p["key"] in available} for p in PRODUCTS]
    return render(request, "marketing/home.html", {"products": products, "plans": _plans(),
                                                  "faq": FAQ})


def pricing(request):
    return render(request, "marketing/pricing.html", {"plans": _plans()})


def legal(request, kind):
    from django.http import Http404

    from apps.accounts.legal import current

    doc = current(kind)
    if doc is None:
        raise Http404
    return render(request, "marketing/legal.html", {"doc": doc})


def blog_index(request):
    from django.core.paginator import Paginator
    from django.utils import translation

    from .models import Post

    posts = Post.objects.published().filter(language=translation.get_language())
    page = Paginator(posts, 9).get_page(request.GET.get("page"))
    return render(request, "marketing/blog_index.html", {"page": page})


def blog_post(request, slug):
    from django.http import Http404
    from django.shortcuts import redirect
    from django.utils import translation

    from .models import Post

    post = Post.objects.published().filter(slug=slug,
                                           language=translation.get_language()).first()
    if post is None:
        # Switching language on a post leads to the same slug in the other language;
        # posts are written separately per language, so show that language's blog.
        if Post.objects.published().filter(slug=slug).exists():
            return redirect("blog")
        raise Http404
    more = (Post.objects.published().filter(language=post.language)
            .exclude(pk=post.pk)[:3])
    site = settings.SITE_URL
    ld = {"@context": "https://schema.org", "@type": "BlogPosting", "headline": post.title,
          "description": post.excerpt, "inLanguage": post.language,
          "datePublished": post.published_at.isoformat(),
          "dateModified": post.updated_at.isoformat(),
          "author": {"@type": "Organization", "name": post.author_name},
          "publisher": {"@type": "Organization", "name": "Qrumy"},
          "mainEntityOfPage": site + request.path}
    if post.cover:
        ld["image"] = site + post.cover.url
    # Same escaping as json_script: the JSON can never close the <script> element.
    ld_json = mark_safe(json.dumps(ld).translate(  # noqa: S308
        {ord(">"): "\\u003E", ord("<"): "\\u003C", ord("&"): "\\u0026"}))
    return render(request, "marketing/blog_post.html",
                  {"post": post, "more": more, "ld_json": ld_json})
