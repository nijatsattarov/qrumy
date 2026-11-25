"""Shared abstract models.

Every model that belongs to a customer organization MUST inherit from
``TenantModel`` and be read through ``Model.objects.for_org(org)``.
See docs/ARCHITECTURE.md §2.2.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        abstract = True


class OrgScopedQuerySet(models.QuerySet):
    def for_org(self, organization):
        if organization is None or getattr(organization, "pk", None) is None:
            raise ValueError("for_org() requires a saved organization")
        return self.filter(organization=organization)


class TenantModel(TimeStampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
        verbose_name=_("organization"),
    )

    objects = OrgScopedQuerySet.as_manager()

    class Meta:
        abstract = True
