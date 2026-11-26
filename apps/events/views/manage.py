import csv

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.organizations.permissions import can, require_capability, require_module

from .. import services
from ..forms import EventForm, FollowUpForm, LeadUpdateForm, PointForm, StaffLeadForm
from ..models import CapturePoint, Event, FollowUp, Lead


def _events(request):
    return Event.objects.for_org(request.organization)


def _event(request, pk):
    return get_object_or_404(_events(request), pk=pk)


def _point(request, event, point_id):
    return get_object_or_404(CapturePoint.objects.for_org(request.organization)
                             .select_related("qr_code"), pk=point_id, event=event)


def _lead(request, pk):
    return get_object_or_404(Lead.objects.for_org(request.organization)
                             .select_related("event", "point", "assigned_to"), pk=pk)


# ----------------------------------------------------------------------------- events
@require_module("events")
@require_capability("content.view")
def event_list(request, org_slug):
    events = _events(request).annotate(n_leads=Count("leads", distinct=True),
                                       n_points=Count("points", distinct=True))
    return render(request, "events/list.html", {"events": events})


@require_module("events")
@require_capability("content.create")
def event_create(request, org_slug):
    form = EventForm(request.POST or None, initial={
        "language": getattr(request, "LANGUAGE_CODE", "az"), "is_active": True,
        "ask_phone": True, "ask_company": True, "ask_message": True})
    if request.method == "POST" and form.is_valid():
        try:
            event = services.create_event(organization=request.organization,
                                          actor=request.user, data=form.cleaned_data,
                                          request=request)
            services.add_point(event=event, actor=request.user,
                               data={"name": request.POST.get("first_point") or _("Main stand")},
                               request=request)
        except services.EventError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, _("Event created. Print the QR code of your stand."))
            return redirect("event_detail", org_slug=org_slug, pk=event.pk)
    return render(request, "events/form.html", {"form": form, "event": None})


@require_module("events")
@require_capability("content.view")
def event_detail(request, org_slug, pk):
    event = _event(request, pk)
    points = event.points.select_related("qr_code").annotate(n=Count("leads"))
    return render(request, "events/detail.html", {
        "event": event, "points": points, "stats": services.stats(event),
        "recent": event.leads.select_related("point")[:8], "point_form": PointForm(),
        "new_portal": request.session.pop("events_portal_link", None)})


@require_module("events")
@require_capability("content.edit")
def event_edit(request, org_slug, pk):
    event = _event(request, pk)
    form = EventForm(request.POST or None, instance=event)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Event saved."))
        return redirect("event_detail", org_slug=org_slug, pk=pk)
    return render(request, "events/form.html", {"form": form, "event": event})


@require_module("events")
@require_capability("content.delete")
@require_POST
def event_delete(request, org_slug, pk):
    event = _event(request, pk)
    if request.POST.get("confirm", "").strip() != event.name.strip():
        messages.error(request, _("Type the event name exactly to confirm deletion."))
        return redirect("event_edit", org_slug=org_slug, pk=pk)
    services.delete_event(event=event, actor=request.user, request=request)
    messages.success(request, _("Event and its leads deleted."))
    return redirect("event_list", org_slug=org_slug)


# ----------------------------------------------------------------------------- points
@require_module("events")
@require_capability("content.edit")
@require_POST
def point_save(request, org_slug, pk, point_id=None):
    event = _event(request, pk)
    point = _point(request, event, point_id) if point_id else None
    form = PointForm(request.POST, instance=point, prefix=f"p{point_id}" if point_id else None)
    if not form.is_valid():
        messages.error(request, _("Check the collection point details."))
    elif point is None:
        try:
            services.add_point(event=event, actor=request.user, data=form.cleaned_data,
                               request=request)
            messages.success(request, _("Collection point added with its own QR code."))
        except services.EventError as exc:
            messages.error(request, str(exc))
    else:
        form.save()
        messages.success(request, _("Collection point saved."))
    return redirect("event_detail", org_slug=org_slug, pk=pk)


@require_module("events")
@require_capability("content.delete")
@require_POST
def point_delete(request, org_slug, pk, point_id):
    event = _event(request, pk)
    point = _point(request, event, point_id)
    services.delete_point(point=point, actor=request.user, request=request)
    messages.success(request, _("Collection point deleted. Its leads are kept."))
    return redirect("event_detail", org_slug=org_slug, pk=pk)


@require_module("events")
@require_capability("content.edit")
@require_POST
def point_portal(request, org_slug, pk, point_id):
    """Create, replace or revoke the exhibitor's private lead link."""
    event = _event(request, pk)
    point = _point(request, event, point_id)
    if request.POST.get("revoke") == "1":
        point.portal_token_hash = ""
        point.save(update_fields=["portal_token_hash", "updated_at"])
        messages.success(request, _("The exhibitor link was turned off."))
    else:
        raw = point.new_portal_token()
        from django.urls import reverse

        request.session["events_portal_link"] = {
            "point": point.pk,
            "url": services.site_url() + reverse("event_portal", kwargs={"token": raw})}
    return redirect("event_detail", org_slug=org_slug, pk=pk)


# ------------------------------------------------------------------------------ leads
def _filtered(request, qs):
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(full_name__icontains=q) | Q(email__icontains=q) |
                       Q(company__icontains=q) | Q(phone__icontains=q))
    for field in ("temperature", "stage"):
        if (v := request.GET.get(field)) in dict(getattr(Lead, field.capitalize()).choices):
            qs = qs.filter(**{field: v})
    if (point := request.GET.get("point", "")).isdigit():
        qs = qs.filter(point_id=int(point))
    if request.GET.get("assigned") == "me":
        qs = qs.filter(assigned_to=request.user)
    return qs


@require_module("events")
@require_capability("content.view")
def lead_list(request, org_slug, pk):
    event = _event(request, pk)
    leads = _filtered(request, event.leads.select_related("point", "assigned_to"))
    page = Paginator(leads, 50).get_page(request.GET.get("page"))
    return render(request, "events/leads.html", {
        "event": event, "page": page, "points": event.points.all(),
        "temperatures": Lead.Temperature.choices, "stages": Lead.Stage.choices,
        "filters": request.GET})


@require_module("events")
@require_capability("content.view")
def lead_export(request, org_slug, pk):
    event = _event(request, pk)
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="leads-{event.pk}.csv"'
    resp.write("﻿")  # Excel opens UTF-8 (Azerbaijani letters) correctly
    writer = csv.writer(resp)
    writer.writerow(services.CSV_HEADER)
    for row in services.csv_rows(_filtered(request, event.leads.all())):
        writer.writerow(row)
    return resp


@require_module("events")
@require_capability("content.create")
def lead_create(request, org_slug, pk):
    event = _event(request, pk)
    form = StaffLeadForm(request.POST or None, event=event,
                         initial={"temperature": "warm", "point": request.GET.get("point")})
    if request.method == "POST" and form.is_valid():
        data = {k: v for k, v in form.cleaned_data.items() if k != "consent"}
        data["interests"] = data.get("interests") or []
        lead = services.add_lead(event=event, actor=request.user,
                                 data={**data, "consent": True})
        messages.success(request, _("Lead saved."))
        if request.POST.get("another") == "1":
            return redirect(f"{request.path}?point={lead.point_id or ''}")
        return redirect("event_lead", org_slug=org_slug, pk=lead.pk)
    return render(request, "events/lead_form.html", {"event": event, "form": form})


@require_module("events")
@require_capability("content.view")
def lead_detail(request, org_slug, pk):
    lead = _lead(request, pk)
    form = LeadUpdateForm(request.POST or None, instance=lead,
                          organization=request.organization)
    if request.method == "POST":
        if not can(request, "content.edit"):
            messages.error(request, _("You don't have permission to do that."))
        elif form.is_valid():
            form.save()
            messages.success(request, _("Lead updated."))
            return redirect("event_lead", org_slug=org_slug, pk=pk)
    return render(request, "events/lead_detail.html", {
        "lead": lead, "event": lead.event, "form": form, "followup_form": FollowUpForm(),
        "notes": lead.notes.select_related("author"),
        "followups": lead.followups.select_related("assigned_to"),
        "today": timezone.localdate()})


@require_module("events")
@require_capability("content.edit")
@require_POST
def lead_note(request, org_slug, pk):
    lead = _lead(request, pk)
    body = request.POST.get("body", "").strip()
    if body:
        services.add_note(lead=lead, actor=request.user, body=body)
        messages.success(request, _("Note added."))
    return redirect("event_lead", org_slug=org_slug, pk=pk)


@require_module("events")
@require_capability("content.edit")
@require_POST
def lead_followup(request, org_slug, pk, followup_id=None):
    lead = _lead(request, pk)
    if followup_id:
        followup = get_object_or_404(FollowUp.objects.for_org(request.organization),
                                     pk=followup_id, lead=lead)
        services.toggle_followup(followup)
    else:
        form = FollowUpForm(request.POST)
        if form.is_valid():
            services.add_followup(lead=lead, actor=request.user, **form.cleaned_data)
            messages.success(request, _("Follow-up task added."))
        else:
            messages.error(request, _("Describe the follow-up task."))
    return redirect("event_lead", org_slug=org_slug, pk=pk)


@require_module("events")
@require_capability("content.delete")
@require_POST
def lead_delete(request, org_slug, pk):
    lead = _lead(request, pk)
    event_pk = lead.event_id
    lead.delete()
    messages.success(request, _("Lead deleted."))
    return redirect("event_leads", org_slug=org_slug, pk=event_pk)
