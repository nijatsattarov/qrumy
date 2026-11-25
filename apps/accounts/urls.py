from django.urls import path

from . import views

urlpatterns = [
    path("profile/", views.profile, name="account_profile"),
    path("delete/", views.delete_account, name="account_delete"),
]
