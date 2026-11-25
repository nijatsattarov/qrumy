"""Dashboard widget registry: product apps contribute cards to the overview page."""

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Widget:
    key: str
    template: str
    context: Callable[[object], dict]
    order: int = 100
    visible: Callable[[object], bool] = field(default=lambda request: True)


_widgets: dict[str, Widget] = {}


def register(widget: Widget) -> None:
    _widgets[widget.key] = widget


def for_request(request) -> list[dict]:
    out = []
    for w in sorted(_widgets.values(), key=lambda w: w.order):
        if w.visible(request):
            out.append({"key": w.key, "template": w.template, **w.context(request)})
    return out
