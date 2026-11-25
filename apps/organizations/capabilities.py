"""Capability matrix: what each organization role may do.

Product apps add their own capabilities here when they are built (e.g. "qr.create").
Checks are always server-side (decorators/mixins in permissions.py).
"""

from .roles import Role

OWN, ADM, MGR, MEM, VIEW = Role.OWNER, Role.ADMIN, Role.MANAGER, Role.MEMBER, Role.VIEWER
ALL = {OWN, ADM, MGR, MEM, VIEW}

CAPABILITIES: dict[str, set[Role]] = {
    "org.view": ALL,
    "org.settings.edit": {OWN, ADM},
    "team.view": ALL,
    "team.invite": {OWN, ADM},
    "team.manage": {OWN, ADM},
    "billing.view": {OWN, ADM},
    "billing.manage": {OWN},
    "audit.view": {OWN, ADM},
    # Generic content capabilities used by product modules
    "content.view": ALL,
    "content.create": {OWN, ADM, MGR, MEM},
    "content.edit": {OWN, ADM, MGR, MEM},
    "content.delete": {OWN, ADM, MGR},
    "analytics.view": ALL,
}


def has_capability(membership, capability: str) -> bool:
    if membership is None:
        return False
    allowed = CAPABILITIES.get(capability)
    if allowed is None:
        raise KeyError(f"Unknown capability: {capability}")
    return Role(membership.role) in allowed
