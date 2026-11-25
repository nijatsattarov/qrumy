from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import services
from .models import Notification


@login_required
def notification_list(request):
    page = Paginator(Notification.objects.filter(user=request.user), 30).get_page(
        request.GET.get("page"))
    return render(request, "notifications/list.html", {"page": page})


@login_required
@require_POST
def mark_all_read(request):
    services.mark_all_read(request.user)
    return redirect("notifications")
