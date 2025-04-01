"""
backfill_assessment_condition.py

Get all assessments of TYPE between a pair of dates, or from all time.
Export answers to a specific set of assessment questions as fhir conditions.
Specify the fhir dataset to export TO.
Add a meta value describing the export method.

Usage:
    backfill_assessment_condition.py [--confirm] [--force] [--start-date=<start_date>] [--stop-date=<stop_date>]

Options:
  -h --help             Show this screen.
  --confirm             Show confirmation stats and require user input before export starts.
  --force               Perform reassignments instead of showing what would happen.
  --start-date=<date>   Only export assessments created on or after this date.
  --stop-date=<date>    Only export assessments created before this date.
"""
import warnings
from datetime import datetime
from typing import List, Union

from docopt import docopt

from app import create_app
from assessments.utils.assessment_exporter import (
    AssessmentExporter,
    AssessmentExportTopic,
)
from authn.models.user import User
from models.enterprise import (
    Assessment,
    AssessmentLifecycle,
    NeedsAssessment,
    NeedsAssessmentTypes,
)
from models.FHIR.condition import Condition
from storage.connection import db
from utils.fhir_requests import FHIRClient
from utils.log import logger

log = logger(__name__)


# Utilities
def get_users_with_data(
    assessment_type: NeedsAssessmentTypes,
    start_date: datetime = None,  # type: ignore[assignment] # Incompatible default for argument "start_date" (default has type "None", argument has type "datetime")
    stop_date: datetime = None,  # type: ignore[assignment] # Incompatible default for argument "stop_date" (default has type "None", argument has type "datetime")
) -> List[User]:
    """Query and return `User`s with completed assessments of type `assessment_type`."""
    warnings.warn(  # noqa  B028  TODO:  No explicit stacklevel keyword argument found. The warn method from the warnings module uses a stacklevel of 1 by default. This will only show a stack trace for the line on which the warn method is called. It is therefore recommended to use a stacklevel of 2 or greater to provide more information to the user.
        """#pod-care-management NeedsAssessment is no longer managed in Mono.
        This routine may be obsoleted and managed in HDC.
        """,
        DeprecationWarning,
    )

    users_query = User.query.join(
        NeedsAssessment, Assessment, AssessmentLifecycle
    ).filter(
        AssessmentLifecycle.type == assessment_type,
        NeedsAssessment.completed == True,
    )
    if start_date:
        users_query = users_query.filter(NeedsAssessment.created_at >= start_date)
    if stop_date:
        users_query = users_query.filter(NeedsAssessment.created_at < stop_date)
    return users_query.all()


def load_existing_data(client, user, questions: list) -> dict:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    """Return user's existing FHIR condition data as a nested lookup object.

    Example: `{'question_name': {'condition_code': {'id': 'fhir_id': 'date': 'datestring'}}}`
    """
    bundle = client.Condition.search(identifier={",".join(questions), str(user.id)})
    lookups = {}
    item: dict
    for item in client.iterate_entries(bundle):
        entry: dict = item["resource"]
        identifiers: dict = client.get_identifiers(entry)
        user_id: str = identifiers.get(
            "user_id", entry["subject"]["identifier"]["value"]
        )

        # user.id could collide with another identifier value, so double check
        # this item is actually applicable to the user.
        if str(user_id) != str(user.id):
            continue

        # Update condition within existing question_name cache
        condition_code: str = entry["code"]["text"]
        existing: dict = lookups.setdefault(identifiers["question_name"], {})
        if (
            condition_code not in existing
            or existing[condition_code]["date"] < entry["recordedDate"]
        ):
            existing[condition_code] = {
                "id": entry["id"],
                "date": entry["recordedDate"],
            }

    return lookups


# Iteration workers
def export_for_user(
    exporter: AssessmentExporter,
    client: FHIRClient,
    user: User,
    questions: List[str],
    start_date: Union[datetime, None],
    stop_date: Union[datetime, None],
    force: bool = False,
) -> int:
    """Gather and submit `Condition` data for a user for export to FHIR.

    Returns the number of conditions exported.
    """
    user_cache = load_existing_data(client, user, questions)
    answers = exporter.all_answers_for(
        user, AssessmentExportTopic.FHIR, questions, after=start_date, before=stop_date  # type: ignore[arg-type] # Argument "after" to "all_answers_for" of "AssessmentExporter" has incompatible type "Optional[datetime]"; expected "datetime" #type: ignore[arg-type] # Argument "before" to "all_answers_for" of "AssessmentExporter" has incompatible type "Optional[datetime]"; expected "datetime"
    )
    conditions = Condition.export_assessment_conditions(answers, user)
    num_exported = 0
    num_unchanged = 0

    for data in conditions:
        identifiers: dict = client.get_identifiers(data)
        condition_code: str = data["code"]["text"]
        question_name: str = identifiers["question_name"]
        existing: dict = user_cache.get(question_name, {}).get(condition_code)

        # We appear to have some non-answer data on some responses.
        if condition_code == "none":
            continue

        # Don't submit unless the FHIR item is missing or outdated
        if not existing:
            client.Condition.create(data)
        elif existing["date"] < data["recordedDate"]:
            client.Condition.update(existing["id"], data)
        else:
            num_unchanged += 1
            continue

        num_exported += 1

    if num_unchanged:
        run_type = "LIVE RUN" if force else "DRY RUN"
        log.info(f"{run_type}: Unchanged in batch", size=num_unchanged, user_id=user.id)

    if num_exported:
        if force:
            log.info("LIVE RUN: Executing batch", size=num_exported, user_id=user.id)
            client.execute_batch()
        else:
            log.info("DRY RUN: Prepped batch", size=num_exported, user_id=user.id)

    return num_exported


# Entry point
@db.from_replica
def run(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    confirm=False,
    force=False,
    questions=[],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
    assessment_type: NeedsAssessmentTypes = None,  # type: ignore[assignment] # Incompatible default for argument "assessment_type" (default has type "None", argument has type "NeedsAssessmentTypes")
    start_date: datetime = None,  # type: ignore[assignment] # Incompatible default for argument "start_date" (default has type "None", argument has type "datetime")
    stop_date: datetime = datetime.now(),  # noqa  B008  TODO:  Do not perform function calls in argument defaults.  The call is performed only once at function definition time. All calls to your function will reuse the result of that definition-time function call.  If this is intended, assign the function call to a module-level variable and use that variable as a default value.
):
    """Iterates users with completed assessments within the supplied date range for export to FHIR.

    The purpose of this utility is to submit completed assessments that were not performed during
    normal use of the `UserAssessmentsResource` & `UserAssessmentResource` endpoints.  This may be
    because of job interruptions or crashes, or data that predated automatic submissions.
    """
    run_type = "LIVE RUN" if force else "DRY RUN"
    log.info(
        f"{run_type}: Configured.", assessment_type=assessment_type, questions=questions
    )

    client = FHIRClient(use_batches=True)
    exporter = AssessmentExporter.for_all_assessments()
    users_with_data = get_users_with_data(assessment_type, start_date, stop_date)  # type: ignore[arg-type] # Argument 1 to "get_users_with_data" has incompatible type "Optional[NeedsAssessmentTypes]"; expected "NeedsAssessmentTypes"

    if confirm:
        should_continue = input(
            f"{run_type}: [{start_date} to {stop_date}] "
            f"Found {len(users_with_data)} user(s). Continue? [Y/n] "
        )
        if should_continue.lower() not in "y":  # allows empty string and explicit "y"
            log.info(f"{run_type}: Aborted.")
            return

    log.info(f"{run_type}: Starting push to FHIR.", user_count=len(users_with_data))

    export_count = 0
    failure_count = 0
    for user in users_with_data:
        try:
            export_count += export_for_user(
                exporter, client, user, questions, start_date, stop_date, force=force
            )
        except Exception:
            log.exception(f"{run_type}: User export failed!", user_id=user.id)
            failure_count += 1

    log.info(
        f"{run_type}: Export finished.",
        export_count=export_count,
        failed_batches=failure_count,
        start_date=start_date.strftime("%Y-%m-%d") if start_date else None,
        stop_date=stop_date.strftime("%Y-%m-%d") if stop_date else None,
    )


if __name__ == "__main__":
    args = docopt(__doc__)
    start_date = args["--start-date"]
    stop_date = args["--stop-date"]

    if start_date:
        start_date = datetime.strptime(start_date, "%Y-%m-%d")

    if stop_date:
        stop_date = datetime.strptime(stop_date, "%Y-%m-%d")

    with create_app().app_context():
        run(
            confirm=args["--confirm"],
            force=args["--force"],
            questions=Condition.question_names,
            assessment_type=NeedsAssessmentTypes.PREGNANCY_ONBOARDING,
            start_date=start_date,
            stop_date=stop_date,
        )
