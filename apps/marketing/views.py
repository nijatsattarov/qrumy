import json

from django.conf import settings
from django.shortcuts import render
from django.utils import translation
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
    {"key": "cards", "icon": "user", "name": _("Qrumy Card"),
     "summary": _("Digital business cards for people and companies: photo, contacts, "
                  "location, social media and a gallery, shared by QR code or link."),
     "points": [_("Four templates in your colours"), _("“Save contact” with one tap"),
                _("Views, saved contacts and link clicks")]},
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
     _("QR Management, Surveys & Feedback, Qrumy Card, Digital Menu, Event Lead Capture and "
       "Asset Management are available now. Qrumy Intelligence (AI) and the Agency workspace "
       "come later; each product is marked as available on this page once it is released.")),
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
    from . import seo
    from .generator import generator_context
    from .seo_tools import TOOLS, content

    meta = seo.page_meta(request, "home", **seo.defaults_for("home"))
    lang = translation.get_language()
    tools = [{"url_name": t.url_name, "icon": t.icon,
              "label": content(t, lang)["link_label"]} for t in TOOLS]
    app_ld = {"@type": "WebApplication", "@id": settings.SITE_URL + "/#app", "name": "Qrumy",
              "url": settings.SITE_URL + "/", "applicationCategory": "BusinessApplication",
              "operatingSystem": "Any (web browser)", "inLanguage": lang,
              "description": str(meta["description"]),
              "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD",
                         "description": str(_("Free static QR code generator, no signup"))},
              "publisher": {"@id": settings.SITE_URL + "/#organization"}}
    website_ld = {"@type": "WebSite", "@id": settings.SITE_URL + "/#website", "name": "Qrumy",
                  "url": settings.SITE_URL + "/", "inLanguage": lang,
                  "publisher": {"@id": settings.SITE_URL + "/#organization"}}
    with translation.override(lang):
        faq = [(str(q), str(a)) for q, a in FAQ]
    return render(request, "marketing/home.html", {
        "products": products, "plans": _plans(), "faq": FAQ, "seo": meta, "tools": tools,
        "ld_json": seo.graph(seo.organization_ld(), website_ld, app_ld, seo.faq_ld(faq)),
        **generator_context(request, request.GET.get("type"))})


def tool_page(request, slug):
    """A free QR generator landing page for one QR type."""
    from django.urls import reverse

    from . import seo
    from .generator import generator_context
    from .seo_tools import TOOLS_BY_SLUG, content

    tool = TOOLS_BY_SLUG[slug]
    lang = translation.get_language()
    c = content(tool, lang)
    meta = seo.page_meta(request, f"tool:{slug}", title=c["title"],
                         description=c["description"], h1=c["h1"])
    related = []
    for rel in tool.related:
        t = TOOLS_BY_SLUG[rel]
        rc = content(t, lang)
        related.append({"url_name": t.url_name, "icon": t.icon, "label": rc["link_label"],
                        "text": rc["description"]})
    home_name = str(_("Home"))
    crumbs = [(home_name, reverse("home"))]
    if slug != "qr-code-generator":
        crumbs.append((str(content(TOOLS_BY_SLUG["qr-code-generator"], lang)["link_label"]),
                       reverse("tool_qr_code_generator")))
    crumbs.append((c["h1"], request.path))
    app_ld = {"@type": "WebApplication", "name": c["h1"], "url": meta["url"],
              "applicationCategory": "UtilitiesApplication",
              "operatingSystem": "Any (web browser)", "inLanguage": lang,
              "description": c["description"], "isAccessibleForFree": True,
              "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
              "publisher": {"@id": settings.SITE_URL + "/#organization"}}
    if not seo.is_bot(request):
        seo.track("tool_view", page=f"tool:{slug}", language=lang,
                  source=seo.traffic_source(request))
    from .models import Post

    guide = (Post.objects.published().filter(
        language=lang, slug__in=["static-vs-dynamic", "statik-ve-dinamik-qr-kod"]).first()
        or Post.objects.published().filter(language=lang).first())
    return render(request, "marketing/tool.html", {
        "tool": tool, "c": c, "seo": meta, "related": related, "crumbs": crumbs, "guide": guide,
        "ld_json": seo.graph(seo.organization_ld(), app_ld, seo.breadcrumbs_ld(crumbs),
                             seo.faq_ld(c["faq"])),
        **generator_context(request, request.GET.get("type") or tool.type_key)})


def pricing(request):
    from . import seo

    meta = seo.page_meta(request, "pricing", **seo.defaults_for("pricing"))
    if not seo.is_bot(request):
        seo.track("pricing_view", page="pricing", language=translation.get_language(),
                  source=seo.traffic_source(request))
    return render(request, "marketing/pricing.html", {"plans": _plans(), "seo": meta})


def legal(request, kind):
    from django.http import Http404

    from apps.accounts.legal import current

    from . import seo

    doc = current(kind)
    if doc is None:
        raise Http404
    first = next((line.strip() for line in doc.body.splitlines()
                  if line.strip() and not line.startswith("#")), "")
    if len(first) > 155:
        first = first[:152].rsplit(" ", 1)[0] + "…"
    meta = seo.page_meta(request, kind, title=doc.title, description=first)
    return render(request, "marketing/legal.html", {"doc": doc, "seo": meta})


def blog_index(request):
    from django.core.paginator import Paginator

    from . import seo
    from .models import Post

    posts = Post.objects.published().filter(language=translation.get_language())
    page = Paginator(posts, 9).get_page(request.GET.get("page"))
    meta = seo.page_meta(request, "blog", **seo.defaults_for("blog"))
    if page.number > 1:
        meta["noindex"] = True  # page 2+ of the list: crawl links, don't index the list
    return render(request, "marketing/blog_index.html", {"page": page, "seo": meta})


def blog_post(request, slug):
    from django.http import Http404
    from django.shortcuts import redirect
    from django.urls import reverse

    from . import seo
    from .models import Post
    from .seo_tools import TOOLS_BY_SLUG, content

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
    meta = seo.page_meta(request, f"post:{post.pk}", title=post.seo_title or post.title,
                         description=post.meta_description or post.excerpt,
                         image=post.cover.url if post.cover else "", og_type="article")
    if post.keywords and not meta["keywords"]:
        meta["keywords"] = post.keywords
    crumbs = [(str(_("Home")), reverse("home")), (str(_("Blog")), reverse("blog")),
              (post.title, request.path)]
    posting = {"@type": "BlogPosting", "headline": post.title[:110],
               "description": meta["description"], "inLanguage": post.language,
               "datePublished": post.published_at.isoformat(),
               "dateModified": post.updated_at.isoformat(),
               "author": {"@type": "Organization" if post.author_name == "Qrumy" else "Person",
                          "name": post.author_name},
               "publisher": {"@id": site + "/#organization"},
               "mainEntityOfPage": {"@type": "WebPage", "@id": site + request.path},
               "image": meta["image"]}
    if post.keywords:
        posting["keywords"] = post.keywords
    tools = [TOOLS_BY_SLUG[s] for s in ("qr-code-generator", "wifi-qr-code-generator",
                                        "whatsapp-qr-code-generator")]
    lang = post.language
    tool_links = [{"url_name": t.url_name, "icon": t.icon,
                   "label": content(t, lang)["link_label"]} for t in tools]
    return render(request, "marketing/blog_post.html", {
        "post": post, "more": more, "seo": meta, "crumbs": crumbs, "tool_links": tool_links,
        "ld_json": seo.graph(seo.organization_ld(), posting, seo.breadcrumbs_ld(crumbs))})


def track_event(request):
    """Beacon for anonymous CTA click counters from public pages."""
    from django.http import HttpResponse, HttpResponseNotAllowed

    from . import seo

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    try:
        data = json.loads(request.body or b"{}")
    except ValueError:
        return HttpResponse(status=400)
    name = str(data.get("e", ""))
    if name in ("cta_dynamic_click", "cta_upgrade_click") and not seo.is_bot(request):
        seo.track(name, page=str(data.get("p", ""))[:80],
                  language=translation.get_language() or "")
    return HttpResponse(status=204)
