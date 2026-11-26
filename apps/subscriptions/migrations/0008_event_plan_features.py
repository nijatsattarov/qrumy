"""Event Lead Capture limits. module.events already exists in the plans."""

from django.db import migrations

EVENT_LIMITS = {"beta": 20, "starter": 2, "growth": 10, "business": 50, "agency": 250}


def seed(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    PlanFeature = apps.get_model("subscriptions", "PlanFeature")
    for key, limit in EVENT_LIMITS.items():
        plan = Plan.objects.filter(key=key).first()
        if plan:
            PlanFeature.objects.get_or_create(plan=plan, feature_key="events.max",
                                              defaults={"enabled": True, "limit_value": limit})


def unseed(apps, schema_editor):
    apps.get_model("subscriptions", "PlanFeature").objects.filter(
        feature_key="events.max").delete()


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0007_menu_plan_features")]
    operations = [migrations.RunPython(seed, unseed)]
