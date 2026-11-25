import json
from unittest import mock

import pytest
from django.core.mail import EmailMultiAlternatives
from django.test import override_settings


@override_settings(
    EMAIL_BACKEND="anymail.backends.resend.EmailBackend",
    ANYMAIL={"RESEND_API_KEY": "re_test_dummy"},
    DEFAULT_FROM_EMAIL="Qrumy <no-reply@qrumy.com>",
)
def test_resend_backend_sends_html_and_text():
    response = mock.Mock(status_code=200, headers={}, text=json.dumps({"id": "msg_123"}))
    response.json.return_value = {"id": "msg_123"}
    with mock.patch("requests.Session.request", return_value=response) as request:
        msg = EmailMultiAlternatives("Salam", "Mətn", to=["a@example.com"])
        msg.attach_alternative("<p>HTML</p>", "text/html")
        msg.send()
    call = request.call_args
    url = call.kwargs.get("url") or call.args[1]
    payload = json.loads(request.call_args.kwargs["data"])
    assert url == "https://api.resend.com/emails"
    assert request.call_args.kwargs["headers"]["Authorization"] == "Bearer re_test_dummy"
    assert payload["from"] == "Qrumy <no-reply@qrumy.com>" and payload["to"] == ["a@example.com"]
    assert payload["html"] == "<p>HTML</p>" and payload["text"] == "Mətn"


def test_settings_pick_resend_only_with_a_key(monkeypatch):
    import importlib

    import config.settings.base as base

    monkeypatch.setenv("RESEND_API_KEY", "re_dummy")
    monkeypatch.delenv("EMAIL_BACKEND", raising=False)
    try:
        assert importlib.reload(base).EMAIL_BACKEND == "anymail.backends.resend.EmailBackend"
        monkeypatch.setenv("RESEND_API_KEY", "")
        assert importlib.reload(base).EMAIL_BACKEND.endswith("console.EmailBackend")
    finally:
        monkeypatch.delenv("RESEND_API_KEY", raising=False)
        importlib.reload(base)


pytestmark = pytest.mark.django_db
