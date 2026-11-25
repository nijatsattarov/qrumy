"""Tenant isolation suite.

1. Every URL that takes ``org_slug`` is requested by a signed-in user of another
   organization → must be 404 (GET and POST).
2. Routes that take object IDs are attacked with *another* org's objects while using the
   attacker's own slug → must be 404 and leave data untouched.
3. Coverage guard: any new org-scoped route with extra URL kwargs must be listed in
   ``OBJECT_ROUTES_COVERED`` (and get an attack test), or this suite fails.
"""

import pytest
from django.urls import URLPattern, URLResolver, get_resolver, reverse

from apps.organizations.models import Invitation, Membership

pytestmark = pytest.mark.django_db

OBJECT_ROUTES_COVERED = {"team_member_role", "team_member_remove", "team_invitation_revoke"}


def _org_routes():
    routes = []

    def walk(patterns, prefix=""):
        for p in patterns:
            if isinstance(p, URLResolver):
                walk(p.url_patterns, prefix + str(p.pattern))
            elif isinstance(p, URLPattern) and p.name:
                full = prefix + str(p.pattern)
                if "<slug:org_slug>" in full:
                    routes.append((p.name, full))

    walk(get_resolver().url_patterns)
    return routes


def _extra_kwargs(route: str) -> list[str]:
    import re

    return [k for k in re.findall(r"<(?:\w+:)?(\w+)>", route) if k != "org_slug"]


@pytest.fixture
def two_orgs(make_user, make_org, add_member):
    victim = make_org("Victim")
    attacker_org = make_org("Attacker")
    attacker = attacker_org.owner
    return victim, attacker_org, attacker


def test_routes_were_discovered():
    names = {n for n, _ in _org_routes()}
    assert {"dashboard", "team", "billing", "organization_settings"} <= names


def test_foreign_org_slug_is_404_for_every_route(client, two_orgs):
    victim, _, attacker = two_orgs
    client.force_login(attacker)
    for name, route in _org_routes():
        kwargs = {"org_slug": victim.slug, **dict.fromkeys(_extra_kwargs(route), 1)}
        url = reverse(name, kwargs=kwargs)
        assert client.get(url).status_code == 404, url
        assert client.post(url, {}).status_code == 404, url


def test_every_object_route_has_an_attack_test():
    uncovered = {n for n, r in _org_routes() if _extra_kwargs(r)} - OBJECT_ROUTES_COVERED
    assert not uncovered, f"Add isolation tests for: {sorted(uncovered)}"


def test_cannot_change_role_of_foreign_member(client, two_orgs, make_user, add_member):
    victim, attacker_org, attacker = two_orgs
    target = add_member(victim, make_user(email="t@example.com"), "member")
    client.force_login(attacker)
    for name, data in (("team_member_role", {"role": "viewer"}), ("team_member_remove", {})):
        url = reverse(name, kwargs={"org_slug": attacker_org.slug, "member_id": target.pk})
        assert client.post(url, data).status_code == 404
    target.refresh_from_db()
    assert target.role == "member"


def test_cannot_revoke_foreign_invitation(client, two_orgs):
    from apps.organizations.services import invite_member

    victim, attacker_org, attacker = two_orgs
    inv, _ = invite_member(organization=victim, email="x@example.com", role="member",
                           actor_membership=Membership.objects.get(organization=victim,
                                                                   role="owner"))
    client.force_login(attacker)
    url = reverse("team_invitation_revoke",
                  kwargs={"org_slug": attacker_org.slug, "invitation_id": inv.pk})
    assert client.post(url).status_code == 404
    assert Invitation.objects.get(pk=inv.pk).revoked_at is None


def test_team_page_lists_only_own_members(client, two_orgs):
    victim, attacker_org, attacker = two_orgs
    client.force_login(attacker)
    body = client.get(reverse("team", kwargs={"org_slug": attacker_org.slug})).content.decode()
    assert victim.owner.email not in body


def test_org_switcher_lists_only_own_orgs(client, two_orgs):
    victim, attacker_org, attacker = two_orgs
    client.force_login(attacker)
    body = client.get(reverse("dashboard", kwargs={"org_slug": attacker_org.slug})).content
    assert b"Victim" not in body


def test_for_org_requires_organization():
    from apps.subscriptions.models import Subscription

    with pytest.raises(ValueError):
        Subscription.objects.for_org(None)
