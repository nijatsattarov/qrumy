from django.urls import path

from . import public
from .views import responses, results, surveys

app_urlpatterns = [
    path("surveys/", surveys.survey_list, name="survey_list"),
    path("surveys/new/", surveys.survey_create, name="survey_create"),
    path("surveys/<int:pk>/", surveys.survey_builder, name="survey_builder"),
    path("surveys/<int:pk>/questions/add/", surveys.question_add, name="survey_question_add"),
    path("surveys/<int:pk>/questions/<int:qid>/", surveys.question_update,
         name="survey_question_update"),
    path("surveys/<int:pk>/questions/<int:qid>/move/", surveys.question_move,
         name="survey_question_move"),
    path("surveys/<int:pk>/questions/<int:qid>/delete/", surveys.question_delete,
         name="survey_question_delete"),
    path("surveys/<int:pk>/settings/", surveys.survey_settings, name="survey_settings"),
    path("surveys/<int:pk>/status/", surveys.survey_status, name="survey_status"),
    path("surveys/<int:pk>/delete/", surveys.survey_delete, name="survey_delete"),
    path("surveys/<int:pk>/share/", surveys.survey_share, name="survey_share"),
    path("surveys/<int:pk>/share/qr/", surveys.survey_create_qr, name="survey_create_qr"),
    path("surveys/<int:pk>/preview/", public.survey_preview, name="survey_preview"),
    path("surveys/<int:pk>/results/", results.survey_results, name="survey_results"),
    path("surveys/<int:pk>/responses/", responses.response_list, name="survey_responses"),
    path("surveys/<int:pk>/responses/export.csv", responses.response_export,
         name="survey_responses_export"),
    path("surveys/<int:pk>/responses/<int:rid>/", responses.response_detail,
         name="survey_response"),
    path("surveys/<int:pk>/responses/<int:rid>/action/", responses.response_action,
         name="survey_response_action"),
]

public_urlpatterns = [
    path("<str:token>", public.survey_page, name="survey_public"),
    path("<str:token>/embed", public.survey_embed, name="survey_embed"),
    path("<str:token>/theme.css", public.survey_theme, name="survey_theme"),
]
