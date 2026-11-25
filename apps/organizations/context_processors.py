from .capabilities import CAPABILITIES, has_capability
from .models import Membership


class _Can:
    """Template helper: ``{% if can.team_invite %}`` → capability "team.invite"."""

    def __init__(self, membership):
        self.membership = membership

    def __getattr__(self, name):
        for cap in (name.replace("_", ".", 1), name.replace("_", ".")):
            if cap in CAPABILITIES:
                return has_capability(self.membership, cap)
        return False


def organizations(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    ctx = {"can": _Can(getattr(request, "membership", None))}
    if getattr(request, "organization", None) is not None:
        ctx["user_memberships"] = (Membership.objects.filter(user=user)
                                   .select_related("organization")
                                   .order_by("organization__name"))
    return ctx
