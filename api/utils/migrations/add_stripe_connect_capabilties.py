import stripe

from common.services.stripe import StripeConnectClient
from common.services.stripe_constants import PAYMENTS_STRIPE_API_KEY
from utils.log import logger

log = logger(__name__)


def get_connect_accounts(page_size=5, starting_after=None, dry_run=True):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    log.debug("Start Migration of Connect Accounts")
    stripe_client = StripeConnectClient(api_key=PAYMENTS_STRIPE_API_KEY)
    accounts_retrieved = 0
    total_accounts_modified = 0

    # get first page
    log.debug(f"Get {page_size} stripe accounts.", starting_after=None)
    initial_accounts = stripe.Account.list(
        limit=page_size, starting_after=starting_after, api_key=stripe_client.api_key
    )
    accounts_retrieved += len(initial_accounts)
    next_page_starts_after, accounts_modified = add_capabilities(
        stripe_client, initial_accounts, dry_run
    )
    total_accounts_modified += accounts_modified

    # get continuing pages
    while next_page_starts_after and next_page_starts_after.id:
        log.debug(
            f"Get {page_size} stripe accounts.",
            starting_after=next_page_starts_after.id,
        )
        accounts = stripe.Account.list(
            limit=page_size,
            starting_after=next_page_starts_after.id,
            api_key=stripe_client.api_key,
        )
        accounts_retrieved += len(accounts)
        last_account_retrieved, accounts_modified = add_capabilities(
            stripe_client, accounts, dry_run
        )
        total_accounts_modified += accounts_modified

        # Check if we've reached a new page or the end
        if last_account_retrieved and last_account_retrieved != next_page_starts_after:
            next_page_starts_after = last_account_retrieved
        else:
            next_page_starts_after = None
    log.debug(
        "End Migration of Connect Accounts",
        accounts_retrieved=accounts_retrieved,
        accounts_modified=total_accounts_modified,
    )
    return True


def add_capabilities(stripe_client, accounts, dry_run):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    account = None
    accounts_modified = 0
    for account in accounts:
        # TODO: move to RBAC permissions instead
        if "transfers" in account.capabilities:
            log.debug(f"Account {account.id} has the transfer capability.")
        else:
            log.debug(f"Updating account {account.id}.")
            if not dry_run:
                stripe.Account.modify(
                    account.id,
                    requested_capabilities=["transfers"],
                    api_key=stripe_client.api_key,
                )
            accounts_modified += 1
    return account, accounts_modified
