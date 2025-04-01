import json
from contextlib import closing

import requests
from sqlalchemy.orm.exc import NoResultFound

from authn.models.user import User
from utils.mailchimp import MAILCHIMP_API_KEY, MAILCHIMP_CONSUMER_LIST, MailchimpClient


def load_subs():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # load subscribers via export API
    # https://apidocs.mailchimp.com/export/1.0/list.func.php
    dc = MAILCHIMP_API_KEY.split("-")[1]
    api_endpoint = (
        "https://{dc}.api.mailchimp.com/export/1.0/list" "?apikey={apikey}&id={id}"
    ).format(dc=dc, apikey=MAILCHIMP_API_KEY, id=MAILCHIMP_CONSUMER_LIST)

    subscribers = []
    with closing(requests.get(api_endpoint, stream=True)) as r:
        lines = r.iter_lines()  # iterator

        headers = json.loads(next(lines).decode("utf-8"))
        for line in lines:
            try:
                line = line.decode("utf-8")
            except UnicodeError as e:
                print(e, line)
                continue

            subscribers.append(dict(zip(headers, json.loads(line))))

    return subscribers


def update_subscriber_ab_group_assignments(subscribers):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    client = MailchimpClient(MAILCHIMP_API_KEY)
    for subscriber in subscribers:
        sub_email = subscriber["Email Address"]
        if subscriber.get("A/B Test Group") or subscriber.get("MMERGE10"):
            print("Skip %s, test group already assigned" % sub_email)
            continue
        try:
            user = User.query.filter(User.email == sub_email).one()
        except NoResultFound:
            print("email %s was not found." % sub_email)
            continue
        except Exception as e:
            print("Exception %s occurred for %s" % (e, subscriber))
            continue

        test_group = "a" if user.id % 2 else "b"
        result = client.update_subscriber_attributes(
            MAILCHIMP_CONSUMER_LIST, user.email, {"MMERGE10": test_group}
        )
        if result.get("email"):
            print(
                "A/B testing group %s assigned in MailChimp for %s" % (test_group, user)
            )
        else:
            print(result)


def main():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    print("Loading subscribers from mailchimp")
    subscribers = load_subs()
    print("Total %s subscribers loaded." % len(subscribers))
    update_subscriber_ab_group_assignments(subscribers)
    print("Done!")
