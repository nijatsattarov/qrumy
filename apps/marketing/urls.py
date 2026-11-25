from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("pricing/", views.pricing, name="pricing"),
    path("terms/", views.legal, {"kind": "terms"}, name="terms"),
    path("blog/", views.blog_index, name="blog"),
    path("blog/<slug:slug>/", views.blog_post, name="blog_post"),
    path("privacy/", views.legal, {"kind": "privacy"}, name="privacy"),
]
