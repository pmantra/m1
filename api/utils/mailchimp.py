import os

import mailchimp

from braze import client
from utils.log import logger

log = logger(__name__)


MAILCHIMP_API_KEY = os.environ.get("MAILCHIMP_API_KEY", "foo-us1")
MC_GIVEAWAYS_API_KEY = os.environ.get("MC_GIVEAWAYS_API_KEY", "foooooo-us10")

MAILCHIMP_CONSUMER_LIST = os.environ.get(
    "MAILCHIMP_CONSUMER_LIST", "NO_MAILCHIMP_CONSUMER_LIST"
)
MAILCHIMP_BRAND_AMBASSADORS_LIST = os.environ.get(
    "MAILCHIMP_BRAND_AMBASSADORS_LIST", "NO_MAILCHIMP_BRAND_AMBASSADORS_LIST"
)
MAILCHIMP_CAMPUS_AMBASSADORS_LIST = os.environ.get(
    "MAILCHIMP_CAMPUS_AMBASSADORS_LIST", "NO_MAILCHIMP_CAMPUS_AMBASSADORS_LIST"
)
MAILCHIMP_CAMPUS_SUBSCRIBERS_LIST = os.environ.get(
    "MAILCHIMP_CAMPUS_SUBSCRIBERS_LIST", "NO_MAILCHIMP_CAMPUS_SUBSCRIBERS_LIST"
)


def add_group_to_email(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    email,
    group_name,
    grouping_name="User Segments",
    list_id=MAILCHIMP_CONSUMER_LIST,
    client=None,
):
    client = client or MailchimpClient(MAILCHIMP_API_KEY)

    subscriber = client.subscriber_info_from_list(list_id, email)
    if subscriber:
        client.ensure_member_has_group(subscriber, grouping_name, group_name)


def subscribe_to_mailchimp(user, list_id=MAILCHIMP_CONSUMER_LIST, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api = mailchimp.Mailchimp(kwargs.get("api_key", MAILCHIMP_API_KEY))

    merge_vars = {
        "FNAME": user.first_name,
        "LNAME": user.last_name,
        "ESP_ID": user.esp_id,
    }

    source = kwargs.get("source") or kwargs.get("MMERGE3")
    if source:
        merge_vars["MMERGE3"] = source

    if kwargs.get("last_child_birthday"):
        merge_vars["DAY1"] = kwargs.get("last_child_birthday")

    if kwargs.get("due_date"):
        merge_vars["DAY2"] = kwargs.get("due_date")

    if kwargs.get("welcome_email_series"):
        merge_vars["MERGE5"] = kwargs.get("welcome_email_series")

    if kwargs.get("invited_at"):
        merge_vars["INVITEDAT"] = kwargs["invited_at"]

    if kwargs.get("invite_id"):
        merge_vars["INVITEID"] = kwargs["invite_id"]

    if kwargs.get("invite_email"):
        merge_vars["EMAIL"] = kwargs["invite_email"]

    try:
        api.lists.subscribe(
            list_id,
            double_optin=False,
            send_welcome=False,
            update_existing=True,
            email={"email": user.email},
            merge_vars=merge_vars,
            email_type="html",
            replace_interests=True,
        )
        log.info("Successfully added %s to %s", user, list_id)
    except mailchimp.ListAlreadySubscribedError:
        log.info("%s is already subscribed to the list", user)
    except mailchimp.Error as e:
        log.error("A MailChimp error occurred for %s: %s - %s", user, e.__class__, e)
    except Exception as e:
        log.error(e)


def unsubscribe_from_mailchimp(email, list_id, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api = mailchimp.Mailchimp(kwargs.get("api_key", MAILCHIMP_API_KEY))

    try:
        api.lists.unsubscribe(
            list_id,
            email={"email": email},
            delete_member=kwargs.get("delete_member", False),
            send_goodbye=kwargs.get("send_goodbye", False),
            send_notify=kwargs.get("send_notify", False),
        )
        log.debug("%s is successfully unsubscribed from list %s", email, list_id)
    except mailchimp.ListDoesNotExistError:
        log.info("List %s does not exist", list_id)
    except mailchimp.EmailNotExistsError:
        log.info("Email %s does not exist in list %s", email, list_id)
    except mailchimp.ListNotSubscribedError:
        log.info("Email %s is not subscribed to list %s", email, list_id)
    except Exception as e:
        log.error(e)


def unsubscribe_user_from_mailchimp(user):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    mc = {
        MAILCHIMP_API_KEY: [MAILCHIMP_CONSUMER_LIST],
        MC_GIVEAWAYS_API_KEY: (
            MailchimpClient(MC_GIVEAWAYS_API_KEY)
            .subscriber_info_from_account(user.email)
            .keys()
        ),
    }
    for key, list_ids in mc.items():
        for list_id in list_ids:
            unsubscribe_from_mailchimp(
                email=user.email, list_id=list_id, api_key=key, delete_member=True
            )
    braze_client = client.BrazeClient()
    braze_client.delete_user(external_id=user.esp_id)


class MailchimpClient:
    def __init__(self, api_key):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.mc = mailchimp.Mailchimp(api_key)

    def subscriber_info_from_list(self, list_id, email_address):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            member = self.mc.lists.member_info(
                id=list_id, emails=[{"email": email_address}]
            )
        except mailchimp.Error as e:
            log.warning(
                "Problem getting member status for list <%s>: %s",
                list_id,
                email_address,
            )
            log.warning(e)
        else:
            if member["success_count"] == 1:
                return member["data"][0]
            else:
                log.debug("<%s> not in list <%s>", email_address, list_id)
                return {}

    def subscriber_info_from_account(self, email_address):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            lists = self.mc.lists.list()
        except mailchimp.Error as e:
            log.warning("Cannot get lists from Mailchimp: %s", e)
            return {}

        list_ids = [l["id"] for l in lists["data"]]
        log.debug("Checking list_ids: %s", list_ids)

        infos = {}
        for list_id in list_ids:
            subscriber = self.subscriber_info_from_list(list_id, email_address)
            if subscriber:
                infos[list_id] = subscriber

        log.info("Got %s infos for: %s", len(infos), email_address)
        return infos

    def ensure_member_has_group(self, member_info, grouping_name, group_name):  # type: ignore[no-untyped-def] # Function is missing a type annotation

        if member_info.get("status") != "subscribed":
            log.debug(
                "<%s> is not currently subscribed to <%s>, skipping...",
                member_info["email"],
                member_info["list_id"],
            )
            return

        for grouping in member_info.get("merges", {}).get("GROUPINGS", []):
            if grouping.get("name") == grouping_name:
                if group_name in [
                    g.get("name")
                    for g in grouping.get("groups", {})
                    if g.get("interested")
                ]:
                    log.debug(
                        "<%s> already in %s/%s in list <%s>",
                        member_info["email"],
                        grouping_name,
                        group_name,
                        member_info["list_id"],
                    )
                    return

        log.debug(
            "Adding <%s> to %s/%s in list <%s>",
            member_info["email"],
            grouping_name,
            group_name,
            member_info["list_id"],
        )

        merge_vars = {"groupings": [{"name": grouping_name, "groups": [group_name]}]}

        try:
            self.mc.lists.update_member(
                id=member_info["list_id"],
                email={"email": member_info["email"]},
                merge_vars=merge_vars,
                replace_interests=False,
            )
        except mailchimp.Error as e:
            log.warning(
                "Problem updating member status for group (%s) member: %s",
                group_name,
                member_info["email"],
            )
            log.warning(e)
            return

    def ensure_tag_exists_in_list(self, list_id, grouping_name, group_name=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        grouping_exists = False
        group_exists = False
        grouping_id = None
        if group_name is None:
            group_exists = True

        try:
            groupings = self.mc.lists.interest_groupings(list_id)
        except mailchimp.Error as e:
            log.warning("Problem getting groups for list: %s", list_id)
            log.warning(e)
            groupings = []

        for grouping in groupings:
            if grouping["name"] == grouping_name:
                grouping_exists = True
                grouping_id = grouping["id"]

                if group_name:
                    for group in grouping["groups"]:
                        if group["name"] == group_name:
                            group_exists = True

        if not grouping_exists:
            if not group_name:
                log.info(
                    "Cannot add grouping <%s> without one group name...", grouping_name
                )
                return False

            try:
                log.debug("Adding grouping <%s> to list <%s>", grouping_name, list_id)
                self.mc.lists.interest_grouping_add(
                    id=list_id, name=grouping_name, type="hidden", groups=[group_name]
                )
                grouping_exists = True
                group_exists = True
            except mailchimp.Error as e:
                log.warning("Problem adding grouping <%s>", grouping_name)
                log.warning(e)

        if not group_exists:
            try:
                log.info(
                    "Adding group <%s> to grouping <%s>", group_name, grouping_name
                )
                self.mc.lists.interest_group_add(
                    id=list_id, group_name=group_name, grouping_id=grouping_id
                )
                group_exists = True
            except mailchimp.Error as e:
                log.warning("Problem adding group <%s>", group_name)
                log.warning(e)

        return group_exists and grouping_exists

    def update_subscriber_attributes(self, list_id, email, merge_vars):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            result = self.mc.lists.update_member(
                id=list_id,
                email={"email": email},
                merge_vars=merge_vars,
                replace_interests=False,
            )
            return result
        except mailchimp.Error as e:
            log.warning("Problem updating attribute for subscriber %s", email)
            log.warning(e)
            return
        except Exception as e:
            log.error(e)
