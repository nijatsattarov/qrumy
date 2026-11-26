import re
import time

import pytest
from django.core import mail, signing

from apps.marketing.contact import SALT
from apps.marketing.models import ContactMessage, ContactPage

pytestmark = pytest.mark.django_db


def _started(seconds_ago=10):
    return signing.dumps({"t": time.time() - seconds_ago}, salt=SALT)


def _post(client, url="/contact/", **extra):
    data = {"name": "Aysel", "email": "aysel@example.com", "topic": "sales",
            "message": "Pro plan?", "started": _started()}
    data.update(extra)
    return client.post(url, data)


def test_page_per_language_and_in_navigation(client):
    en = client.get("/contact/").content.decode()
    az = client.get("/az/contact/").content.decode()
    assert "Contact us" in en and "support@qrumy.com" in en and 'name="message"' in en
    assert "Bizimlə əlaqə" in az
    assert 'href="/contact/"' in client.get("/").content.decode()
    assert "/contact/" in client.get("/sitemap.xml").content.decode()


def test_edits_in_admin_show_on_page(client):
    page = ContactPage.objects.get(language="en")
    page.phone, page.whatsapp, page.form_enabled = "+994 12 555 00 00", "+994501234567", False
    page.save()
    body = client.get("/contact/").content.decode()
    assert "+994 12 555 00 00" in body and "https://wa.me/994501234567" in body
    assert 'name="message"' not in body


def test_message_saved_and_emailed(client, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        r = _post(client)
    assert r.status_code == 302
    msg = ContactMessage.objects.get()
    assert (msg.name, msg.topic, msg.language, msg.is_handled) == ("Aysel", "sales", "en", False)
    assert mail.outbox and mail.outbox[-1].to == ["support@qrumy.com"]
    assert "Aysel" in mail.outbox[-1].subject


def test_spam_protection(client):
    assert _post(client, website="http://spam").status_code == 200
    assert _post(client, started="forged").status_code == 200
    assert _post(client, started=_started(0)).status_code == 200  # too fast for a person
    assert _post(client, email="not-an-email").status_code == 200
    assert not ContactMessage.objects.exists()


def test_rate_limited(client, settings):
    settings.CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                   "LOCATION": "contact-rl"}}
    codes = [_post(client).status_code for _ in range(7)]
    assert codes[0] == 302 and codes[-1] in (403, 429)


def test_admin_pages(client, make_user):
    from allauth.mfa.models import Authenticator

    staff = make_user(email="s@example.com", is_staff=True, is_superuser=True)
    Authenticator.objects.create(user=staff, type=Authenticator.Type.TOTP, data={})
    client.force_login(staff)
    _post(client)
    for url in ("/qadmin/marketing/contactpage/", "/qadmin/marketing/contactmessage/"):
        assert client.get(url).status_code == 200
    page = ContactPage.objects.get(language="az")
    assert client.get(f"/qadmin/marketing/contactpage/{page.pk}/change/").status_code == 200
    assert re.search("Əlaqə", client.get("/qadmin/").content.decode())
