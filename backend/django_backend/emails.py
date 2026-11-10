from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def _send_email(
    *,
    subject: str,
    to_email: str,
    text_template: str,
    html_template: str,
    context: dict,
) -> None:
    render_context = {"frontend_url": settings.FRONTEND_URL, **context}
    text_body = render_to_string(text_template, render_context).strip() + "\n"
    html_body = render_to_string(html_template, render_context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def send_invitation_email(to_email: str, otp: str, role: str, department: str) -> None:
    _send_email(
        subject="You're invited to Intradoc AI",
        to_email=to_email,
        text_template="emails/invitation.txt",
        html_template="emails/invitation.html",
        context={"otp": otp, "role": role, "department": department},
    )


def send_password_reset_email(to_email: str, otp: str) -> None:
    _send_email(
        subject="Your Intradoc AI password reset code",
        to_email=to_email,
        text_template="emails/password_reset.txt",
        html_template="emails/password_reset.html",
        context={"otp": otp},
    )
