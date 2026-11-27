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
    seo_title = models.CharField(_("SEO title"), max_length=90, blank=True,
                                 help_text=_("Optional, 50–60 characters. Empty: the title."))
    meta_description = models.CharField(
        _("meta description"), max_length=200, blank=True,
        help_text=_("Optional, 120–160 characters. Empty: the summary."))
    keywords = models.CharField(_("keywords"), max_length=255, blank=True,
                                help_text=_("Optional, comma-separated."))
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


class PromoQuerySet(models.QuerySet):
    def live(self):
        now = timezone.now()
        return (self.filter(is_active=True)
                .filter(models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now))
                .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now)))


class Promo(models.Model):
    """A pop-up offer (e.g. a discount) shown on the website, managed in the admin."""

    class Placement(models.TextChoices):
        HOME = "home", _("Home page only")
        PUBLIC = "public", _("All public pages (home, pricing, blog)")
        APP = "app", _("Customer dashboard")
        EVERYWHERE = "everywhere", _("Public pages and dashboard")

    class Audience(models.TextChoices):
        ALL = "all", _("Everyone")
        GUESTS = "guests", _("Visitors who are not signed in")
        USERS = "users", _("Signed-in customers")

    class Frequency(models.TextChoices):
        ONCE = "once", _("Once (until the visitor closes it)")
        DAILY = "daily", _("At most once a day")
        SESSION = "session", _("Once per visit")

    name = models.CharField(_("internal name"), max_length=80,
                            help_text=_("Only visible in the admin."))
    is_active = models.BooleanField(_("active"), default=True)
    language = models.CharField(_("language"), max_length=8, blank=True,
                                choices=[("", _("All languages")), *settings.LANGUAGES])
    title = models.CharField(_("title"), max_length=90)
    message = models.TextField(_("text"), max_length=400)
    image = models.ImageField(_("image"), upload_to=blog_upload_to, blank=True,
                              validators=[validate_blog_image],
                              help_text=_("Optional. Shown above the title."))
    badge = models.CharField(_("badge"), max_length=24, blank=True,
                             help_text=_("Small label, e.g. “-30%” or “New”."))
    coupon_code = models.CharField(_("discount code"), max_length=40, blank=True,
                                   help_text=_("Optional. Shown with a copy button."))
    button_label = models.CharField(_("button text"), max_length=40, blank=True)
    button_url = models.CharField(
        _("button link"), max_length=500, blank=True,
        help_text=_("A page of this site (e.g. /pricing/) or a full https:// link. "
                    "Empty: the button goes to sign-up."))
    placement = models.CharField(_("where to show"), max_length=12, choices=Placement.choices,
                                 default=Placement.PUBLIC)
    audience = models.CharField(_("who sees it"), max_length=8, choices=Audience.choices,
                                default=Audience.ALL)
    frequency = models.CharField(_("how often"), max_length=8, choices=Frequency.choices,
                                 default=Frequency.ONCE)
    delay_seconds = models.PositiveSmallIntegerField(_("delay (seconds)"), default=4,
                                                     help_text=_("0 shows it immediately."))
    starts_at = models.DateTimeField(_("starts"), null=True, blank=True)
    ends_at = models.DateTimeField(_("ends"), null=True, blank=True,
                                   help_text=_("Empty = no end date."))
    priority = models.PositiveSmallIntegerField(
        _("priority"), default=0, help_text=_("If several offers apply, the highest wins."))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PromoQuerySet.as_manager()

    class Meta:
        ordering = ["-priority", "-updated_at"]
        verbose_name = _("pop-up offer")
        verbose_name_plural = _("pop-up offers")

    def __str__(self) -> str:
        return self.name

    def clean(self):
        url = (self.button_url or "").strip()
        if url and not (url.startswith("/") and not url.startswith("//")) \
                and not url.startswith("https://"):
            raise ValidationError({"button_url": _("Use a site page like /pricing/ or a "
                                                   "https:// link.")})
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValidationError({"ends_at": _("The end must be after the start.")})

    @property
    def storage_key(self) -> str:
        # Changes when the offer is edited, so an updated offer is shown again.
        return f"qrumy-promo-{self.pk}-{int(self.updated_at.timestamp())}"


class ContactPage(models.Model):
    """Content of the public contact page, one per language (edited in the admin)."""

    language = models.CharField(_("language"), max_length=8, choices=settings.LANGUAGES,
                                unique=True)
    title = models.CharField(_("title"), max_length=120)
    intro = models.TextField(_("intro text"), max_length=600, blank=True)
    email = models.EmailField(_("email"), blank=True)
    phone = models.CharField(_("phone"), max_length=32, blank=True)
    whatsapp = models.CharField(_("WhatsApp number"), max_length=32, blank=True,
                                help_text=_("With country code, e.g. +994501234567."))
    address = models.CharField(_("address"), max_length=240, blank=True)
    map_url = models.URLField(_("map link"), max_length=500, blank=True,
                              help_text=_("Optional Google Maps link. Without it the address "
                                          "opens in Google Maps."))
    hours = models.CharField(_("working hours"), max_length=160, blank=True,
                             help_text=_("e.g. Mon–Fri 09:00–18:00"))
    form_enabled = models.BooleanField(_("show the contact form"), default=True)
    notify_email = models.EmailField(
        _("send messages to"), blank=True,
        help_text=_("New form messages are emailed here. Empty: only saved in the admin."))
    success_message = models.CharField(
        _("message after sending"), max_length=300, blank=True,
        help_text=_("Empty: a standard thank-you text."))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["language"]
        verbose_name = _("contact page")
        verbose_name_plural = _("contact page")

    def __str__(self) -> str:
        return f"{self.title} ({self.language})"

    @property
    def maps_link(self) -> str:
        if self.map_url:
            return self.map_url
        if self.address:
            from urllib.parse import quote

            return "https://www.google.com/maps/search/?api=1&query=" + quote(self.address)
        return ""

    @property
    def whatsapp_link(self) -> str:
        import re

        digits = re.sub(r"\D", "", self.whatsapp or "")
        return f"https://wa.me/{digits}" if digits else ""


class ContactMessage(models.Model):
    class Topic(models.TextChoices):
        GENERAL = "general", _("General question")
        SALES = "sales", _("Plans and pricing")
        SUPPORT = "support", _("Help with my account")
        PARTNERSHIP = "partnership", _("Partnership")

    name = models.CharField(_("name"), max_length=120)
    email = models.EmailField(_("email"))
    phone = models.CharField(_("phone"), max_length=32, blank=True)
    company = models.CharField(_("company"), max_length=160, blank=True)
    topic = models.CharField(_("topic"), max_length=12, choices=Topic.choices,
                             default=Topic.GENERAL)
    message = models.TextField(_("message"), max_length=3000)
    language = models.CharField(_("language"), max_length=8, blank=True)
    is_handled = models.BooleanField(_("handled"), default=False)
    staff_notes = models.TextField(_("internal notes"), blank=True)
    created_at = models.DateTimeField(_("received"), auto_now_add=True)

    class Meta:
        ordering = ["is_handled", "-created_at"]
        verbose_name = _("contact message")
        verbose_name_plural = _("contact messages")

    def __str__(self) -> str:
        return f"{self.name} — {self.get_topic_display()}"


# --------------------------------------------------------------------------------- SEO
class SeoSettings(models.Model):
    """Site-wide SEO settings (one row, edited in the admin)."""

    title_suffix = models.CharField(_("title suffix"), max_length=40, default=" | Qrumy",
                                    help_text=_("Added to page titles that do not already "
                                                "contain the brand name."))
    default_og_image = models.ImageField(
        _("default social image"), upload_to=blog_upload_to, blank=True,
        validators=[validate_blog_image],
        help_text=_("1200×630. Used when a page has no image of its own. Empty: the built-in "
                    "Qrumy image."))
    google_site_verification = models.CharField(
        _("Google Search Console verification code"), max_length=120, blank=True,
        help_text=_("Only the content value of the HTML tag Google gives you, e.g. "
                    "“abc123…”. Leave empty if you verify by DNS."))
    bing_site_verification = models.CharField(_("Bing verification code"), max_length=120,
                                              blank=True)
    yandex_site_verification = models.CharField(_("Yandex verification code"),
                                                max_length=120, blank=True)
    same_as = models.TextField(
        _("official social profiles"), blank=True,
        help_text=_("One link per line (Instagram, LinkedIn, Facebook…). Used in the "
                    "Organization structured data."))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("SEO settings")
        verbose_name_plural = _("SEO settings")

    def __str__(self) -> str:
        return str(_("SEO settings"))

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from django.core.cache import cache

        cache.delete("qrumy:seo-settings")

    @classmethod
    def load(cls) -> "SeoSettings":
        from django.core.cache import cache

        obj = cache.get("qrumy:seo-settings")
        if obj is None:
            obj = cls.objects.first() or cls()
            cache.set("qrumy:seo-settings", obj, 300)
        return obj

    @property
    def same_as_list(self) -> list[str]:
        return [u.strip() for u in self.same_as.splitlines() if u.strip().startswith("https://")]


class SeoPage(models.Model):
    """Admin overrides for the SEO of one public page in one language.

    Empty fields keep the built-in text. ``page`` is the page key, e.g. "home",
    "pricing" or "tool:wifi-qr-code-generator".
    """

    page = models.CharField(_("page"), max_length=80)
    language = models.CharField(_("language"), max_length=8, choices=settings.LANGUAGES)
    title = models.CharField(_("SEO title"), max_length=90, blank=True,
                             help_text=_("50–60 characters work best. Empty: built-in title."))
    meta_description = models.CharField(
        _("meta description"), max_length=200, blank=True,
        help_text=_("120–160 characters. Shown under the title in Google. Empty: built-in."))
    keywords = models.CharField(
        _("keywords"), max_length=255, blank=True,
        help_text=_("Comma-separated, e.g. “free qr code generator, wifi qr code”. Google "
                    "ignores this tag for ranking; use the words in the title, H1 and text."))
    focus_keyword = models.CharField(
        _("focus keyword"), max_length=80, blank=True,
        help_text=_("The main search phrase of this page. The admin checks whether it "
                    "appears in the title and description."))
    h1 = models.CharField(_("H1 heading"), max_length=120, blank=True,
                          help_text=_("Optional. Empty: built-in heading."))
    og_image = models.ImageField(_("social image"), upload_to=blog_upload_to, blank=True,
                                 validators=[validate_blog_image],
                                 help_text=_("1200×630. Empty: the default social image."))
    noindex = models.BooleanField(_("hide from search engines (noindex)"), default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["page", "language"]
        verbose_name = _("page SEO")
        verbose_name_plural = _("page SEO")
        constraints = [models.UniqueConstraint(fields=["page", "language"],
                                               name="marketing_seopage_unique")]

    def __str__(self) -> str:
        return f"{self.page} ({self.language})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from django.core.cache import cache

        cache.delete(f"qrumy:seo:{self.page}:{self.language}")


class SiteEvent(models.Model):
    """First-party, anonymous daily counters for the acquisition funnel.

    No cookies, IPs or personal data: only the event name, page key, language,
    traffic source (search / social / direct / other) and a count per day.
    """

    day = models.DateField()
    name = models.CharField(max_length=40)
    page = models.CharField(max_length=80, blank=True)
    language = models.CharField(max_length=8, blank=True)
    source = models.CharField(max_length=10, blank=True)
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["day", "name", "page", "language",
                                                       "source"],
                                               name="marketing_siteevent_unique")]
        indexes = [models.Index(fields=["name", "day"])]
        verbose_name = _("site event")
        verbose_name_plural = _("site events")

    def __str__(self) -> str:
        return f"{self.day} {self.name} {self.page} = {self.count}"
