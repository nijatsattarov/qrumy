from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.audit_logs.services import record
from apps.core import quotas
from apps.core.utils import hash_token
from apps.notifications.services import notify, send_templated_email
from apps.organizations.models import Membership

from .models import CapturePoint, Event, FollowUp, Lead, LeadNote

EVENTS_FEATURE = "events.max"
MAX_POINTS = 200


class EventError(Exception):
    pass


# ----------------------------------------------------------------------------- events
def create_event(*, organization, actor, data: dict, request=None) -> Event:
    try:
        quotas.check(organization, EVENTS_FEATURE, Event.objects.for_org(organization).count())
    except quotas.QuotaExceeded as exc:
        raise EventError(_("Your plan allows up to %(limit)s events.") % {"limit": exc.limit}) \
            from exc
    event = Event.objects.create(organization=organization, created_by=actor, **data)
    record("event.created", actor=actor, organization=organization, target=event,
           request=request)
    return event


def delete_event(*, event, actor, request=None) -> None:
    from apps.qr_management import services as qr_services

    for point in event.points.select_related("qr_code"):
        _pause_qr(point, actor, request, qr_services)
    record("event.deleted", actor=actor, organization=event.organization,
           changes={"name": event.name, "leads": event.leads.count()}, request=request)
    event.delete()


def _pause_qr(point, actor, request, qr_services):
    qr = point.qr_code
    if qr and qr.deleted_at is None and qr.status == "active":
        qr_services.set_status(qr=qr, actor=actor, status="paused", request=request)


# ----------------------------------------------------------------------------- points
def add_point(*, event, actor, data: dict, request=None) -> CapturePoint:
    if event.points.count() >= MAX_POINTS:
        raise EventError(_("An event can have up to %(n)s collection points.") % {
            "n": MAX_POINTS})
    point = CapturePoint.objects.create(organization=event.organization, event=event, **data)
    ensure_qr(point=point, actor=actor, request=request)
    return point


def ensure_qr(*, point, actor, request=None):
    from apps.qr_management import services as qr_services
    from apps.qr_management.engine import QRStyle

    if point.qr_code_id and point.qr_code.deleted_at is None:
        return point.qr_code
    try:
        qr = qr_services.create_qr(
            organization=point.organization, actor=actor, qr_type="event_lead",
            mode="dynamic", name=f"{point.event.name} · {point.name}"[:120],
            payload={"capture_token": point.capture_token, "point_name": point.name},
            style=QRStyle(frame="bottom", cta_text=_("Leave your contacts")[:30]),
            request=request)
    except qr_services.QRError as exc:
        raise EventError(str(exc)) from exc
    point.qr_code = qr
    point.save(update_fields=["qr_code", "updated_at"])
    return qr


def delete_point(*, point, actor, request=None) -> None:
    from apps.qr_management import services as qr_services

    _pause_qr(point, actor, request, qr_services)
    point.delete()


def point_by_portal_token(raw: str) -> CapturePoint | None:
    if not raw:
        return None
    return (CapturePoint.objects.select_related("event", "organization")
            .filter(portal_token_hash=hash_token(raw)).first())


# ------------------------------------------------------------------------------ leads
def _recipients(organization):
    return [m.user for m in Membership.objects.filter(
        organization=organization, role__in=["owner", "admin", "manager"]).select_related("user")]


@transaction.atomic
def capture_lead(*, point, data: dict, consent_text: str) -> Lead:
    """A visitor filled in the public form."""
    event = point.event
    lead = Lead.objects.create(organization=point.organization, event=event, point=point,
                               source=Lead.Source.QR, consent=True,
                               consent_text=consent_text[:400], **data)
    url = reverse("event_lead", kwargs={"org_slug": point.organization.slug, "pk": lead.pk})
    title = _("New lead at %(point)s: %(name)s") % {"point": point.name, "name": lead.full_name}
    for user in _recipients(point.organization):
        notify(user, kind="events.lead", organization=point.organization, title=title,
               body=event.name, url=url)
    if point.contact_email:
        transaction.on_commit(lambda: send_templated_email(
            to=point.contact_email, template="events/email/new_lead",
            context={"lead": lead, "point": point, "event": event}, language=event.language))
    return lead


def add_lead(*, event, actor, data: dict) -> Lead:
    """Staff typed in a lead (e.g. from a business card)."""
    return Lead.objects.create(organization=event.organization, event=event,
                               source=Lead.Source.STAFF, added_by=actor, **data)


def add_note(*, lead, actor, body: str) -> LeadNote:
    return LeadNote.objects.create(organization=lead.organization, lead=lead, author=actor,
                                   body=body.strip()[:2000])


def add_followup(*, lead, actor, title: str, due_on=None) -> FollowUp:
    return FollowUp.objects.create(organization=lead.organization, lead=lead,
                                   title=title.strip()[:160], due_on=due_on,
                                   assigned_to=lead.assigned_to or actor)


def toggle_followup(followup) -> None:
    followup.done_at = None if followup.done_at else timezone.now()
    followup.save(update_fields=["done_at", "updated_at"])


# ------------------------------------------------------------------------------ stats
def stats(event) -> dict:
    leads = event.leads.all()
    today = timezone.localdate()
    by_temp = dict(leads.values_list("temperature").annotate(n=Count("pk")))
    by_stage = dict(leads.values_list("stage").annotate(n=Count("pk")))
    per_point = list(event.points.annotate(n=Count("leads")).order_by("-n")
                     .values("pk", "name", "company_name", "n"))
    start = event.starts_on or (leads.order_by("created_at").values_list(
        "created_at", flat=True).first() or timezone.now()).date()
    end = max(event.ends_on or today, start)
    days = min((end - start).days + 1, 31)
    per_day = dict(leads.filter(created_at__date__gte=start).annotate(d=TruncDate("created_at"))
                   .values_list("d").annotate(n=Count("pk")))
    series = [{"day": start + timedelta(days=i), "n": per_day.get(start + timedelta(days=i), 0)}
              for i in range(days)]
    total = leads.count()
    return {"total": total, "hot": by_temp.get("hot", 0), "warm": by_temp.get("warm", 0),
            "cold": by_temp.get("cold", 0), "by_stage": by_stage, "per_point": per_point,
            "series": series, "max_day": max([s["n"] for s in series] or [0]),
            "chart_values": [s["n"] for s in series],
            "chart_labels": [s["day"].strftime("%d.%m") for s in series],
            "with_email": leads.exclude(email="").count(),
            "open_followups": FollowUp.objects.filter(lead__event=event,
                                                      done_at__isnull=True).count()}


CSV_HEADER = ["created", "event", "collection point", "exhibitor", "full name", "email",
              "phone", "company", "job title", "interests", "message", "interest level",
              "stage", "assigned to", "source", "consent"]


def csv_rows(leads):
    for lead in leads.select_related("event", "point", "assigned_to"):
        yield [timezone.localtime(lead.created_at).strftime("%Y-%m-%d %H:%M"), lead.event.name,
               lead.point.name if lead.point else "",
               lead.point.company_name if lead.point else "", lead.full_name, lead.email,
               lead.phone, lead.company, lead.job_title, "; ".join(lead.interests),
               lead.message, lead.get_temperature_display(), lead.get_stage_display(),
               lead.assigned_to.email if lead.assigned_to else "", lead.get_source_display(),
               "yes" if lead.consent else "no"]


def site_url() -> str:
    return settings.SITE_URL
