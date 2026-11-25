from django.shortcuts import render

from apps.organizations.permissions import require_capability
from apps.organizations.services import team_usage
from apps.subscriptions.entitlements import get_entitlements
from apps.subscriptions.features import FEATURES
from apps.subscriptions.models import Plan


@require_capability("billing.view")
def billing(request, org_slug):
    org = request.organization
    ent = get_entitlements(org)
    usage = {"team.members": team_usage(org)}
    limits = []
    for key, feature in FEATURES.items():
        if feature.kind != "limit":
            continue
        limit = ent.limit(key)
        used = usage.get(key)
        pct = min(100, int(used * 100 / limit)) if limit and used is not None else None
        limits.append({"label": feature.label, "limit": limit, "used": used, "pct": pct})
    modules = [{"label": f.label, "enabled": ent.can(k)}
               for k, f in FEATURES.items() if k.startswith("module.")]
    plans = Plan.objects.filter(is_public=True, is_active=True, is_beta=False)
    return render(request, "billing/billing.html", {
        "entitlements": ent, "subscription": ent.subscription, "limits": limits,
        "modules": modules, "plans": plans,
    })
