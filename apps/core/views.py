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
             "Disallow: /invitations/", "Disallow: /s/", "Disallow: /q/", "Disallow: /a/",
             f"Sitemap: {request.build_absolute_uri('/sitemap.xml')}"]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def public_media(request, path):
    """Serve files under MEDIA_ROOT/public/ when no web server does it.

    In the Docker setup Nginx answers /media/public/ itself and this view is never reached.
    It keeps logos and blog images working when the app runs without Nginx in front.
    Only the public/ folder is served; private files stay behind their own views.
    """
    import mimetypes
    from pathlib import Path

    from django.conf import settings
    from django.http import FileResponse, Http404

    root = (Path(settings.MEDIA_ROOT) / "public").resolve()
    target = (root / path).resolve()
    if root not in target.parents or not target.is_file():
        raise Http404
    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    if content_type not in {"image/png", "image/jpeg", "image/webp", "image/gif",
                            "image/svg+xml"}:
        raise Http404
    response = FileResponse(target.open("rb"), content_type=content_type)
    response["Cache-Control"] = "public, max-age=604800"
    response["X-Content-Type-Options"] = "nosniff"
    if content_type == "image/svg+xml":
        response["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
    return response
