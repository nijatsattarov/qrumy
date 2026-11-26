"""Azerbaijani-friendly admin labels for third-party apps that ship no translation."""

import contextlib

from django.apps import apps
from django.utils.translation import gettext_lazy as _

APP_LABELS = {
    "django_celery_beat": _("Scheduled tasks"),
    "mfa": _("Two-factor authentication"),
}
MODEL_LABELS = {
    ("django_celery_beat", "periodictask"): (_("scheduled task"), _("scheduled tasks")),
    ("django_celery_beat", "intervalschedule"): (_("interval"), _("intervals")),
    ("django_celery_beat", "crontabschedule"): (_("crontab schedule"), _("crontab schedules")),
    ("django_celery_beat", "solarschedule"): (_("solar event"), _("solar events")),
    ("django_celery_beat", "clockedschedule"): (_("one-time schedule"), _("one-time schedules")),
    ("django_celery_beat", "periodictasks"): (_("task change tracking"),
                                              _("task change tracking")),
    ("mfa", "authenticator"): (_("authenticator"), _("authenticators")),
}


def apply() -> None:
    for label, name in APP_LABELS.items():
        with contextlib.suppress(LookupError):
            apps.get_app_config(label).verbose_name = name
    for (app_label, model), (single, plural) in MODEL_LABELS.items():
        try:
            meta = apps.get_model(app_label, model)._meta
        except LookupError:
            continue
        meta.verbose_name, meta.verbose_name_plural = single, plural
