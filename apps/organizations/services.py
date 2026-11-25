"""Organization business logic. Views call these; they never write models directly."""

from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.audit_logs.services import record
from apps.core import quotas
from apps.core.utils import generate_token, hash_token, slugify_az
from apps.notifications.services import notify, send_templated_email

from .models import Invitation, Membership, Organization
from .roles import Role, assignable_roles, rank
from .signals import organization_created

TEAM_MEMBERS_FEATURE = "team.members"


class OrganizationError(Exception):
    """A rule violation with a user-facing message."""


def _unique_slug(name: str) -> str:
    base = slugify_az(name, max_length=50) or "org"
    slug, n = base, 2
    while Organization.objects.filter(slug=slug).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


@transaction.atomic
def create_organization(*, owner, name: str, request=None, **fields) -> Organization:
    org = Organization.objects.create(name=name.strip(), slug=_unique_slug(name), owner=owner,
                                      **fields)
    Membership.objects.create(user=owner, organization=org, role=Role.OWNER)
    organization_created.send(sender=Organization, organization=org, actor=owner)
    record("organization.created", actor=owner, organization=org, target=org, request=request)
    return org


def update_organization(*, organization, actor, form, request=None) -> Organization:
    changed = list(form.changed_data)
    org = form.save()
    if changed:
        record("organization.updated", actor=actor, organization=org, target=org,
               changes={"fields": changed}, request=request)
    return org


def team_usage(organization) -> int:
    """Members + pending invitations count against the team limit."""
    pending = Invitation.objects.filter(organization=organization, accepted_at__isnull=True,
                                        revoked_at__isnull=True,
                                        expires_at__gt=timezone.now()).count()
    return organization.memberships.count() + pending


def invite_member(*, organization, actor_membership, email: str, role: str,
                  request=None) -> tuple[Invitation, str]:
    email = email.strip().lower()
    if Role(role) not in assignable_roles(actor_membership.role):
        raise OrganizationError(_("You cannot invite someone with this role."))
    if organization.memberships.filter(user__email__iexact=email).exists():
        raise OrganizationError(_("This person is already a member of the organization."))
    try:
        quotas.check(organization, TEAM_MEMBERS_FEATURE, team_usage(organization))
    except quotas.QuotaExceeded as exc:
        raise OrganizationError(
            _("Your plan allows up to %(limit)s team members (including pending invitations).")
            % {"limit": exc.limit}
        ) from exc

    # An expired, never-answered invitation must not block a fresh one.
    Invitation.objects.filter(organization=organization, email__iexact=email,
                              accepted_at__isnull=True, revoked_at__isnull=True,
                              expires_at__lte=timezone.now()).update(revoked_at=timezone.now())
    raw_token = generate_token()
    try:
        with transaction.atomic():
            invitation = Invitation.objects.create(
                organization=organization, email=email, role=role,
                token_hash=hash_token(raw_token), invited_by=actor_membership.user,
                expires_at=timezone.now() + timedelta(days=settings.QRUMY_INVITATION_TTL_DAYS),
            )
    except IntegrityError as exc:
        raise OrganizationError(_("An invitation is already pending for this email.")) from exc

    accept_url = settings.SITE_URL + reverse("invitation_accept", kwargs={"token": raw_token})
    send_templated_email(
        to=email, template="organizations/email/invitation",
        context={"organization": organization, "inviter": actor_membership.user,
                 "role": invitation.get_role_display(), "accept_url": accept_url,
                 "days": settings.QRUMY_INVITATION_TTL_DAYS},
        language=organization.language,
    )
    record("team.invited", actor=actor_membership.user, organization=organization,
           target=invitation, changes={"role": role}, request=request)
    return invitation, raw_token


def revoke_invitation(*, invitation, actor_membership, request=None) -> None:
    if invitation.accepted_at or invitation.revoked_at:
        return
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["revoked_at", "updated_at"])
    record("team.invitation_revoked", actor=actor_membership.user,
           organization=invitation.organization, target=invitation, request=request)


def get_invitation_by_token(raw_token: str) -> Invitation | None:
    return (Invitation.objects.select_related("organization", "invited_by")
            .filter(token_hash=hash_token(raw_token)).first())


@transaction.atomic
def accept_invitation(*, invitation: Invitation, user, request=None) -> Membership:
    invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
    if not invitation.is_pending:
        raise OrganizationError(_("This invitation is no longer valid."))
    if user.email.lower() != invitation.email.lower():
        raise OrganizationError(
            _("This invitation was sent to %(email)s. Sign in with that email to accept it.")
            % {"email": invitation.email}
        )
    if not invitation.organization.is_active:
        raise OrganizationError(_("This organization is not available."))
    membership, created = Membership.objects.get_or_create(
        user=user, organization=invitation.organization, defaults={"role": invitation.role})
    invitation.accepted_at = timezone.now()
    invitation.accepted_by = user
    invitation.save(update_fields=["accepted_at", "accepted_by", "updated_at"])
    if created:
        record("team.joined", actor=user, organization=invitation.organization,
               target=membership, changes={"role": membership.role}, request=request)
        if invitation.invited_by_id:
            notify(invitation.invited_by, kind="team.joined",
                   organization=invitation.organization,
                   title=_("%(name)s joined %(org)s") % {
                       "name": user.display_name, "org": invitation.organization.name},
                   url=reverse("team", kwargs={"org_slug": invitation.organization.slug}))
    return membership


def _ensure_can_manage(actor_membership, target_membership) -> None:
    if target_membership.organization_id != actor_membership.organization_id:
        raise OrganizationError(_("Member not found."))
    if target_membership.role == Role.OWNER:
        raise OrganizationError(_("The organization owner cannot be changed or removed."))
    if rank(actor_membership.role) <= rank(target_membership.role):
        raise OrganizationError(_("You can only manage members with a lower role than yours."))


def change_role(*, actor_membership, target_membership, new_role: str,
                request=None) -> Membership:
    _ensure_can_manage(actor_membership, target_membership)
    if Role(new_role) not in assignable_roles(actor_membership.role):
        raise OrganizationError(_("You cannot assign this role."))
    old = target_membership.role
    target_membership.role = new_role
    target_membership.save(update_fields=["role", "updated_at"])
    record("team.role_changed", actor=actor_membership.user,
           organization=target_membership.organization, target=target_membership,
           changes={"from": old, "to": new_role}, request=request)
    return target_membership


def remove_member(*, actor_membership, target_membership, request=None) -> None:
    _ensure_can_manage(actor_membership, target_membership)
    record("team.removed", actor=actor_membership.user,
           organization=target_membership.organization, target=target_membership,
           changes={"email": target_membership.user.email}, request=request)
    target_membership.delete()


def leave_organization(*, membership, request=None) -> None:
    if membership.role == Role.OWNER:
        raise OrganizationError(_("The owner cannot leave the organization."))
    record("team.left", actor=membership.user, organization=membership.organization,
           target=membership, request=request)
    membership.delete()


@transaction.atomic
def transfer_ownership(*, organization, actor_membership, target_membership,
                       request=None) -> None:
    if actor_membership.role != Role.OWNER or actor_membership.organization_id != organization.pk:
        raise OrganizationError(_("Only the owner can transfer ownership."))
    if target_membership.organization_id != organization.pk or target_membership.pk == \
            actor_membership.pk:
        raise OrganizationError(_("Choose another member of this organization."))
    target_membership.role = Role.OWNER
    target_membership.save(update_fields=["role", "updated_at"])
    actor_membership.role = Role.ADMIN
    actor_membership.save(update_fields=["role", "updated_at"])
    organization.owner = target_membership.user
    organization.save(update_fields=["owner", "updated_at"])
    record("organization.ownership_transferred", actor=actor_membership.user,
           organization=organization, target=organization,
           changes={"to": target_membership.user.email}, request=request)
    notify(target_membership.user, kind="organization.owner", organization=organization,
           title=_("You are now the owner of %(org)s") % {"org": organization.name},
           url=reverse("organization_settings", kwargs={"org_slug": organization.slug}))


@transaction.atomic
def delete_organization(*, organization, actor, request=None) -> None:
    """Deletes the organization and ALL its data (codes, surveys, assets, ...)."""
    record("organization.deleted", actor=actor, organization=None, target=organization,
           changes={"slug": organization.slug}, request=request)
    organization.delete()
