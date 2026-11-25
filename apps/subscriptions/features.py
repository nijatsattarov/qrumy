"""Registry of plan feature keys.

``bool`` features are on/off; ``limit`` features carry a number (None = unlimited).
Product apps add their keys here in the phase that implements them.
"""

from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class Feature:
    key: str
    kind: str  # "bool" | "limit"
    label: object


FEATURES = {f.key: f for f in [
    Feature("team.members", "limit", _("Team members")),
    Feature("module.qr", "bool", _("QR Management")),
    Feature("module.surveys", "bool", _("Surveys & Feedback")),
    Feature("module.events", "bool", _("Event Lead Capture")),
    Feature("module.assets", "bool", _("Asset Management")),
    Feature("module.ai", "bool", _("Qrumy Intelligence")),
    Feature("module.agency", "bool", _("Agency workspace")),
    Feature("branding.remove", "bool", _("Remove Qrumy branding")),
]}
