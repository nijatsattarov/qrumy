"""Blog posts written by staff in the admin (English and Azerbaijani)."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _
from PIL import Image

from apps.core.utils import generate_token

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP"}


def validate_blog_image(file) -> None:
    if file.size > MAX_IMAGE_BYTES:
        raise ValidationError(_("The image must be 5 MB or smaller."))
    try:
        file.seek(0)
        with Image.open(file) as img:
            fmt = img.format
            img.verify()
    except Exception as exc:  # noqa: BLE001
        raise ValidationError(_("Upload a valid PNG, JPEG or WebP image.")) from exc
    finally:
        file.seek(0)
    if fmt not in ALLOWED_FORMATS:
        raise ValidationError(_("Upload a valid PNG, JPEG or WebP image."))


def blog_upload_to(instance, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "png"
    return f"public/blog/{generate_token(12)}.{ext}"


class PostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(published_at__isnull=False, published_at__lte=timezone.now())


class Post(models.Model):
    language = models.CharField(_("language"), max_length=8, choices=settings.LANGUAGES,
                                default="en")
    title = models.CharField(_("title"), max_length=160)
    slug = models.SlugField(_("URL slug"), max_length=160, allow_unicode=False,
                            help_text=_("Part of the address: /blog/<slug>/"))
    excerpt = models.CharField(_("summary"), max_length=300,
                               help_text=_("Shown in the post list and in search results."))
    body = models.TextField(
        _("text"),
        help_text=_("“## ” heading, “### ” subheading, “- ” list item, **bold**, "
                    "[link text](https://…), ![image description](/media/public/blog/…). "
                    "Blank lines separate paragraphs. HTML is not interpreted."))
    cover = models.ImageField(_("cover image"), upload_to=blog_upload_to, blank=True,
                              validators=[validate_blog_image],
                              help_text=_("Optional. 1200×630 works best for sharing."))
    cover_alt = models.CharField(_("cover description"), max_length=160, blank=True)
    author_name = models.CharField(_("author"), max_length=80, default="Qrumy")
    published_at = models.DateTimeField(_("published at"), null=True, blank=True,
                                        help_text=_("Empty = draft (not shown to anyone). "
                                                    "A future time schedules the post."))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-created_at"]
        verbose_name = _("blog post")
        verbose_name_plural = _("blog posts")
        constraints = [models.UniqueConstraint(fields=["language", "slug"],
                                               name="marketing_post_unique_slug")]

    def __str__(self) -> str:
        return f"{self.title} ({self.language})"

    def get_absolute_url(self) -> str:
        with translation.override(self.language):
            return reverse("blog_post", kwargs={"slug": self.slug})

    @property
    def is_published(self) -> bool:
        return bool(self.published_at and self.published_at <= timezone.now())

    @property
    def reading_minutes(self) -> int:
        return max(1, round(len(self.body.split()) / 200))


class PostImage(models.Model):
    """Images used inside a post's text. Upload, then paste the shown address."""

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(_("image"), upload_to=blog_upload_to,
                              validators=[validate_blog_image])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("image")
        verbose_name_plural = _("images")

    def __str__(self) -> str:
        return self.image.name
