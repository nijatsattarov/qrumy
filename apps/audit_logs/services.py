from apps.core.utils import client_ip, hash_ip

from .models import AuditLog


def record(action: str, *, actor=None, organization=None, target=None, changes=None,
           request=None) -> AuditLog:
    """Write one audit entry. Never store secrets or raw personal data in ``changes``."""
    entry = AuditLog(action=action, organization=organization, changes=changes or {})
    if actor is not None and getattr(actor, "is_authenticated", False):
        entry.actor = actor
        entry.actor_email = actor.email
        entry.is_staff_action = bool(actor.is_staff) and action.startswith("admin.")
    if target is not None:
        entry.target_type = target._meta.label_lower
        entry.target_id = str(target.pk)
        entry.target_repr = str(target)[:255]
    if request is not None:
        entry.ip_hash = hash_ip(client_ip(request))
        entry.user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]
    entry.save()
    return entry
