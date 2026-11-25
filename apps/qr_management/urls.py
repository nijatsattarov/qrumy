from django.urls import path

from . import public
from .views import analytics, bulk, codes, folders

app_urlpatterns = [
    path("qr/", codes.qr_list, name="qr_list"),
    path("qr/new/", codes.qr_choose_type, name="qr_choose_type"),
    path("qr/new/<slug:type_key>/", codes.qr_create, name="qr_create"),
    path("qr/preview/", codes.qr_preview, name="qr_preview"),
    path("qr/bulk/", bulk.bulk_create, name="qr_bulk"),
    path("qr/bulk/template.csv", bulk.bulk_template, name="qr_bulk_template"),
    path("qr/actions/", codes.qr_bulk_action, name="qr_bulk_action"),
    path("qr/folders/new/", folders.folder_create, name="qr_folder_create"),
    path("qr/folders/<int:folder_id>/rename/", folders.folder_rename, name="qr_folder_rename"),
    path("qr/folders/<int:folder_id>/delete/", folders.folder_delete, name="qr_folder_delete"),
    path("qr/<int:pk>/", codes.qr_detail, name="qr_detail"),
    path("qr/<int:pk>/edit/", codes.qr_edit, name="qr_edit"),
    path("qr/<int:pk>/status/", codes.qr_set_status, name="qr_set_status"),
    path("qr/<int:pk>/delete/", codes.qr_delete, name="qr_delete"),
    path("qr/<int:pk>/download/<str:fmt>/", codes.qr_download, name="qr_download"),
    path("qr/<int:pk>/landing-preview/", public.preview_landing, name="qr_landing_preview"),
    path("qr/<int:pk>/analytics.csv", analytics.analytics_export, name="qr_analytics_export"),
    path("analytics/", analytics.analytics_overview, name="analytics_overview"),
    path("analytics/export.csv", analytics.analytics_export, name="analytics_export"),
]

public_urlpatterns = [
    path("<str:code>", public.scan, name="qr_scan"),
    path("<str:code>/contact.vcf", public.vcard_download, name="qr_vcard"),
]
