import pytest
from allauth.account.models import EmailAddress

from apps.accounts.models import User
from apps.organizations.models import Membership
from apps.organizations.services import create_organization


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def make_user(db):
    def _make(email="user@example.com", password="correct-horse-battery", verified=True, **kw):
        user = User.objects.create_user(email=email, password=password,
                                        full_name=kw.pop("full_name", "Test User"), **kw)
        EmailAddress.objects.create(user=user, email=user.email, verified=verified, primary=True)
        return user

    return _make


@pytest.fixture
def make_org(make_user):
    def _make(name="Acme", owner=None):
        owner = owner or make_user(email=f"owner-{name.lower().replace(' ', '')}@example.com")
        return create_organization(owner=owner, name=name)

    return _make


@pytest.fixture
def add_member():
    def _add(org, user, role="member"):
        return Membership.objects.create(organization=org, user=user, role=role)

    return _add
