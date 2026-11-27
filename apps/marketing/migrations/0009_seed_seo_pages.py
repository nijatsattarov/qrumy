"""Create the (empty) SEO rows that admins edit: one per public page and language.

Empty fields keep the built-in texts, so this changes nothing on the site by itself.
"""

from django.db import migrations

PAGES = ["home", "pricing", "blog", "contact", "terms", "privacy"]
TOOLS = ["qr-code-generator", "url-qr-code-generator", "wifi-qr-code-generator",
         "email-qr-code-generator", "phone-qr-code-generator", "whatsapp-qr-code-generator",
         "sms-qr-code-generator", "vcard-qr-code-generator", "location-qr-code-generator",
         "text-qr-code-generator"]


def seed(apps, schema_editor):
    SeoPage = apps.get_model("marketing", "SeoPage")
    SeoSettings = apps.get_model("marketing", "SeoSettings")
    for page in PAGES + [f"tool:{t}" for t in TOOLS]:
        for lang in ("en", "az"):
            SeoPage.objects.get_or_create(page=page, language=lang)
    if not SeoSettings.objects.exists():
        SeoSettings.objects.create()


class Migration(migrations.Migration):
    dependencies = [("marketing", "0008_blog_seo_fields")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
