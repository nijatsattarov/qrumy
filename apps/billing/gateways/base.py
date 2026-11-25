from abc import ABC, abstractmethod
from dataclasses import dataclass


class CheckoutUnavailable(Exception):
    """Self-service payment is not possible with this gateway (e.g. during the free beta)."""


@dataclass
class CheckoutSession:
    redirect_url: str
    reference: str


class PaymentGateway(ABC):
    """Contract every payment provider adapter implements (Stripe, Paddle, ...).

    A subscription is activated only from a *verified* provider event (webhook) —
    never because the user returned from a checkout page.
    """

    key: str = ""

    @abstractmethod
    def start_checkout(self, *, organization, plan, interval: str, actor) -> CheckoutSession: ...

    @abstractmethod
    def cancel(self, *, subscription, actor) -> None: ...

    @abstractmethod
    def handle_webhook(self, request) -> None: ...
