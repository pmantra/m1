from __future__ import annotations

import datetime
import os
import smtplib
import ssl
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from flask import current_app

from common.constants import Environment
from utils import cache
from utils.error_handler import retry_action
from utils.log import logger

log = logger(__name__)

FROM_EMAIL = "hello@mavenclinic.com"
PRACTITIONER_SUPPORT_EMAIL = "kaitlyn@mavenclinic.com"
PROVIDER_FROM_EMAIL = "providers@hello.mavenclinic.com"
PROVIDER_REPLY_EMAIL = "providers@mavenclinic.com"
# retry all SMTPException based exceptions and SSL errors
EMAIL_RETRYABLE_ERRORS = (smtplib.SMTPException, ssl.SSLError)


RATE_LIMIT_PER_HOUR = 10


def alert_admin(text_content, alert_emails=None, subject=None, production_only=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    alert_emails = alert_emails or ["backend@mavenclinic.com"]
    subject = subject or "Bad Data Results :)"

    for email in alert_emails:
        send_message(
            email,
            subject,
            text=text_content,
            internal_alert=True,
            production_only=production_only,
        )


def send_message(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    to_email: str,
    subject: str,
    html=None,
    text: str | None = None,
    headers: dict | None = None,
    from_email: str = FROM_EMAIL,
    from_name: str | None = None,
    reply_to: str | None = None,
    ical=None,
    csv_attachments=None,
    internal_alert=None,
    production_only=False,
) -> None:
    """
    Compose an email according to the parameters and send it via MailChimp SMTP.

    :param to_email:
    :param subject:
    :param html:
    :param text:
    :param headers:
    :param from_email:
    :param from_name:
    :param ical: iCalendar file content
    :param csv_attachments: list of tuples (filename, csv_data)
    :param internal_alert: will send using google smtp relay instead of mandrill
    :param production_only: will send only in production environments, (e.g. not QA)
    """
    headers = headers or {}

    if Environment.current() != Environment.PRODUCTION:
        if production_only:
            log.info(
                f"skipping sending email in non-production environment: {to_email}, {subject}"
            )
            return
        subject = f"{os.environ.get('ENVIRONMENT')}: {subject}"

    redis = cache.redis_client()
    rate_limit_key = f"emails:rate_limiter:{to_email}"

    try:
        emails_sent = int(redis.get(rate_limit_key))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
    except Exception as e:
        log.info(
            "Could not get email rate limit for %s, setting to 0", to_email, exception=e
        )
        emails_sent = 0

    if emails_sent > RATE_LIMIT_PER_HOUR:
        log.info("%s is over the email rate limit!", to_email)
        return

    # Create message container - the correct MIME type
    # is multipart/alternative.
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject

    if from_name is None:
        msg["From"] = from_email
    if from_name and from_email:
        msg["From"] = formataddr((from_name, from_email))
    if from_email is None:
        log.warning("Need a from_email to send!!")
        return

    if reply_to:
        msg["Reply-To"] = reply_to

    msg["To"] = to_email

    try:
        for k, v in headers.items():
            msg[k] = v
    except Exception as e:
        log.warning("Problem adding %s to %s", headers, msg, exception=e)

    # Preferred format last: iCalendar, Text, HTML
    # https://en.wikipedia.org/wiki/MIME#Alternative
    if ical:
        ical_part = MIMEText(ical, _subtype="calendar", _charset="utf-8")
        msg.attach(ical_part)

        ical_attachment = MIMEApplication(
            ical, _subtype="ics", name="maven_appointment.ics"
        )
        ical_attachment.add_header(
            "Content-Disposition", "attachment", filename="maven_appointment.ics"
        )
        msg.attach(ical_attachment)

    if csv_attachments:
        for filename, csv_data in csv_attachments:
            attachment = MIMEText(csv_data, _subtype="csv")
            attachment.add_header(
                "Content-Disposition", "attachment", filename=filename
            )
            msg.attach(attachment)

    if text:
        part1 = MIMEText(text, "plain")
        msg.attach(part1)
    if html:
        part2 = MIMEText(html, "html")
        msg.attach(part2)

    if not (text or html):
        log.warning("Need at least one of html or text to send an email!")
    else:
        if current_app.config["DEBUG"] or current_app.config["TESTING"]:
            log.info("Would have sent an email to: %s", msg["To"])
            log.debug(f"Email Raw is: \n{msg}")
        else:
            log.info("Sending an email to %s with subject %s", to_email, subject)
            try:
                if internal_alert:
                    _send_email_via_gmail(msg)
                else:
                    _send_email_via_mandrill(msg)
            except UnicodeEncodeError as e:
                log.warning(e)

            try:
                # expire every hour on the hour
                redis.setex(
                    rate_limit_key,
                    (60 * (60 - datetime.datetime.utcnow().minute)),
                    (emails_sent + 1),
                )
            except Exception as e:
                log.info(
                    "Could not set rate_limit_key for email for %s",
                    to_email,
                    exception=e,
                )


@retry_action(EMAIL_RETRYABLE_ERRORS)
def _send_email_via_mandrill(msg):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if os.environ.get("TESTING"):
        log.debug("in testing mode, not sending email...")
        return

    s = smtplib.SMTP("smtp.mandrillapp.com", 2525)
    s.starttls()

    try:
        s.login(os.environ["MANDRILL_USER"], os.environ["MANDRILL_PASSWORD"])
    except Exception as e:
        log.info("Cannot send email - cannot login to mandrill!", exception=e)
    else:
        to_addr = msg["To"]
        if "," in to_addr:
            to_addr = list(map(str.strip, to_addr.split(",")))
        s.sendmail(msg["From"], to_addr, msg.as_string())
        s.quit()


@retry_action(EMAIL_RETRYABLE_ERRORS)
def _send_email_via_gmail(msg):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if os.environ.get("TESTING"):
        log.debug("In testing mode, not sending email...")
        return

    s = smtplib.SMTP("smtp-relay.gmail.com", 587)
    s.starttls()

    try:
        s.login(
            os.environ.get("GOOGLE_SMTP_USERNAME", "hello@mavenclinic.com"),
            os.environ["GOOGLE_SMTP_PASSWORD"],
        )
    except Exception as e:
        log.info("Cannot send email - cannot login to gmail!", exception=e)
    else:
        to_addr = msg["To"]
        if "," in to_addr:
            to_addr = list(map(str.strip, to_addr.split(",")))
        s.sendmail(msg["From"], to_addr, msg.as_string())
        s.quit()
