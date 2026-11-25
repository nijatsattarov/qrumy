"""First blog posts (en + az). Only adds a post if its slug is not taken in that language,
so it never touches posts edited in the admin."""

from datetime import timedelta
from pathlib import Path

from django.db import migrations
from django.utils import timezone

TEXTS = Path(__file__).resolve().parent.parent / "blog_seed"
POSTS = [
    ("qr-feedback", 0, {
        "en": ("How to collect customer feedback with a QR code",
               "Place a short survey where your customers already are and hear about "
               "problems before they turn into bad reviews."),
        "az": ("QR kod ilə müştəri rəyini necə toplamalı",
               "Qısa sorğunu müştərilərinizin olduğu yerə qoyun və problemləri pis rəyə "
               "çevrilməzdən əvvəl öyrənin."),
    }),
    ("static-vs-dynamic", 1, {
        "en": ("Static vs dynamic QR codes: which one should you use?",
               "Both look the same, but only one can be changed after printing and tell "
               "you how many people scanned it."),
        "az": ("Statik və dinamik QR kod: hansını seçməli?",
               "Hər ikisi eyni görünür, amma yalnız birini çapdan sonra dəyişmək və neçə "
               "nəfərin skan etdiyini görmək olur."),
    }),
]
SLUGS = {"az": {"qr-feedback": "qr-kod-ile-musteri-reyi",
                "static-vs-dynamic": "statik-ve-dinamik-qr-kod"}}


def seed(apps, schema_editor):
    Post = apps.get_model("marketing", "Post")
    now = timezone.now()
    for key, age_days, langs in POSTS:
        for lang, (title, excerpt) in langs.items():
            slug = SLUGS.get(lang, {}).get(key, key)
            if Post.objects.filter(language=lang, slug=slug).exists():
                continue
            body = (TEXTS / f"{key}_{lang}.txt").read_text(encoding="utf-8").strip()
            Post.objects.create(language=lang, slug=slug, title=title, excerpt=excerpt,
                                body=body, published_at=now - timedelta(days=age_days))


def unseed(apps, schema_editor):
    Post = apps.get_model("marketing", "Post")
    for key, _age, _langs in POSTS:
        Post.objects.filter(slug__in=[key, *(s.get(key, "") for s in SLUGS.values())],
                            images__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [("marketing", "0001_blog")]
    operations = [migrations.RunPython(seed, unseed)]
