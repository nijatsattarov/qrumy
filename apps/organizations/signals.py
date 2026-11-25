from django.dispatch import Signal

# Sent inside the creation transaction. kwargs: organization, actor
organization_created = Signal()
