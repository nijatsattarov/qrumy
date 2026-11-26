"""Qrumy Card plan features. Editable in the admin."""

from django.db import migrations

CARD_LIMITS = {"beta": 25, "starter": 3, "growth": 15, "business": 50, "agency": 250}


def seed(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    PlanFeature = apps.get_model("subscriptions", "PlanFeature")
    for plan in Plan.objects.all():
        PlanFeature.objects.get_or_create(plan=plan, feature_key="module.cards",
                                          defaults={"enabled": True})
        if plan.key in CARD_LIMITS:
            PlanFeature.objects.get_or_create(
                plan=plan, feature_key="cards.max",
                defaults={"enabled": True, "limit_value": CARD_LIMITS[plan.key]})


def unseed(apps, schema_editor):
    apps.get_model("subscriptions", "PlanFeature").objects.filter(
        feature_key__in=["module.cards", "cards.max"]).delete()


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0005_asset_plan_features")]
    operations = [migrations.RunPython(seed, unseed)]
