from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.accounts.views import set_language
from apps.assets import urls as asset_urls
from apps.core import views as core_views
from apps.marketing.sitemaps import StaticViewSitemap
from apps.qr_management import urls as qr_urls
from apps.surveys import urls as survey_urls

admin.site.site_header = "Qrumy"

urlpatterns = [
    path(settings.QRUMY_ADMIN_PATH, admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("accounts/", include("allauth.urls")),
    path("i18n/setlang/", set_language, name="set_language"),
    path("app/<slug:org_slug>/billing/", include("apps.billing.urls")),
    path("app/<slug:org_slug>/", include(qr_urls.app_urlpatterns)),
    path("q/", include(qr_urls.public_urlpatterns)),
    path("app/<slug:org_slug>/", include(survey_urls.app_urlpatterns)),
    path("s/", include(survey_urls.public_urlpatterns)),
    path("app/<slug:org_slug>/", include(asset_urls.app_urlpatterns)),
    path("a/", include(asset_urls.public_urlpatterns)),
    path("app/", include("apps.organizations.urls")),
    path("invitations/", include("apps.organizations.invitation_urls")),
    path("notifications/", include("apps.notifications.urls")),
    path("robots.txt", core_views.robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": {"static": StaticViewSitemap}},
         name="django.contrib.sitemaps.views.sitemap"),
]

urlpatterns += i18n_patterns(
    path("", include("apps.marketing.urls")),
    prefix_default_language=False,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
