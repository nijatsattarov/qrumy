"""Legal documents (Terms, Privacy) edited by staff, versioned, in English and Azerbaijani."""

from django.conf import settings
from django.db import models
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _


class LegalDocument(models.Model):
    class Kind(models.TextChoices):
        TERMS = "terms", _("Terms of Service")
        PRIVACY = "privacy", _("Privacy Policy")

    kind = models.CharField(_("document"), max_length=10, choices=Kind.choices)
    language = models.CharField(_("language"), max_length=8, choices=settings.LANGUAGES)
    version = models.CharField(_("version"), max_length=20,
                               help_text=_("e.g. 2026-12-01. Increase it for every change "
                                           "users must accept again."))
    title = models.CharField(_("title"), max_length=150)
    body = models.TextField(_("text"), help_text=_("Plain text. A line starting with “## ” is a "
                                                   "heading, “- ” a list item; blank lines "
                                                   "separate paragraphs."))
    published_at = models.DateTimeField(_("published at"), null=True, blank=True,
                                        help_text=_("Empty = draft (not shown to anyone)."))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "accounts"
        ordering = ["kind", "language", "-published_at"]
        verbose_name = _("legal document")
        verbose_name_plural = _("legal documents")
        constraints = [models.UniqueConstraint(fields=["kind", "language", "version"],
                                               name="accounts_legal_unique_version")]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} ({self.language}) v{self.version}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from django.core.cache import cache

        cache.delete("qrumy:legal-links")


class TermsAcceptance(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="terms_acceptances")
    terms_version = models.CharField(max_length=20)
    privacy_version = models.CharField(max_length=20, blank=True)
    accepted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "accounts"
        ordering = ["-accepted_at"]
        verbose_name = _("terms acceptance")
        verbose_name_plural = _("terms acceptances")

    def __str__(self) -> str:
        return f"{self.user_id} accepted terms v{self.terms_version}"


def current(kind: str, language: str | None = None) -> LegalDocument | None:
    """Latest published document in the language, falling back to English."""
    language = language or translation.get_language() or settings.LANGUAGE_CODE
    qs = LegalDocument.objects.filter(kind=kind, published_at__lte=timezone.now())
    return (qs.filter(language=language).order_by("-published_at").first()
            or qs.filter(language=settings.LANGUAGE_CODE).order_by("-published_at").first())


def terms_required() -> bool:
    return current(LegalDocument.Kind.TERMS, settings.LANGUAGE_CODE) is not None
