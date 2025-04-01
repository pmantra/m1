from __future__ import absolute_import

import click

from airflow.utils import with_app_context
from incentives.models.incentive import IncentiveAction
from incentives.repository.incentive_fulfillment import IncentiveFulfillmentRepository
from models.tracks import TrackName
from storage.connection import db
from utils import braze
from utils.braze import BrazeUserOffboardingIncentives
from utils.log import logger

log = logger(__name__)


def delete_incentive_fulfillments(track: TrackName, action: IncentiveAction):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info("Finding incentive fulfillments")
    incentive_fulfillments_and_esp_ids = IncentiveFulfillmentRepository().get_all_by_params(
        track=track, action=IncentiveAction(action).name  # type: ignore[arg-type] # Argument "action" to "get_all_by_params" of "IncentiveFulfillmentRepository" has incompatible type "str"; expected "IncentiveAction"
    )
    log.info(
        f"Number of incentive_fulfillments that satisfy conditions: {len(incentive_fulfillments_and_esp_ids)}",
        track=track,
        action=action,
    )

    incentive_fulfillments = [
        inc_fuls[0] for inc_fuls in incentive_fulfillments_and_esp_ids
    ]
    for inc_ful in incentive_fulfillments:
        db.session.delete(inc_ful)

    # only return esp_ids
    return [inc_fuls[1] for inc_fuls in incentive_fulfillments_and_esp_ids]


def delete_incentive_fulfillments_wrapper(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    track: TrackName,
    action: IncentiveAction,
    dry_run: bool = False,
):
    try:
        log.info("\n=================================================")
        log.info(
            "Starting updates\n=================================================\n"
        )

        user_esp_ids = delete_incentive_fulfillments(track, action)
    except Exception as e:
        db.session.rollback()
        log.info("Got an exception while updating.", exception=e)  # noqa
        return

    if dry_run:
        log.info("Dry run requested. Rolling back changes.")  # noqa
        db.session.rollback()
        return

    log.info("Committing deletion of incentive fulfillment rows...")  # noqa
    db.session.commit()

    # updating braze
    braze_incentives = []
    for esp_ids in user_esp_ids:
        braze_incentives.append(
            BrazeUserOffboardingIncentives(
                incentive_id_offboarding=None,
                external_id=esp_ids,
            )
        )

    log.info("Sending incentive updates to Braze...")
    braze.send_incentives_offboarding(braze_incentives)

    log.info("Finished.")  # noqa


@click.command()
@click.option(
    "--track",
    required=True,
    prompt="Track name that will be used to find incentive fulfillment rows to delete",
    type=click.Choice([track.value for track in TrackName], case_sensitive=True),
)
@click.option(
    "--action",
    required=True,
    prompt="Incentive action name that will be used to find incentive fulfillment rows to delete",
    type=click.Choice(
        [action.value for action in IncentiveAction], case_sensitive=True
    ),
)
@click.option(
    "--dry-run",
    "-D",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
@with_app_context()
def main(track: TrackName, action: IncentiveAction, dry_run: bool = False):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    delete_incentive_fulfillments_wrapper(track, action, dry_run)


if __name__ == "__main__":
    main()
