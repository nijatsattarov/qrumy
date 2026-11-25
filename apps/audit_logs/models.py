from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLog(models.Model):
    """Append-only record of sensitive actions (tenant and super-admin)."""

    created_at = models.DateTimeField(_("time"), auto_now_add=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="+",
                              verbose_name=_("actor"))
    actor_email = models.EmailField(_("actor email"), blank=True)
    is_staff_action = models.BooleanField(_("staff action"), default=False)
    organization = models.ForeignKey("organizations.Organization", null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name="audit_logs",
                                     verbose_name=_("organization"))
    action = models.CharField(_("action"), max_length=100, db_index=True)
    target_type = models.CharField(_("target type"), max_length=100, blank=True)
    target_id = models.CharField(_("target id"), max_length=64, blank=True)
    target_repr = models.CharField(_("target"), max_length=255, blank=True)
    changes = models.JSONField(_("details"), default=dict, blank=True)
    ip_hash = models.CharField(_("IP hash"), max_length=32, blank=True)
    user_agent = models.CharField(_("user agent"), max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("audit log entry")
        verbose_name_plural = _("audit log")
        indexes = [models.Index(fields=["organization", "-created_at"])]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.action}"
