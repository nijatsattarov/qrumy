import re

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.organizations import services
from apps.organizations.models import Invitation, Membership
from apps.subscriptions.models import FeatureOverride

pytestmark = pytest.mark.django_db


def _invite(client, org, email, role="member"):
    return client.post(reverse("team_invite", kwargs={"org_slug": org.slug}),
                       {"email": email, "role": role})


def _token_from_mail():
    return re.search(r"/invitations/([\w-]+)/", mail.outbox[-1].body).group(1)


def test_full_invitation_flow(client, make_user, make_org):
    org = make_org()
    client.force_login(org.owner)
    _invite(client, org, "new@example.com", "manager")
    inv = Invitation.objects.get()
    assert inv.role == "manager" and len(mail.outbox) == 1
    token = _token_from_mail()
    assert inv.token_hash != token  # only the hash is stored

    invitee = make_user(email="new@example.com")
    client.force_login(invitee)
    url = reverse("invitation_accept", kwargs={"token": token})
    assert client.get(url).status_code == 200
    resp = client.post(url)
    assert resp["Location"] == reverse("dashboard", kwargs={"org_slug": org.slug})
    assert Membership.objects.get(organization=org, user=invitee).role == "manager"
    # cannot be reused
    assert client.get(url).status_code == 404


def test_invitation_requires_matching_email(client, make_user, make_org):
    org = make_org()
    client.force_login(org.owner)
    _invite(client, org, "new@example.com")
    token = _token_from_mail()
    other = make_user(email="other@example.com")
    client.force_login(other)
    client.post(reverse("invitation_accept", kwargs={"token": token}))
    assert not Membership.objects.filter(user=other).exists()


def test_expired_invitation_rejected(client, make_user, make_org):
    org = make_org()
    client.force_login(org.owner)
    _invite(client, org, "new@example.com")
    token = _token_from_mail()
    Invitation.objects.update(expires_at=timezone.now() - timezone.timedelta(minutes=1))
    client.force_login(make_user(email="new@example.com"))
    assert client.post(reverse("invitation_accept", kwargs={"token": token})).status_code == 404


def test_expired_invitation_does_not_block_reinvite(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    _invite(client, org, "new@example.com")
    Invitation.objects.update(expires_at=timezone.now() - timezone.timedelta(minutes=1))
    _invite(client, org, "new@example.com")
    assert Invitation.objects.filter(revoked_at__isnull=True).count() == 1
    assert Invitation.objects.count() == 2


def test_member_and_viewer_cannot_invite(client, make_user, make_org, add_member):
    org = make_org()
    for role in ("member", "viewer", "manager"):
        user = make_user(email=f"{role}@example.com")
        add_member(org, user, role)
        client.force_login(user)
        assert _invite(client, org, f"x-{role}@example.com").status_code == 403
    assert not Invitation.objects.exists()


def test_admin_cannot_invite_admin_or_owner(make_user, make_org, add_member):
    org = make_org()
    admin = add_member(org, make_user(email="a@example.com"), "admin")
    for role in ("admin", "owner"):
        with pytest.raises(services.OrganizationError):
            services.invite_member(organization=org, actor_membership=admin,
                                   email=f"{role}@x.com", role=role)


def test_team_limit_enforced(make_user, make_org):
    org = make_org()
    FeatureOverride.objects.create(organization=org, feature_key="team.members",
                                   enabled=True, limit_value=2)
    owner = Membership.objects.get(organization=org, role="owner")
    services.invite_member(organization=org, actor_membership=owner, email="a@x.com",
                           role="member")
    with pytest.raises(services.OrganizationError):
        services.invite_member(organization=org, actor_membership=owner, email="b@x.com",
                               role="member")


def test_role_change_rules(client, make_user, make_org, add_member):
    org = make_org()
    admin = add_member(org, make_user(email="a@example.com"), "admin")
    admin2 = add_member(org, make_user(email="a2@example.com"), "admin")
    member = add_member(org, make_user(email="m@example.com"), "member")
    client.force_login(admin.user)
    url = lambda m: reverse("team_member_role", kwargs={"org_slug": org.slug, "member_id": m.pk})  # noqa: E731
    client.post(url(member), {"role": "manager"})
    member.refresh_from_db()
    assert member.role == "manager"
    client.post(url(member), {"role": "admin"})  # cannot grant own level
    member.refresh_from_db()
    assert member.role == "manager"
    client.post(url(admin2), {"role": "viewer"})  # cannot manage peers
    admin2.refresh_from_db()
    assert admin2.role == "admin"
    owner = Membership.objects.get(organization=org, role="owner")
    client.post(url(owner), {"role": "viewer"})
    owner.refresh_from_db()
    assert owner.role == "owner"


def test_remove_member_and_owner_protection(client, make_user, make_org, add_member):
    org = make_org()
    member = add_member(org, make_user(email="m@example.com"), "member")
    client.force_login(org.owner)
    client.post(reverse("team_member_remove", kwargs={"org_slug": org.slug,
                                                      "member_id": member.pk}))
    assert not Membership.objects.filter(pk=member.pk).exists()
    owner = Membership.objects.get(organization=org, role="owner")
    admin = add_member(org, make_user(email="a@example.com"), "admin")
    client.force_login(admin.user)
    client.post(reverse("team_member_remove", kwargs={"org_slug": org.slug,
                                                      "member_id": owner.pk}))
    assert Membership.objects.filter(pk=owner.pk).exists()


def test_owner_cannot_leave(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    client.post(reverse("team_leave", kwargs={"org_slug": org.slug}))
    assert Membership.objects.filter(organization=org, user=org.owner).exists()


def test_htmx_invite_returns_partial(client, make_org):
    org = make_org()
    client.force_login(org.owner)
    resp = client.post(reverse("team_invite", kwargs={"org_slug": org.slug}),
                       {"email": "h@example.com", "role": "member"}, HTTP_HX_REQUEST="true")
    body = resp.content.decode()
    assert resp.status_code == 200 and "h@example.com" in body and "<html" not in body
