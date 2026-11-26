from django.conf import settings


def connect() -> None:
    from allauth.account.signals import user_signed_up

    user_signed_up.connect(on_user_signed_up, dispatch_uid="qrumy-social-signup")


def on_user_signed_up(sender, request, user, sociallogin=None, **kwargs):
    """Google sign-ups skip our sign-up form: record the terms shown next to the button,
    and take the name and the page language."""
    if sociallogin is None:
        return
    from .legal import LegalDocument, TermsAcceptance, current

    terms = current(LegalDocument.Kind.TERMS)
    if terms:
        privacy = current(LegalDocument.Kind.PRIVACY)
        TermsAcceptance.objects.create(user=user, terms_version=terms.version,
                                       privacy_version=privacy.version if privacy else "")
    fields = []
    data = sociallogin.account.extra_data or {}
    name = (data.get("name") or " ".join(
        x for x in (data.get("given_name"), data.get("family_name")) if x)).strip()
    if name and not user.full_name:
        user.full_name = name[:150]
        fields.append("full_name")
    lang = getattr(request, "LANGUAGE_CODE", None)
    if lang in dict(settings.LANGUAGES) and user.language != lang:
        user.language = lang
        fields.append("language")
    if fields:
        user.save(update_fields=fields)
