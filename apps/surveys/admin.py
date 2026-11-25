from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Question, Response, Survey


class QuestionInline(TabularInline):
    model = Question
    extra = 0
    fields = ("position", "qtype", "label", "required")
    readonly_fields = fields


@admin.register(Survey)
class SurveyAdmin(ModelAdmin):
    list_display = ("title", "organization", "status", "response_count", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "organization__name", "public_token")
    list_select_related = ("organization",)
    readonly_fields = ("public_token", "response_count", "published_at", "created_by")
    inlines = [QuestionInline]


@admin.register(Response)
class ResponseAdmin(ModelAdmin):
    list_display = ("survey", "organization", "submitted_at", "source", "status", "nps")
    list_filter = ("status", "source")
    search_fields = ("survey__title", "organization__name")
    list_select_related = ("survey", "organization")
    readonly_fields = [f.name for f in Response._meta.fields]

    def has_add_permission(self, request):
        return False
