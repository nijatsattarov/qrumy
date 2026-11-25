"""Initial plans. Prices are the spec's starting hypotheses; edit them in the admin."""

from django.db import migrations

MODULES = ["module.qr", "module.surveys", "module.events", "module.assets", "module.ai",
           "module.agency"]

PLANS = [
    # key, name, monthly cents, yearly cents, public, beta, order, team limit, modules, extra
    ("beta", "Beta", 0, 0, True, True, 0, 10,
     ["module.qr", "module.surveys", "module.events", "module.assets"], []),
    ("free", "Free", 0, 0, True, False, 10, 2, ["module.qr", "module.surveys"], []),
    ("starter", "Starter", 1900, 19000, True, False, 20, 3,
     ["module.qr", "module.surveys", "module.events", "module.assets"], []),
    ("growth", "Growth", 4900, 49000, True, False, 30, 10,
     ["module.qr", "module.surveys", "module.events", "module.assets"], ["branding.remove"]),
    ("business", "Business", 9900, 99000, True, False, 40, 25,
     ["module.qr", "module.surveys", "module.events", "module.assets", "module.ai"],
     ["branding.remove"]),
    ("agency", "Agency", 14900, 149000, True, False, 50, 50, MODULES, ["branding.remove"]),
]

DESCRIPTIONS = {
    "beta": "Everything available today, free while Qrumy is in beta.",
    "free": "Get started with QR codes and simple surveys.",
    "starter": "For small businesses running their first campaigns.",
    "growth": "Dynamic QR, events and assets for growing teams.",
    "business": "Higher limits, AI insights and advanced permissions.",
    "agency": "Manage multiple clients from one workspace.",
}


def seed(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    PlanFeature = apps.get_model("subscriptions", "PlanFeature")
    for key, name, monthly, yearly, public, beta, order, team, modules, extra in PLANS:
        plan, _ = Plan.objects.get_or_create(key=key, defaults={
            "name": name, "description": DESCRIPTIONS[key], "price_monthly_cents": monthly,
            "price_yearly_cents": yearly, "is_public": public, "is_beta": beta,
            "sort_order": order,
        })
        PlanFeature.objects.get_or_create(plan=plan, feature_key="team.members",
                                          defaults={"enabled": True, "limit_value": team})
        for feature in modules + extra:
            PlanFeature.objects.get_or_create(plan=plan, feature_key=feature,
                                              defaults={"enabled": True})


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0001_initial")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
