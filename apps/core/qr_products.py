"""Product shortcuts shown at the top of the QR type picker (e.g. Digital Menu).

Higher-level modules register tiles here so the QR app does not import them.
"""

from collections.abc import Callable
from dataclasses import dataclass

from django.urls import reverse


@dataclass(frozen=True)
class ProductTile:
    key: str
    label: object
    description: object
    icon: str
    url_name: str  # takes org_slug
    visible: Callable = lambda request: True
    order: int = 0


_TILES: dict[str, ProductTile] = {}


def register(tile: ProductTile) -> None:
    _TILES[tile.key] = tile


def tiles_for(request) -> list[dict]:
    org = getattr(request, "organization", None)
    if org is None:
        return []
    out = []
    for t in sorted(_TILES.values(), key=lambda t: t.order):
        if t.visible(request):
            out.append({"label": t.label, "description": t.description, "icon": t.icon,
                        "url": reverse(t.url_name, kwargs={"org_slug": org.slug})})
    return out
