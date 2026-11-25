import pytest
from django.urls import reverse

from apps.accounts.legal import LegalDocument, TermsAcceptance, current
from apps.marketing.templatetags.legal import legal_markup

pytestmark = pytest.mark.django_db


def test_seeded_documents_published_in_both_languages():
    for kind in ("terms", "privacy"):
        for lang in ("en", "az"):
            doc = current(kind, lang)
            assert doc is not None and doc.language == lang and doc.version == "2026-11-25"
            assert doc.body.count("\n## ") >= 10


@pytest.mark.parametrize(
    "url,text",
    [
        ("/terms/", "Acceptable use"),
        ("/privacy/", "How long we keep data"),
        ("/az/terms/", "Qəbuledilən istifadə"),
        ("/az/privacy/", "Məlumatları nə qədər saxlayırıq"),
    ],
)
def test_legal_pages_render_headings(client, url, text):
    body = client.get(url).content.decode()
    assert "<h2>" in body and text in body and "<li>" in body


def test_signup_needs_terms_checkbox(client):
    data = {
        "full_name": "A",
        "email": "a@example.com",
        "password1": "a-strong-passphrase-1",
        "password2": "a-strong-passphrase-1",
    }
    page = client.get(reverse("account_signup")).content.decode()
    assert 'name="accept_terms"' in page and 'href="/terms/"' in page
    client.post(reverse("account_signup"), data)
    assert not TermsAcceptance.objects.exists()
    client.post(reverse("account_signup"), {**data, "accept_terms": "on"})
    assert TermsAcceptance.objects.get().terms_version == "2026-11-25"


def test_admin_edit_new_version_replaces_published_one(client):
    from django.utils import timezone

    LegalDocument.objects.create(
        kind="terms",
        language="en",
        version="2027-01-01",
        title="Terms v2",
        body="## Changed\nNew text.",
        published_at=timezone.now(),
    )
    assert "Terms v2" in client.get("/terms/").content.decode()


def test_legal_markup_escapes_html():
    html = legal_markup("## Head <b>\nline <script>x</script>\n- item & co\n\nPara")
    assert html == (
        "<h2>Head &lt;b&gt;</h2><p>line &lt;script&gt;x&lt;/script&gt;</p>"
        "<ul><li>item &amp; co</li></ul><p>Para</p>"
    )
