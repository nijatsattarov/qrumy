from functools import wraps

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import Http404

from apps.core import quotas

from .capabilities import has_capability


def require_capability(capability: str):
    """Function-view decorator; OrganizationMiddleware has already verified membership."""

    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not has_capability(getattr(request, "membership", None), capability):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        wrapper.required_capability = capability
        return wrapper

    return decorator


def can(request, capability: str) -> bool:
    return has_capability(getattr(request, "membership", None), capability)


def module_enabled(request, module: str) -> bool:
    """A product module is usable when released and included in the org's plan."""
    org = getattr(request, "organization", None)
    return (org is not None and module in settings.QRUMY_AVAILABLE_MODULES
            and quotas.is_enabled(org, f"module.{module}"))


def require_module(module: str):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not module_enabled(request, module):
                raise Http404
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
