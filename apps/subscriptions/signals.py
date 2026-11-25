from django.dispatch import receiver

from apps.organizations.signals import organization_created

from .services import start_default_subscription


@receiver(organization_created)
def assign_default_plan(sender, organization, **kwargs):
    start_default_subscription(organization)
