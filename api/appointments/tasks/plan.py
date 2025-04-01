from tasks.helpers import get_user
from tasks.queues import job
from utils.log import logger
from utils.mailchimp import (
    MAILCHIMP_API_KEY,
    MAILCHIMP_CAMPUS_SUBSCRIBERS_LIST,
    MAILCHIMP_CONSUMER_LIST,
    MailchimpClient,
    subscribe_to_mailchimp,
    unsubscribe_from_mailchimp,
)

log = logger(__name__)


SUBSCRIPTION_SUPPORT_EMAIL = "kaitlyn@mavenclinic.com"


@job(traced_parameters=("user_id",))
def post_subscribe_setup(user_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    user = get_user(user_id)
    if user:
        mc = MailchimpClient(MAILCHIMP_API_KEY)

        main_list_info = mc.subscriber_info_from_list(
            MAILCHIMP_CONSUMER_LIST, user.email
        )
        if main_list_info:
            log.info("Unsubscribing %s from MC consumer list", user)
            unsubscribe_from_mailchimp(user.email, MAILCHIMP_CONSUMER_LIST)

            log.info("Subscribing %s to MC campus subscriber list", user)
            subscribe_to_mailchimp(user, list_id=MAILCHIMP_CAMPUS_SUBSCRIBERS_LIST)
            log.info("All set subscribing %s to campus subscriber list", user)
        else:
            log.info("%s not in consumer list on MC", user)
