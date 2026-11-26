from django.urls import path

from .views import manage, public

app_urlpatterns = [
    path("menus/", manage.menu_list, name="menu_list"),
    path("menus/new/", manage.menu_create, name="menu_create"),
    path("menus/<int:pk>/", manage.menu_builder, name="menu_builder"),
    path("menus/<int:pk>/settings/", manage.menu_settings, name="menu_settings"),
    path("menus/<int:pk>/share/", manage.menu_share, name="menu_share"),
    path("menus/<int:pk>/publish/", manage.menu_publish, name="menu_publish"),
    path("menus/<int:pk>/delete/", manage.menu_delete, name="menu_delete"),
    path("menus/<int:pk>/preview/", manage.menu_preview, name="menu_preview"),
    path("menus/<int:pk>/categories/new/", manage.category_save, name="menu_category_create"),
    path("menus/<int:pk>/categories/<int:cat_id>/", manage.category_save,
         name="menu_category_update"),
    path("menus/<int:pk>/categories/<int:cat_id>/move/", manage.category_move,
         name="menu_category_move"),
    path("menus/<int:pk>/categories/<int:cat_id>/delete/", manage.category_delete,
         name="menu_category_delete"),
    path("menus/<int:pk>/items/new/", manage.item_edit, name="menu_item_create"),
    path("menus/<int:pk>/items/<int:item_id>/", manage.item_edit, name="menu_item_edit"),
    path("menus/<int:pk>/items/<int:item_id>/action/", manage.item_action,
         name="menu_item_action"),
]

public_urlpatterns = [
    path("<str:token>", public.menu_page, name="menu_public"),
    path("<str:token>/e", public.menu_event, name="menu_event"),
    path("<str:token>/theme.css", public.menu_theme, name="menu_theme"),
]
