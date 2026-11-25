import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.billing.gateways import CheckoutUnavailable, ManualGateway, get_gateway
from apps.core import quotas
from apps.subscriptions.entitlements import get_entitlements, invalidate
from apps.subscriptions.models import FeatureOverride, Plan, Subscription

pytestmark = pytest.mark.django_db


def test_plans_seeded():
    assert set(Plan.objects.values_list("key", flat=True)) >= {
        "beta", "free", "starter", "growth", "business", "agency"}


def test_beta_entitlements(make_org):
    ent = get_entitlements(make_org())
    assert ent.can("module.qr") and ent.limit("team.members") == 10
    assert not ent.can("module.agency") and ent.limit("module.agency") == 0
    assert not ent.can("unknown.feature")


def test_override_takes_precedence_and_expires(make_org):
    org = make_org()
    ov = FeatureOverride.objects.create(organization=org, feature_key="team.members",
                                        limit_value=99)
    assert get_entitlements(org).limit("team.members") == 99
    ov.expires_at = timezone.now() - timezone.timedelta(days=1)
    ov.save()
    invalidate(org)
    assert get_entitlements(org).limit("team.members") == 10


def test_only_one_current_subscription(make_org):
    org = make_org()
    with pytest.raises(IntegrityError), transaction.atomic():
        Subscription.objects.create(organization=org, plan=Plan.objects.get(key="free"),
                                    started_at=timezone.now())


def test_manual_gateway_assigns_plan_and_audits(make_org, make_user):
    from apps.audit_logs.models import AuditLog

    org = make_org()
    staff = make_user(email="staff@example.com", is_staff=True)
    ManualGateway().assign_plan(organization=org, plan=Plan.objects.get(key="business"),
                                actor=staff, reason="pilot customer")
    invalidate(org)
    assert get_entitlements(org).plan.key == "business"
    assert Subscription.objects.for_org(org).filter(status="canceled").count() == 1
    assert AuditLog.objects.filter(action="admin.billing.plan_assigned").exists()


def test_manual_gateway_never_takes_payments(make_org):
    with pytest.raises(CheckoutUnavailable):
        get_gateway().start_checkout(organization=make_org(), plan=Plan.objects.get(key="growth"),
                                     interval="month", actor=None)


def test_quota_check(make_org):
    org = make_org()
    quotas.check(org, "team.members", current=9)
    with pytest.raises(quotas.QuotaExceeded):
        quotas.check(org, "team.members", current=10)


def test_billing_page_permissions(client, make_org, make_user, add_member):
    from django.urls import reverse

    org = make_org()
    url = reverse("billing", kwargs={"org_slug": org.slug})
    client.force_login(org.owner)
    assert client.get(url).status_code == 200
    member = make_user(email="m@example.com")
    add_member(org, member, "member")
    client.force_login(member)
    assert client.get(url).status_code == 403
