from django.urls import path

from . import contact, generator, views

urlpatterns = [
    path("", views.home, name="home"),
    path("qr-generator/fields/", generator.generator_fields, name="generator_fields"),
    path("qr-generator/preview/", generator.generator_preview, name="generator_preview"),
    path("qr-generator/download/<str:fmt>/", generator.generator_download,
         name="generator_download"),
    path("contact/", contact.contact, name="contact"),
    path("pricing/", views.pricing, name="pricing"),
    path("terms/", views.legal, {"kind": "terms"}, name="terms"),
    path("blog/", views.blog_index, name="blog"),
    path("blog/<slug:slug>/", views.blog_post, name="blog_post"),
    path("privacy/", views.legal, {"kind": "privacy"}, name="privacy"),
]
