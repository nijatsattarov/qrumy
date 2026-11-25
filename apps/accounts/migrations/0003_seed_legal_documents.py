"""Publish the first Terms of Service and Privacy Policy (en + az).

Only creates a document when none of that kind and language exists yet, so it never
overwrites texts edited in the admin. Later changes are made in the admin
(Accounts → Legal documents) by adding a new version.
"""

from pathlib import Path

from django.db import migrations
from django.utils import timezone

TEXTS = Path(__file__).resolve().parent.parent / "legal_texts"
VERSION = "2026-11-25"
TITLES = {
    ("terms", "en"): "Terms of Service",
    ("terms", "az"): "İstifadə Şərtləri",
    ("privacy", "en"): "Privacy Policy",
    ("privacy", "az"): "Məxfilik Siyasəti",
}


def seed(apps, schema_editor):
    LegalDocument = apps.get_model("accounts", "LegalDocument")
    now = timezone.now()
    for (kind, language), title in TITLES.items():
        if LegalDocument.objects.filter(kind=kind, language=language).exists():
            continue
        body = (TEXTS / f"{kind}_{language}.txt").read_text(encoding="utf-8").strip()
        LegalDocument.objects.create(kind=kind, language=language, version=VERSION,
                                     title=title, body=body, published_at=now)


def unseed(apps, schema_editor):
    LegalDocument = apps.get_model("accounts", "LegalDocument")
    LegalDocument.objects.filter(version=VERSION, title__in=TITLES.values()).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_legaldocument_termsacceptance")]
    operations = [migrations.RunPython(seed, unseed)]
