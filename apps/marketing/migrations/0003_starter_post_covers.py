"""Give the starter posts a branded cover image (only if they have none yet)."""

from django.core.files.base import ContentFile
from django.db import migrations

STARTER_SLUGS = ["qr-feedback", "static-vs-dynamic", "qr-kod-ile-musteri-reyi",
                 "statik-ve-dinamik-qr-kod"]


def add_covers(apps, schema_editor):
    from apps.core.utils import generate_token
    from apps.marketing.covers import make_cover

    Post = apps.get_model("marketing", "Post")
    for post in Post.objects.filter(slug__in=STARTER_SLUGS, cover=""):
        post.cover.save(f"public/blog/{generate_token(12)}.jpg",
                        ContentFile(make_cover(post.title, "Qrumy blog")), save=False)
        post.cover_alt = post.title
        post.save(update_fields=["cover", "cover_alt"])


class Migration(migrations.Migration):
    dependencies = [("marketing", "0002_seed_blog_posts")]
    operations = [migrations.RunPython(add_covers, migrations.RunPython.noop)]
