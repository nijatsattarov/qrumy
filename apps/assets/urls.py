from django.urls import path

from . import public
from .views import assets, faults, setup

app_urlpatterns = [
    path("assets/", assets.asset_list, name="asset_list"),
    path("assets/new/", assets.asset_create, name="asset_create"),
    path("assets/export.csv", assets.asset_export, name="asset_export"),
    path("assets/setup/", setup.setup, name="asset_setup"),
    path("assets/setup/locations/new/", setup.location_save, name="asset_location_create"),
    path("assets/setup/locations/<int:loc_id>/", setup.location_save,
         name="asset_location_update"),
    path("assets/setup/locations/<int:loc_id>/delete/", setup.location_delete,
         name="asset_location_delete"),
    path("assets/setup/categories/new/", setup.category_save, name="asset_category_create"),
    path("assets/setup/categories/<int:cat_id>/", setup.category_save,
         name="asset_category_update"),
    path("assets/setup/categories/<int:cat_id>/delete/", setup.category_delete,
         name="asset_category_delete"),
    path("assets/files/<int:doc_id>/", assets.document_file, name="asset_document_file"),
    path("assets/faults/", faults.fault_list, name="asset_faults"),
    path("assets/faults/<int:pk>/", faults.fault_detail, name="asset_fault"),
    path("assets/faults/<int:pk>/update/", faults.fault_update, name="asset_fault_update"),
    path("assets/faults/<int:pk>/photo/", faults.fault_photo, name="asset_fault_photo"),
    path("assets/<int:pk>/", assets.asset_detail, name="asset_detail"),
    path("assets/<int:pk>/edit/", assets.asset_edit, name="asset_edit"),
    path("assets/<int:pk>/action/", assets.asset_action, name="asset_action"),
    path("assets/<int:pk>/delete/", assets.asset_delete, name="asset_delete"),
]

public_urlpatterns = [
    path("<str:token>", public.profile, name="asset_public"),
    path("<str:token>/report", public.report, name="asset_public_report"),
    path("<str:token>/thanks", public.thanks, name="asset_public_thanks"),
]
