from django.urls import path

from .views import invitations

urlpatterns = [
    path("<str:token>/", invitations.invitation_accept, name="invitation_accept"),
]
