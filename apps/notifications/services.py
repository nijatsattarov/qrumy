from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone, translation

from .models import Notification
from .tasks import send_email_task


def notify(user, *, kind: str, title: str, body: str = "", url: str = "",
           organization=None) -> Notification:
    return Notification.objects.create(user=user, kind=kind, title=title, body=body, url=url,
                                       organization=organization)


def unread_count(user) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).count()


def mark_all_read(user) -> int:
    return Notification.objects.filter(user=user, read_at__isnull=True).update(
        read_at=timezone.now())


def send_templated_email(*, to: str, template: str, context: dict,
                         language: str | None = None) -> None:
    """Render ``<template>_subject.txt`` / ``.txt`` / ``.html`` in the recipient's language
    and send asynchronously via Celery."""
    language = language or settings.LANGUAGE_CODE
    ctx = {"SITE_URL": settings.SITE_URL, **context}
    with translation.override(language):
        subject = render_to_string(f"{template}_subject.txt", ctx).strip().replace("\n", " ")
        text = render_to_string(f"{template}.txt", ctx)
        html = render_to_string(f"{template}.html", ctx)
    send_email_task.delay(to=to, subject=subject, text=text, html=html)
