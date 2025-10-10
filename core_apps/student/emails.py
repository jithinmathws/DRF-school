from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.translation import gettext_lazy as _
from loguru import logger
from core_apps.student import models as StudentModel


def send_student_creation_email(user, student):
    subject = _("Your New Student Account has been Created")
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    context = {"user": user, "student": student, "site_name": settings.SITE_NAME}
    html_email = render_to_string("emails/student_created.html", context)
    plain_email = strip_tags(html_email)
    email = EmailMultiAlternatives(subject, plain_email, from_email, recipient_list)
    email.attach_alternative(html_email, "text/html")
    try:
        email.send()
        logger.info(f"Student Created email sent to: {user.email}")
    except Exception as e:
        logger.error(
            f"Failed to send student created email to {email}: Error: {str(e)}"
        )
