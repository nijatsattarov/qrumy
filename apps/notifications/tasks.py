from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def send_email_task(self, *, to: str, subject: str, text: str, html: str = "") -> None:
    message = EmailMultiAlternatives(subject=subject, body=text,
                                     from_email=settings.DEFAULT_FROM_EMAIL, to=[to])
    if html:
        message.attach_alternative(html, "text/html")
    message.send()
