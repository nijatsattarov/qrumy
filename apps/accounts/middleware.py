from django.conf import settings
from django.utils import translation

APP_PATH_PREFIXES = ("/app/", "/accounts/", "/invitations/", "/notifications/",
                     "/a/", "/q/")  # public asset & QR pages follow the phone's language


class UserLanguageMiddleware:
    """Pick the language for product pages (URLs without a language prefix).

    Django's LocaleMiddleware forces the default language on every unprefixed URL when
    ``i18n_patterns(prefix_default_language=False)`` is used. Marketing pages keep that
    URL-based behaviour (/ = English, /az/ = Azerbaijani); inside the product we use the
    signed-in user's preference, otherwise the language cookie / browser language.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.supported = dict(settings.LANGUAGES)

    def __call__(self, request):
        if request.path.startswith(APP_PATH_PREFIXES):
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated and user.language in self.supported:
                lang = user.language
            else:
                lang = translation.get_language_from_request(request, check_path=False)
            if lang in self.supported:
                translation.activate(lang)
                request.LANGUAGE_CODE = lang
        return self.get_response(request)
