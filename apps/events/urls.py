from django.urls import path

from .views import manage, public

app_urlpatterns = [
    path("events/", manage.event_list, name="event_list"),
    path("events/new/", manage.event_create, name="event_create"),
    path("events/<int:pk>/", manage.event_detail, name="event_detail"),
    path("events/<int:pk>/edit/", manage.event_edit, name="event_edit"),
    path("events/<int:pk>/delete/", manage.event_delete, name="event_delete"),
    path("events/<int:pk>/points/new/", manage.point_save, name="event_point_create"),
    path("events/<int:pk>/points/<int:point_id>/", manage.point_save, name="event_point_update"),
    path("events/<int:pk>/points/<int:point_id>/delete/", manage.point_delete,
         name="event_point_delete"),
    path("events/<int:pk>/points/<int:point_id>/link/", manage.point_portal,
         name="event_point_portal"),
    path("events/<int:pk>/leads/", manage.lead_list, name="event_leads"),
    path("events/<int:pk>/leads/new/", manage.lead_create, name="event_lead_create"),
    path("events/<int:pk>/leads/export.csv", manage.lead_export, name="event_leads_export"),
    path("leads/<int:pk>/", manage.lead_detail, name="event_lead"),
    path("leads/<int:pk>/note/", manage.lead_note, name="event_lead_note"),
    path("leads/<int:pk>/followups/", manage.lead_followup, name="event_lead_followup"),
    path("leads/<int:pk>/followups/<int:followup_id>/", manage.lead_followup,
         name="event_followup_toggle"),
    path("leads/<int:pk>/delete/", manage.lead_delete, name="event_lead_delete"),
]

public_urlpatterns = [
    path("x/<str:token>", public.portal, name="event_portal"),
    path("<str:token>", public.lead_form, name="event_public"),
    path("<str:token>/thanks", public.lead_thanks, name="event_public_thanks"),
]
