from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    name = "apps.accounts"
    label = "accounts"
    verbose_name = _("Accounts")

    def ready(self):
        from django.apps import apps

        # allauth's "account" app is also called "Accounts"; rename it so the admin
        # sidebar does not show two sections with the same name.
        if apps.is_installed("allauth.account"):
            apps.get_app_config("account").verbose_name = _("Sign-in emails")
