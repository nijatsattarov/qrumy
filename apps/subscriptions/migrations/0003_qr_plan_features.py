"""QR Management plan features (Phase 2). Values are editable in the admin."""

from django.db import migrations

# plan: (dynamic QR limit, bulk creation, max file size MB)
QR_FEATURES = {
    "beta": (100, True, 10),
    "free": (5, False, 5),
    "starter": (50, True, 10),
    "growth": (250, True, 20),
    "business": (1000, True, 25),
    "agency": (5000, True, 25),
}


def seed(apps, schema_editor):
    Plan = apps.get_model("subscriptions", "Plan")
    PlanFeature = apps.get_model("subscriptions", "PlanFeature")
    for key, (dynamic, bulk, file_mb) in QR_FEATURES.items():
        plan = Plan.objects.filter(key=key).first()
        if plan is None:
            continue
        PlanFeature.objects.get_or_create(plan=plan, feature_key="qr.dynamic",
                                          defaults={"enabled": True, "limit_value": dynamic})
        PlanFeature.objects.get_or_create(plan=plan, feature_key="qr.bulk",
                                          defaults={"enabled": bulk})
        PlanFeature.objects.get_or_create(plan=plan, feature_key="qr.file_mb",
                                          defaults={"enabled": True, "limit_value": file_mb})


def unseed(apps, schema_editor):
    PlanFeature = apps.get_model("subscriptions", "PlanFeature")
    PlanFeature.objects.filter(feature_key__in=["qr.dynamic", "qr.bulk", "qr.file_mb"]).delete()


class Migration(migrations.Migration):
    dependencies = [("subscriptions", "0002_seed_plans")]
    operations = [migrations.RunPython(seed, unseed)]
