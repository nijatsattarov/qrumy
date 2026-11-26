from apps.core.widgets import Widget
from apps.core.widgets import register as register_widget
from apps.organizations.permissions import can, module_enabled

from .models import Card


def _context(request):
    cards = Card.objects.for_org(request.organization)
    return {"card_count": cards.count(), "cards_latest": cards[:3]}


def register() -> None:
    register_widget(Widget("cards", "cards/widgets/overview.html", _context, order=25,
                           visible=lambda r: module_enabled(r, "cards")
                           and can(r, "content.view")))
