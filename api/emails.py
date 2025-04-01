from dateutil.relativedelta import relativedelta
from flask import current_app, render_template

from braze import client
from common import stats
from utils import mail, security
from utils.log import logger

log = logger(__name__)


def confirm_email(to_email, first_name=None, source: str = "ios") -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    token = security.new_confirm_email_token(to_email)

    context = {
        "email": to_email,
        "token": token,
        "first_name": first_name,
        "base_url": current_app.config["BASE_URL"],
    }

    if "web" == source:
        text_tpl = "mail/welcome_web_text.j2"
        html_tpl = "mail/welcome_web_html.j2"
    elif "android" == source:
        text_tpl = "mail/welcome_android_text.j2"
        html_tpl = "mail/welcome_android_html.j2"
    else:
        text_tpl = "mail/welcome_text.j2"
        html_tpl = "mail/welcome_html.j2"

    text = render_template(text_tpl, **context)
    html = render_template(html_tpl, **context)

    mail.send_message(
        to_email,
        subject=f"Welcome to Maven, {first_name}",
        reply_to="support@mavenclinic.com",
        html=html,
        text=text,
        from_name="Maven",
    )
    log.info(f"Sent confirm email to {to_email}")


def transfer_complete(invoices, amount, entries):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not invoices:
        log.warning("No invoices exist. Won't notify of transfer complete.")
        return

    practitioner = invoices[0].practitioner
    if not practitioner:
        log.warning(
            "No practitioner set in the invoice. Won't notify of transfer complete.",
            invoices=[invoices],
        )
        return
    else:
        log.info("Sending transfer_complete email to", practitioner_id=practitioner.id)

    invoice_month = "Unknown"
    # this should be for the previous month
    if invoices[0].started_at:
        invoice_month = invoices[0].started_at - relativedelta(months=1)
        invoice_month = invoice_month.strftime("%B")  # type: ignore[attr-defined] # "str" has no attribute "strftime"

    subject = f"You just received ${amount:,.2f} from Maven"

    active_contract = practitioner.practitioner_profile.active_contract
    if active_contract:
        show_entries = active_contract.emits_fees
    else:
        log.warning("Fallback to using is_staff", practitioner_id=practitioner.id)
        show_entries = not practitioner.practitioner_profile.is_staff

    context = {
        "entries": entries,
        "amount": amount,
        "practitioner": practitioner,
        "invoice_month": invoice_month,
        "show_entries": show_entries,
    }
    log.info("Context for email ready", context=context)
    text = render_template("mail/transfer_complete_text.j2", **context)
    html = render_template("mail/transfer_complete_html.j2", **context)

    headers = {"X-MC-Template": "prac-2018|main-content"}
    try:
        braze_client = client.BrazeClient()
        braze_email = client.BrazeEmail(
            external_ids=[practitioner.esp_id],
            app_id=client.constants.BRAZE_WEB_APP_ID,  # type: ignore[arg-type] # Argument "app_id" to "BrazeEmail" has incompatible type "Optional[str]"; expected "str"
            from_=mail.PROVIDER_FROM_EMAIL,
            reply_to=mail.PROVIDER_REPLY_EMAIL,
            subject=subject,
            body=html,
            plaintext_body=text,
            headers=headers,
        )
        message_dispatch_id = braze_client.send_email(
            email=braze_email,
            recipient_subscription_state="all",  # Include unsubscribed users
        )
        log.info(
            "Sent transfer_complete email.",
            practitioner_id=practitioner.id,
            message_dispatch_id=message_dispatch_id,
        )
    except Exception as e:
        log.error(
            "Sending transfer_complete email failed.",
            practitioner_id=practitioner.id,
            exception=e,
        )
        stats.increment(
            metric_name="api.emails.transfer_complete.failed",
            pod_name=stats.PodNames.PAYMENTS_POD,
        )


def gift_receipt(sender_email, sender_name, amount, paid_amount, recipient_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    subject = "Thanks for your purchase!"

    context = {
        "sender_name": sender_name,
        "paid_amount": paid_amount,
        "amount": amount,
        "recipient_name": recipient_name,
    }
    text = render_template("mail/gift_receipt_text.j2", **context)
    html = render_template("mail/gift_receipt_html.j2", **context)

    headers = {"X-MC-Template": "member-2018|main-content"}
    mail.send_message(
        sender_email,
        subject=subject,
        html=html,
        text=text,
        headers=headers,
        from_email="support@mavenclinic.com",
    )


def gift_delivery(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    recipient_email, recipient_name, sender_name, amount, paid_amount, message, code
):
    subject = "Here's your code"

    context = {
        "sender_name": sender_name,
        "amount": amount,
        "paid_amount": paid_amount,
        "message": message,
        "recipient_name": recipient_name,
        "base_url": current_app.config["BASE_URL"],
        "code": code,
    }
    text = render_template("mail/gift_delivery_text.j2", **context)
    html = render_template("mail/gift_delivery_html.j2", **context)

    headers = {"X-MC-Template": "member-2018|main-content"}
    mail.send_message(
        recipient_email,
        subject=subject,
        html=html,
        text=text,
        headers=headers,
        from_name="Maven",
        from_email="support@mavenclinic.com",
    )


def practitioner_dosespot_link(practitioner, link):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    context = {"link": link}
    text = render_template("mail/practitioner_dosespot_link.j2", **context)
    mail.send_message(
        practitioner.get("email"),
        subject="Maven Clinic Electronic Prescription Link",
        text=text,
    )
    log.debug(f"All set with practitioner_dosespot_link for User: ({practitioner.id})")


def follow_up_reminder_email(profile):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    care_coordinators = profile.user.care_coordinators
    if not care_coordinators:
        log.warning(
            f"No care coordinators found for user id: {profile.user_id}. Skipping "
            "follow up reminder email."
        )
        return

    log.debug(f"Sending follow up reminder email for member profile {profile}")
    mail.send_message(
        care_coordinators[0].email,
        subject="Follow-up Reminder",
        text=f"User id: {profile.user_id}",
        reply_to="support@mavenclinic.com",
    )
