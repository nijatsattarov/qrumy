from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("pricing/", views.pricing, name="pricing"),
    path("terms/", views.legal, {"kind": "terms"}, name="terms"),
    path("privacy/", views.legal, {"kind": "privacy"}, name="privacy"),
]
