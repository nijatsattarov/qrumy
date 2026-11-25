import pytest
from allauth.account.models import EmailAddress

from apps.accounts.models import User
from apps.organizations.models import Membership
from apps.organizations.services import create_organization


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.STORAGES = {
        **settings.STORAGES,
        "private": {"BACKEND": "django.core.files.storage.FileSystemStorage",
                    "OPTIONS": {"location": str(tmp_path / "private"), "base_url": None}},
    }


@pytest.fixture(autouse=True)
def _clear_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


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


@pytest.fixture
def make_qr():
    from apps.qr_management import services
    from apps.qr_management.engine import QRStyle

    def _make(org, *, qr_type="url", mode="dynamic", name="Menu", payload=None, **kw):
        payload = payload or {"url": "https://example.com/menu"}
        return services.create_qr(organization=org, actor=org.owner, qr_type=qr_type, mode=mode,
                                  name=name, payload=payload, style=kw.pop("style", QRStyle()),
                                  verify=kw.pop("verify", False), **kw)

    return _make


@pytest.fixture
def make_survey():
    from apps.surveys import services
    from apps.surveys.models import Survey

    def _make(org, *, title="Feedback", publish=True, qtypes=("csat", "single", "longtext"),
              **fields):
        survey = services.create_survey(organization=org, actor=org.owner, title=title, **fields)
        for qtype in qtypes:
            services.add_question(survey=survey, qtype=qtype)
        if publish:
            services.publish(survey=survey, actor=org.owner)
        return Survey.objects.get(pk=survey.pk)

    return _make


@pytest.fixture
def make_asset():
    from apps.assets import services

    def _make(org, *, name="Coffee machine", **data):
        return services.create_asset(organization=org, actor=org.owner,
                                     data={"name": name, **data})

    return _make


@pytest.fixture
def jpeg_bytes():
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (40, 30), (200, 50, 50)).save(buf, "JPEG")
    return buf.getvalue()
