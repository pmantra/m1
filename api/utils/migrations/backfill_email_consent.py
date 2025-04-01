from __future__ import annotations

import dataclasses
import datetime
import os

import click
import requests

from authn.domain.repository import UserRepository
from braze.client import constants
from models.profiles import MemberProfile
from preferences import models, service
from storage.connection import db
from utils.log import logger

log = logger(__name__)


user_repository = UserRepository()
preference_service = service.PreferenceService()
member_preferences_service = service.MemberPreferencesService()

API_KEY = os.environ.get("BRAZE_API_KEY")
UNSUBSCRIBES_ENDPOINT = f"{constants.API_ENDPOINT}/email/unsubscribes"

DEFAULT_BATCH_SIZE = 1_000


def get_unsubscribes_from_braze(
    offset: int = 0, limit: int = 500
) -> [BrazeUnsubscribeResponseEmail]:  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
    log.info(
        "Fetching unsubscribes from Braze API.",
        braze_endpoint=UNSUBSCRIBES_ENDPOINT,
        offset=offset,
    )

    emails = []
    if not API_KEY:
        log.warning("Skipping Braze API request in environment without an api key.")
        return emails

    try:
        resp = requests.get(
            UNSUBSCRIBES_ENDPOINT,
            headers={
                "Content-type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
            },
            params={  # type: ignore[arg-type] # Argument "params" to "get" has incompatible type "Dict[str, object]"; expected "Optional[Union[SupportsItems[Union[str, bytes, int, float], Union[str, bytes, int, float, Iterable[Union[str, bytes, int, float]], None]], Tuple[Union[str, bytes, int, float], Union[str, bytes, int, float, Iterable[Union[str, bytes, int, float]], None]], Iterable[Tuple[Union[str, bytes, int, float], Union[str, bytes, int, float, Iterable[Union[str, bytes, int, float]], None]]], str, bytes]]"
                "limit": limit,
                "offset": offset,
                "start_date": "2010-01-01",
                "end_date": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
                "sort_direction": "asc",
            },
            timeout=15,
        )
        resp.raise_for_status()
        json_ = resp.json()
        for email in json_["emails"]:
            emails.append(BrazeUnsubscribeResponseEmail(**email))
        return emails
    except requests.HTTPError as http_e:
        log.error(
            "Braze API request failed.",
            braze_endpoint=UNSUBSCRIBES_ENDPOINT,
            exception=http_e,
        )
        raise http_e
    except Exception as e:
        log.error(
            "Braze API request failed.",
            braze_endpoint=UNSUBSCRIBES_ENDPOINT,
            exception=e,
        )
        raise e


def get_unsubscribe_insert_statements(
    preference: models.Preference,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> [InsertDataRow]:  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
    """
    Call the Braze API to get users who unsubscribed.
    """
    log.info("Calling Braze to find users who unsubscribed")

    # this is the maximum number of results Braze will return in a single call to its endpoint
    braze_request_limit = 500

    offset = 0
    rows = []
    while True:
        email_objs = get_unsubscribes_from_braze(
            offset=offset,
            limit=min(braze_request_limit, batch_size),
        )
        for email_obj in email_objs:
            email_obj: BrazeUnsubscribeResponseEmail  # type: ignore[no-redef] # Name "email_obj" already defined on line 100

            # look up the user by email
            user = user_repository.get_by_email(email=email_obj.email)
            if not user:
                log.warn("Could not find user by email", email=email_obj.email)
                continue

            # If user does not have a MemberPreference for email comms,
            # create a MemberPreference and set the value to false
            existing_member_pref = member_preferences_service.get_by_preference_name(
                member_id=user.id,
                preference_name=preference.name,
            )
            if not existing_member_pref:
                current_time = datetime.datetime.utcnow()
                rows.append(
                    InsertDataRow(
                        member_id=str(user.id),
                        preference_id=str(preference.id),
                        value="false",
                        created_at=current_time,
                        modified_at=current_time,
                    )
                )

        if len(email_objs) < braze_request_limit:
            break
        else:
            offset += len(email_objs)

    return rows


def get_opted_in_insert_statements(
    preference: models.Preference,
    unsubscribed_user_ids: [int],  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> [InsertDataRow]:  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
    log.info("Finding users who did not unsubscribe")
    query = db.session.query(MemberProfile.user_id).filter(
        MemberProfile.user_id.notin_(unsubscribed_user_ids)
    )

    current_time = datetime.datetime.utcnow()

    batch_num = 0
    batch = query.limit(batch_size).all()
    to_add = []
    while batch:
        last_id = batch[-1].user_id
        batch_num += 1

        for opted_in_user in batch:
            row = InsertDataRow(
                member_id=str(opted_in_user[0]),
                preference_id=str(preference.id),
                value="true",
                created_at=current_time,
                modified_at=current_time,
            )
            to_add.append(row)

        if len(to_add) >= batch_size:
            yield to_add
            to_add = []
        else:
            log.debug("Still building batch...", batch=batch_num, size=len(batch))

        # Pull in the next batch
        batch = query.filter(MemberProfile.user_id > last_id).limit(batch_size).all()
    if to_add:
        yield to_add


def insert_in_batches(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    batch: list[InsertDataRow], batch_size: int = DEFAULT_BATCH_SIZE, batch_num: int = 0
):
    session = db.session().using_bind("default")

    inserts = [dataclasses.asdict(insert_) for insert_ in batch]

    start_idx = 0
    num_inserts = len(inserts)
    for _ in range(start_idx, num_inserts, batch_size):
        batch_num += 1
        end_idx = min(start_idx + batch_size, num_inserts)
        batch_inserts = inserts[start_idx:end_idx]
        num_batch_inserts = len(batch_inserts)

        log.info(
            "Inserting rows",
            batch_num=batch_num,
            num_rows=num_batch_inserts,
            start_idx=start_idx,
            end_idx=end_idx,
        )
        session.execute(
            """
            SET @@local.net_read_timeout=360;
            INSERT INTO `member_preferences` (member_id, preference_id, value, created_at, modified_at)
            VALUES (:member_id, :preference_id, :value, :created_at, :modified_at)
            ON DUPLICATE KEY UPDATE
                `member_id`=VALUES(`member_id`),
                `preference_id`=VALUES(`preference_id`),
                `value`=VALUES(`value`),
                `modified_at`=VALUES(`modified_at`)
            """,
            params=batch_inserts,
        )
        log.info(
            "Inserted rows",
            batch_num=batch_num,
            num_rows=num_batch_inserts,
            start_idx=start_idx,
            end_idx=end_idx,
        )

        start_idx = end_idx


def backfill_preferences(batch_size: int = DEFAULT_BATCH_SIZE):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    # Create the `opted_in_email_communications` Preference if it doesn't exist
    opt_in_email_pref = preference_service.get_by_name(
        name="opted_in_email_communications"
    )
    if not opt_in_email_pref:
        opt_in_email_pref = preference_service.create(
            name="opted_in_email_communications",
            default_value="false",
            type="bool",
        )

    unsubscribe_inserts: [InsertDataRow] = get_unsubscribe_insert_statements(  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
        preference=opt_in_email_pref
    )
    insert_in_batches(batch=unsubscribe_inserts, batch_size=batch_size)

    unsubscribed_user_ids = [
        unsubscribe_insert.member_id for unsubscribe_insert in unsubscribe_inserts
    ]

    opt_in_inserts: [InsertDataRow] = get_opted_in_insert_statements(  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
        preference=opt_in_email_pref, unsubscribed_user_ids=unsubscribed_user_ids
    )
    batch_num = 0
    for opt_in_inserts_batch in opt_in_inserts:
        insert_in_batches(
            batch=opt_in_inserts_batch, batch_size=batch_size, batch_num=batch_num
        )
        batch_num += 1


def backfill(dry_run: bool = False, batch_size: int = DEFAULT_BATCH_SIZE):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    log.info(
        "Running email opt-in preference backfill.",
        dry_run=dry_run,
    )
    from app import create_app

    with create_app(task_instance=True).app_context():
        try:
            with db.session.no_autoflush:
                backfill_preferences(batch_size=batch_size)
        except Exception as e:
            db.session.rollback()
            log.exception("Got an exception while backfilling.", exception=e)
            return

        if dry_run:
            log.info("Dry run requested. Rolling back changes.")
            db.session.rollback()
            return

        log.info("Committing changes...")
        db.session.commit()
        log.info("Finished.")


@dataclasses.dataclass
class BrazeUnsubscribeResponseEmail:
    email: str
    unsubscribed_at: datetime.datetime


@dataclasses.dataclass
class InsertDataRow:
    member_id: str
    preference_id: str
    value: str
    created_at: datetime.datetime
    modified_at: datetime.datetime


@click.command()
@click.option(
    "--dry_run",
    "-d",
    is_flag=True,
    help="Run the script but do not save the result in the database.",
)
@click.option(
    "--batch_size",
    "-b",
    default=DEFAULT_BATCH_SIZE,
    help="The number of MemberTracks to pull into memory at a time.",
)
def main(dry_run: bool = False, batch_size: int = DEFAULT_BATCH_SIZE):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    backfill(dry_run=dry_run, batch_size=batch_size)


if __name__ == "__main__":
    main()
