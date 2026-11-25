"""Asset Management plan features (Phase 6). Editable in the admin."""

from django.db import migrations

ASSET_LIMITS = {"beta": 500, "starter": 100, "growth": 500, "business": 2500, "agency": 10000}


def seed(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    PlanFeature = apps.get_model("subscriptions", "PlanFeature")
    for key, limit in ASSET_LIMITS.items():
        plan = Plan.objects.filter(key=key).first()
        if plan:
            PlanFeature.objects.get_or_create(plan=plan, feature_key="assets.max",
                                              defaults={"enabled": True, "limit_value": limit})


def unseed(apps, schema_editor):
    apps.get_model("subscriptions", "PlanFeature").objects.filter(
        feature_key="assets.max").delete()


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0004_survey_plan_features")]
    operations = [migrations.RunPython(seed, unseed)]
