"""Navigation registry: each app registers its own sidebar items.

Items are filtered per request by a ``visible(request)`` callable supplied by the
registering app (capability + module checks live there, not in core).
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from django.urls import reverse


@dataclass(frozen=True)
class NavItem:
    key: str
    label: object  # lazy translation string
    url_name: str
    icon: str
    order: int = 100
    section: str = "main"  # "main" | "workspace"
    visible: Callable[[object], bool] = field(default=lambda request: True)


_items: dict[str, NavItem] = {}


def register(item: NavItem) -> None:
    _items[item.key] = item


def items_for(request) -> list[dict]:
    org = getattr(request, "organization", None)
    if org is None:
        return []
    current = getattr(getattr(request, "resolver_match", None), "url_name", None)
    result = []
    for item in sorted(_items.values(), key=lambda i: i.order):
        if not item.visible(request):
            continue
        result.append({
            "key": item.key,
            "label": item.label,
            "icon": item.icon,
            "section": item.section,
            "url": reverse(item.url_name, kwargs={"org_slug": org.slug}),
            "active": current == item.url_name or (current or "").startswith(item.key + "_"),
        })
    return result
