from django.conf import settings

from .base import CheckoutUnavailable, PaymentGateway
from .manual import ManualGateway

_GATEWAYS: dict[str, type[PaymentGateway]] = {ManualGateway.key: ManualGateway}


def get_gateway(key: str | None = None) -> PaymentGateway:
    key = key or getattr(settings, "QRUMY_PAYMENT_GATEWAY", ManualGateway.key)
    return _GATEWAYS[key]()


__all__ = ["CheckoutUnavailable", "ManualGateway", "PaymentGateway", "get_gateway"]
