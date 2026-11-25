"""Marks seeded plan texts for translation (makemessages cannot read the database)."""

from django.utils.translation import gettext_noop

PLAN_STRINGS = [
    gettext_noop("Everything available today, free while Qrumy is in beta."),
    gettext_noop("Get started with QR codes and simple surveys."),
    gettext_noop("For small businesses running their first campaigns."),
    gettext_noop("Dynamic QR, events and assets for growing teams."),
    gettext_noop("Higher limits, AI insights and advanced permissions."),
    gettext_noop("Manage multiple clients from one workspace."),
]
