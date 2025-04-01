import datetime
import os

from apns_clerk import APNs
from apns_clerk import Message as APNSMessage
from apns_clerk import Session

from utils.log import logger

log = logger(__name__)


CERTIFICATES = {
    "forum": os.environ.get("APNS_CERTIFICATE", "secrets/forum.pem"),
    "member": os.environ.get("APNS_CERTIFICATE", "secrets/member.pem"),
    "practitioner": os.environ.get("APNS_CERTIFICATE", "secrets/practitioner.pem"),
}

base_url = os.environ.get("BASE_URL")

# TODO: we should disable this in a dev context
if base_url in (
    "https://www.qa1.mvnapp.net",
    "https://www.qa2.mvnapp.net",
    "https://www.staging.mvnapp.net",
    "https://www.mavenclinic.com",
):
    session = Session()
else:
    log.debug("We are testing - no APNS needed")


def apns_send_bulk_message(device_ids, alert, application_name="forum", **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        message = APNSMessage(device_ids, alert=alert, **kwargs)
        send_result = apns_send_message_object(message, application_name)
        log.info(
            "Successfully sent apns",
            device_ids=device_ids,
            application_name=application_name,
        )
        return send_result
    except Exception as e:
        log.warning(
            "Problem sending notification via APNS to %s. Error: %s. Application_name: %s",
            device_ids,
            e,
            application_name,
        )


def apns_send_message_object(message, application_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        srv = _get_apns_service_connection(application_name)
        return srv.send(message)
    except Exception as e:
        log.warning(
            "Problem sending notification via APNS for %s. Error: %s. Application_name: %s",
            message,
            e,
            application_name,
        )


def _get_apns_service_connection(application_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    # Expunge connections older than an hour from the pool
    delta = datetime.timedelta(minutes=60)

    cert_file = CERTIFICATES.get(application_name)
    log.debug("send - cert_file: %s", cert_file)

    session.outdate(delta)
    con = session.get_connection("push_production", cert_file=cert_file)

    return APNs(con)


def apns_fetch_inactive_ids(application_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    cert_file = CERTIFICATES.get(application_name)
    log.debug("inactive - cert_file: %s", cert_file)

    session = Session()
    con = session.new_connection("feedback_production", cert_file=cert_file)
    srv = APNs(con)

    inactive = []
    for (
        token,
        when,  # noqa  B007  TODO:  Loop control variable 'when' not used within the loop body. If this is intended, start the name with an underscore.
    ) in srv.feedback():
        inactive.append(token)

    return inactive
