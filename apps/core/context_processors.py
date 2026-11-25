from django.conf import settings

from . import navigation


def qrumy(request):
    return {
        "SITE_URL": settings.SITE_URL,
        "QRUMY_AVAILABLE_MODULES": settings.QRUMY_AVAILABLE_MODULES,
        "nav_items": navigation.items_for(request),
        "current_organization": getattr(request, "organization", None),
        "current_membership": getattr(request, "membership", None),
    }
