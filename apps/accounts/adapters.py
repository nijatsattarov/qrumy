from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request) -> bool:
        # Free beta: open registration (can be closed via env without a deploy).
        return getattr(settings, "QRUMY_SIGNUP_OPEN", True)
