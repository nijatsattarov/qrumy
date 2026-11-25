from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AuditLogsConfig(AppConfig):
    name = "apps.audit_logs"
    label = "audit_logs"
    verbose_name = _("Audit logs")
