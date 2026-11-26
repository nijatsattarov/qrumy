"""Starter content for the contact page (en + az). Edit it in the admin."""

from django.db import migrations

PAGES = {
    "en": {"title": "Contact us",
           "intro": "Questions about Qrumy, plans or a partnership? Write to us — we usually "
                    "answer within one business day.",
           "hours": "Mon–Fri 09:00–18:00 (Baku time)"},
    "az": {"title": "Bizimlə əlaqə",
           "intro": "Qrumy, planlar və ya əməkdaşlıqla bağlı sualınız var? Bizə yazın — "
                    "adətən bir iş günü ərzində cavab veririk.",
           "hours": "B.e.–Cümə 09:00–18:00 (Bakı vaxtı)"},
}


def seed(apps, schema_editor):
    ContactPage = apps.get_model("marketing", "ContactPage")
    for lang, data in PAGES.items():
        ContactPage.objects.get_or_create(language=lang, defaults={
            **data, "email": "support@qrumy.com", "address": "Bakı, Azərbaycan",
            "form_enabled": True, "notify_email": "support@qrumy.com"})


class Migration(migrations.Migration):
    dependencies = [("marketing", "0005_contact")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
