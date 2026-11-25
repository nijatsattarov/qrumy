from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    OWNER = "owner", _("Owner")
    ADMIN = "admin", _("Admin")
    MANAGER = "manager", _("Manager")
    MEMBER = "member", _("Member")
    VIEWER = "viewer", _("Viewer")


RANK = {Role.OWNER: 50, Role.ADMIN: 40, Role.MANAGER: 30, Role.MEMBER: 20, Role.VIEWER: 10}

ROLE_DESCRIPTIONS = {
    Role.OWNER: _("Full control, including billing and the organization itself."),
    Role.ADMIN: _("Manage settings, team and all content."),
    Role.MANAGER: _("Create, edit and delete content; view analytics."),
    Role.MEMBER: _("Create and edit content."),
    Role.VIEWER: _("Read-only access."),
}


def rank(role: str) -> int:
    return RANK.get(Role(role), 0)


def assignable_roles(actor_role: str) -> list[Role]:
    """Roles an actor may grant: strictly below their own. Ownership is never granted."""
    return [r for r in Role if r != Role.OWNER and rank(r) < rank(actor_role)]
