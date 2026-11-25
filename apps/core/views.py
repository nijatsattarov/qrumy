from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@never_cache
@require_GET
def healthz(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:  # noqa: BLE001 — report, never raise from a health check
        db_ok = False
    return JsonResponse({"status": "ok" if db_ok else "degraded", "database": db_ok},
                        status=200 if db_ok else 503)


def ratelimited(request, exception=None):
    return render(request, "429.html", status=429)


def robots_txt(request):
    lines = ["User-agent: *", "Disallow: /app/", "Disallow: /accounts/",
             "Disallow: /invitations/", "Disallow: /s/", "Disallow: /q/",
             f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
