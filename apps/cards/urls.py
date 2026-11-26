from django.urls import path

from .views import manage, public

app_urlpatterns = [
    path("cards/", manage.card_list, name="card_list"),
    path("cards/new/", manage.card_create, name="card_create"),
    path("cards/<int:pk>/edit/<slug:step>/", manage.card_step, name="card_step"),
    path("cards/<int:pk>/photos/", manage.card_photo_add, name="card_photo_add"),
    path("cards/<int:pk>/photos/<int:photo_id>/delete/", manage.card_photo_delete,
         name="card_photo_delete"),
    path("cards/<int:pk>/publish/", manage.card_publish, name="card_publish"),
    path("cards/<int:pk>/delete/", manage.card_delete, name="card_delete"),
    path("cards/<int:pk>/preview/", manage.card_preview, name="card_preview"),
]

public_urlpatterns = [
    path("<str:token>", public.card_page, name="card_public"),
    path("<str:token>/contact.vcf", public.card_vcard, name="card_vcard"),
    path("<str:token>/go/<int:n>", public.card_link, name="card_link"),
    path("<str:token>/theme.css", public.card_theme, name="card_theme"),
]
