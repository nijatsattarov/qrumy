"""Surveys plan features (Phase 3). Values are editable in the admin."""

from django.db import migrations

# plan: (surveys, responses per month)
SURVEY_FEATURES = {
    "beta": (25, 2000),
    "free": (3, 100),
    "starter": (10, 1000),
    "growth": (50, 5000),
    "business": (200, 25000),
    "agency": (1000, 100000),
}


def seed(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    PlanFeature = apps.get_model("subscriptions", "PlanFeature")
    for key, (surveys, responses) in SURVEY_FEATURES.items():
        plan = Plan.objects.filter(key=key).first()
        if plan is None:
            continue
        PlanFeature.objects.get_or_create(plan=plan, feature_key="surveys.max",
                                          defaults={"enabled": True, "limit_value": surveys})
        PlanFeature.objects.get_or_create(plan=plan, feature_key="surveys.responses_month",
                                          defaults={"enabled": True, "limit_value": responses})


def unseed(apps, schema_editor):
    apps.get_model("subscriptions", "PlanFeature").objects.filter(
        feature_key__in=["surveys.max", "surveys.responses_month"]).delete()


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0003_qr_plan_features")]
    operations = [migrations.RunPython(seed, unseed)]
