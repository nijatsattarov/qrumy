from django.urls import path
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit

from . import contact, generator, views
from .seo_tools import TOOLS

urlpatterns = [
    path("", views.home, name="home"),
    path("qr-generator/fields/", generator.generator_fields, name="generator_fields"),
    path("qr-generator/preview/", generator.generator_preview, name="generator_preview"),
    path("qr-generator/download/<str:fmt>/", generator.generator_download,
         name="generator_download"),
    path("contact/", contact.contact, name="contact"),
    path("t/", csrf_exempt(ratelimit(key="ip", rate="60/m", block=True)(views.track_event)),
         name="track_event"),
    path("pricing/", views.pricing, name="pricing"),
    path("terms/", views.legal, {"kind": "terms"}, name="terms"),
    path("blog/", views.blog_index, name="blog"),
    path("blog/<slug:slug>/", views.blog_post, name="blog_post"),
    path("privacy/", views.legal, {"kind": "privacy"}, name="privacy"),
    # Free QR generator landing pages (one per QR type / search intent)
    *[path(f"{t.slug}/", views.tool_page, {"slug": t.slug}, name=t.url_name) for t in TOOLS],
]
