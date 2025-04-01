import click
from sqlalchemy import func

from authn.models.user import User
from common.services.api import chunk
from models.enterprise import OnboardingState, UserOnboardingState
from storage.connection import db
from utils import braze
from utils.braze import BrazeUserOnboardingState
from utils.log import logger

log = logger(__name__)

ONBOARDING_STATES_FOR_MARKETING_CAMPAIGN = (
    OnboardingState.USER_CREATED,
    OnboardingState.FAILED_ELIGIBILITY,
    OnboardingState.TRACK_SELECTION,
    OnboardingState.FAILED_TRACK_SELECTION,
)


def filter_by_useful_states(query):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    return query.filter(
        UserOnboardingState.state.in_(ONBOARDING_STATES_FOR_MARKETING_CAMPAIGN)
    )


def query_onboarding_state_counts():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    all_onboarding_state_count = db.session.query(
        func.count(UserOnboardingState.id)
    ).scalar()
    useful_onboarding_state_count = filter_by_useful_states(
        db.session.query(func.count(UserOnboardingState.id))
    ).scalar()
    return all_onboarding_state_count, useful_onboarding_state_count


def report_onboarding_states_to_braze(  # type: ignore[no-untyped-def] # Function is missing a type annotation
    dry_run, include_all_states, page_size, page_limit
):
    """
    Queries existing UserOnboardingState records to report to Braze as a backfill.

    `dry_run`: whether to actually send requests to Braze. If True, no requests will be sent
    `include_all_states`: whether the included states are filtered to the set of states being used in the relevant Marketing campaign
    `page_size`: the number of rows reported to Braze in a single request
    `page_limit`: the maximum number of pages to send, to prevent sending too many requests in QA environments
    """
    if dry_run:
        log.info(
            "Dry run of reporting onboarding states to Braze",
            include_all_states=include_all_states,
            page_size=page_size,
            page_limit=page_limit,
        )
    else:
        log.info(
            "Reporting onboarding states to Braze",
            include_all_states=include_all_states,
            page_size=page_size,
            page_limit=page_limit,
        )

    query = (
        db.session.query(UserOnboardingState.state, User.esp_id, User.email, User.id)
        .join(User, UserOnboardingState.user_id == User.id)
        .order_by(UserOnboardingState.user_id)
    )

    if not include_all_states:
        query = filter_by_useful_states(query)

    user_onboarding_states = query.all()
    db.session.commit()

    for page_number, page in enumerate(chunk(user_onboarding_states, page_size)):

        if not dry_run:
            mapped_user_onboarding_states = list(
                map(
                    lambda row: BrazeUserOnboardingState(
                        onboarding_state=row.state,
                        external_id=row.esp_id,
                    ),
                    page,
                )
            )
            braze.send_onboarding_states(mapped_user_onboarding_states)

        if page_limit and page_number >= page_limit - 1:
            log.info("Reached page limit, exiting", page_limit=page_limit)
            break
        log.info(f"Finished processing page number {page_number}")


def backfill(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    dry_run: bool = False,
    include_all_states: bool = False,
    page_limit: int = None,  # type: ignore[assignment] # Incompatible default for argument "page_limit" (default has type "None", argument has type "int")
    page_size: int = 50,
):
    log.info(
        "Running onboarding status backfill",
        dry_run=dry_run,
        include_all_states=include_all_states,
        page_limit=page_limit,
        page_size=page_size,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        if dry_run:
            (
                all_onboarding_state_count,
                useful_onboarding_state_count,
            ) = query_onboarding_state_counts()
            log.info(
                "Statistics on onboarding state",
                all_onboarding_state_count=all_onboarding_state_count,
                useful_onboarding_state_count=useful_onboarding_state_count,
            )

        report_onboarding_states_to_braze(
            dry_run, include_all_states, page_size, page_limit
        )


@click.command()
@click.option(
    "--dry_run",
    "-d",
    is_flag=True,
    help="Retrieves the data from the database without updating Braze",
)
@click.option(
    "--include_all_states",
    is_flag=True,
    help="Whether all states or just the campaign relevant states should be reported to Braze",
)
def main(dry_run: bool = False, include_all_states=False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    backfill(dry_run=dry_run, include_all_states=include_all_states)


if __name__ == "__main__":
    main()
