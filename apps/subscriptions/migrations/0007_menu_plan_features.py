"""Digital Menu plan features. Editable in the admin."""

from django.db import migrations

MENU_LIMITS = {"beta": 10, "starter": 1, "growth": 5, "business": 20, "agency": 100}


def seed(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    PlanFeature = apps.get_model("subscriptions", "PlanFeature")
    for plan in Plan.objects.all():
        PlanFeature.objects.get_or_create(plan=plan, feature_key="module.menus",
                                          defaults={"enabled": True})
        if plan.key in MENU_LIMITS:
            PlanFeature.objects.get_or_create(
                plan=plan, feature_key="menus.max",
                defaults={"enabled": True, "limit_value": MENU_LIMITS[plan.key]})


def unseed(apps, schema_editor):
    apps.get_model("subscriptions", "PlanFeature").objects.filter(
        feature_key__in=["module.menus", "menus.max"]).delete()


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0006_card_plan_features")]
    operations = [migrations.RunPython(seed, unseed)]
