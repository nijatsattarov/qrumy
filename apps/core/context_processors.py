from django.conf import settings

from . import navigation


def _legal_links() -> dict:
    from django.core.cache import cache

    links = cache.get("qrumy:legal-links")
    if links is None:
        from django.apps import apps
        from django.utils import timezone

        Doc = apps.get_model("accounts", "LegalDocument")  # noqa: N806 — core can't import accounts
        kinds = set(Doc.objects.filter(published_at__lte=timezone.now())
                    .values_list("kind", flat=True))
        links = {"terms": "terms" in kinds, "privacy": "privacy" in kinds}
        cache.set("qrumy:legal-links", links, 300)
    return links


def qrumy(request):
    return {
        "LEGAL": _legal_links(),
        "SITE_URL": settings.SITE_URL,
        "QRUMY_AVAILABLE_MODULES": settings.QRUMY_AVAILABLE_MODULES,
        "nav_items": navigation.items_for(request),
        "current_organization": getattr(request, "organization", None),
        "current_membership": getattr(request, "membership", None),
    }
