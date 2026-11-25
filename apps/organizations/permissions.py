from functools import wraps

from django.core.exceptions import PermissionDenied

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
