from __future__ import annotations

import dataclasses
import datetime
import enum
import logging
import time
from typing import Any, List, Tuple

from sqlalchemy import and_, sql
from sqlalchemy.sql.expression import Select

from app import create_app
from eligibility import e9y, repository
from eligibility.tasks.backfill_e9y_with_oe_uoe import _get_e9y_verification_type
from models import enterprise as enterprise_models
from storage.connection import db
from tasks.queues import job
from utils.log import logger

logging.basicConfig(level=logging.CRITICAL)
log = logger(__name__)


def populate_backfill_data() -> None:
    """
    Prepare backfill data,
    We fill the eligibility_verification_state with all data required for making the GRPC call
    to eligibility to check if verification exists
    @return:
    """
    app = create_app(task_instance=True)
    with app.app_context():
        try:
            db.session.execute(
                """
                insert into maven.`eligibility_verification_state`
                (
                    `user_id`
                    , `user_organization_employee_id`
                    , `organization_employee_id`
                    , `organization_id`
                    , `oe_member_id`
                    , `verification_type`
                    , `unique_corp_id`
                    , `dependent_id`
                    , `first_name`
                    , `last_name`
                    , `date_of_birth`
                    , `email`
                    , `work_state`
                    , `verified_at`
                    , `deactivated_at`
                )
                select
                    u.id,
                    uoe.id,
                    oe.id,
                    oe.organization_id,
                    oe.eligibility_member_id,
                    o.eligibility_type,
                    oe.unique_corp_id,
                    oe.dependent_id,
                    oe.first_name,
                    oe.last_name,
                    oe.date_of_birth,
                    oe.email,
                    oe.work_state,
                    oe.created_at,
                    oe.deleted_at
                from maven.user u
                inner join maven.user_organization_employee uoe
                    on u.id  = uoe.user_id
                inner join (
                    select
                        user_id,
                        max(id) as id
                    from maven.user_organization_employee
                    group by user_id
                ) uoe_by_user
                    on uoe.user_id = uoe_by_user.user_id
                    and uoe.id = uoe_by_user.id
                inner join maven.organization_employee oe
                    on oe.id = uoe.organization_employee_id
                inner join maven.organization o
                    on oe.organization_id = o.id
                order by u.id, uoe.id
                on duplicate key update
                    `user_id` = values (`user_id`),
                    `user_organization_employee_id` = values (`user_organization_employee_id`), 
                    `organization_employee_id` = values (`organization_employee_id`), 
                    `organization_id` = values (`organization_id`), 
                    `oe_member_id` = values (`oe_member_id`), 
                    `verification_type` = values (`verification_type`), 
                    `unique_corp_id` = values (`unique_corp_id`), 
                    `dependent_id` = values (`dependent_id`), 
                    `first_name` = values (`first_name`), 
                    `last_name` = values (`last_name`), 
                    `date_of_birth` = values (`date_of_birth`), 
                    `email` = values (`email`), 
                    `work_state` = values (`work_state`), 
                    `verified_at` = values (`verified_at`), 
                    `deactivated_at` = values (`deactivated_at`);
                """
            )
            db.session.commit()
            log.info("populated backfill data success")
        except Exception as e:
            log.error(f"populated backfill data failed: exception={str(e)}")


def backfill_member_track_verification_id() -> None:
    """
    Use the data in eligibility_verification_state to backfill verification_id
    into member_track.eligibility_verification_id
    @return:
    """
    app = create_app(task_instance=True)
    with app.app_context():
        try:
            db.session.execute(
                """
                UPDATE maven.member_track mt
                INNER JOIN maven.client_track ct
                ON mt.client_track_id=ct.id
                INNER JOIN maven.eligibility_verification_state source
                ON ct.organization_id=source.e9y_organization_id
                AND mt.user_id=source.user_id
                SET mt.eligibility_verification_id=source.e9y_verification_id
                WHERE mt.eligibility_member_id IS NULL
                AND mt.eligibility_verification_id IS NULL
                AND source.backfill_status in ('SUCCESS', 'ORG_MATCH');
                """
            )
            db.session.commit()
            log.info("backfill member_track success")
        except Exception as e:
            log.error(f"backfill data failed: exception={str(e)}")


def backfill_credit_verification_id() -> None:
    """
    Use the data in eligibility_verification_state to backfill verification_id
    into credit.eligibility_verification_id
    @return:
    """
    app = create_app(task_instance=True)
    with app.app_context():
        try:
            db.session.execute(
                """
                UPDATE maven.credit credit
                INNER JOIN maven.organization_employee oe
                ON credit.organization_employee_id=oe.id
                INNER JOIN maven.eligibility_verification_state source
                ON credit.user_id=source.user_id
                AND oe.organization_id=source.organization_id
                SET credit.eligibility_verification_id=source.e9y_verification_id
                WHERE credit.eligibility_member_id IS NULL
                AND credit.eligibility_verification_id IS NULL
                AND credit.organization_employee_id IS NOT NULL
                AND source.backfill_status in ('SUCCESS', 'ORG_MATCH');
                """
            )
            db.session.commit()
            log.info("backfill credit success")
        except Exception as e:
            log.error(f"backfill data failed: exception={str(e)}")


def backfill_reimbursement_wallet_verification_id() -> None:
    """
    Use the data in eligibility_verification_state to backfill verification_id
    into reimbursement_wallet.eligibility_verification_id
    @return:
    """
    app = create_app(task_instance=True)
    with app.app_context():
        try:
            db.session.execute(
                """
                UPDATE maven.reimbursement_wallet rw
                INNER JOIN maven.organization_employee oe
                ON rw.organization_employee_id=oe.id
                INNER JOIN maven.eligibility_verification_state source
                ON rw.user_id=source.user_id
                AND oe.organization_id=source.organization_id
                SET rw.initial_eligibility_verification_id=source.e9y_verification_id
                WHERE rw.initial_eligibility_member_id IS NULL
                AND rw.initial_eligibility_verification_id IS NULL
AND source.backfill_status in ('SUCCESS', 'ORG_MATCH');
                """
            )
            db.session.commit()
            log.info("backfill reimbursement_wallet success")
        except Exception as e:
            log.error(f"backfill data failed: exception={str(e)}")


@dataclasses.dataclass
class OrganizationEmployeeForUser:
    id: int
    user_id: int
    user_organization_employee_id: int
    organization_employee_id: int
    organization_id: int
    oe_member_id: int
    verification_type: str
    unique_corp_id: str
    dependent_id: str
    first_name: str
    last_name: str
    date_of_birth: datetime.date
    email: str
    work_state: str
    verified_at: datetime.datetime
    deactivated_at: datetime.datetime
    e9y_member_id: int
    e9y_verification_id: int
    e9y_organization_id: int
    e9y_unique_corp_id: int
    e9y_dependent_id: int
    backfill_status: str


@dataclasses.dataclass
class ValidationResult:
    verification_exists: bool
    org_id_matches: bool
    unique_corp_id_matches: bool


class BackfillStatus(enum.Enum):
    NOT_FOUND = "NOT_FOUND"
    ORG_MATCH = "ORG_MATCH"
    ORG_MISMATCH = "ORG_MISMATCH"
    FAILED = "FAILED"
    SUCCESS = "SUCCESS"


def get_batch(app, batch_size: int = 5_000) -> List[OrganizationEmployeeForUser]:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    """Get a batch of OrganizationEmployeeForUser to check"""
    with app.app_context():
        res = db.session.execute(
            """
                SELECT *
                FROM maven.eligibility_verification_state 
                WHERE backfill_status IS NULL
                LIMIT :batch_size
            """,
            {
                "batch_size": batch_size,
            },
        )

    return [OrganizationEmployeeForUser(**dict(r)) for r in res]


def _resolve_backfill_status(
    oe_user: OrganizationEmployeeForUser,
    verification: e9y.EligibilityVerification | None,
) -> BackfillStatus:
    """Based on an OrganizationEmployeeForUser and verification, determine the backfill status"""
    if not verification:
        return BackfillStatus.NOT_FOUND

    organization_id_matches: bool = (
        oe_user.organization_id == verification.organization_id
    )

    if organization_id_matches:
        return BackfillStatus.ORG_MATCH
    else:
        return BackfillStatus.ORG_MISMATCH


def update_oe_user(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    app,
    oe_user: OrganizationEmployeeForUser,
    verification: e9y.EligibilityVerification | None,
):
    """Update the eligibility_verification_state table with result from e9y"""
    with app.app_context():
        db.session.execute(
            """
                UPDATE maven.eligibility_verification_state 
                SET 
                    e9y_member_id=:member_id,
                    e9y_verification_id=:verification_id,
                    e9y_organization_id=:organization_id,
                    e9y_unique_corp_id=:unique_corp_id,
                    e9y_dependent_id=:dependent_id,
                    backfill_status=:backfill_status
                WHERE id=:id
            """,
            {
                "id": oe_user.id,
                "verification_id": verification.verification_id
                if verification
                else None,
                "organization_id": verification.organization_id
                if verification
                else None,
                "unique_corp_id": verification.unique_corp_id if verification else None,
                "dependent_id": verification.dependent_id if verification else None,
                "member_id": verification.eligibility_member_id
                if verification
                else None,
                "backfill_status": _resolve_backfill_status(
                    oe_user=oe_user, verification=verification
                ).value,
            },
        )
        db.session.commit()
    log.info(
        "Finished updating eligibility_verification_state row", user_id=oe_user.user_id
    )


@job
def process_batch(batch_size: int = 5_000):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """Pull batch_size number of records and validate the verification in e9y"""
    app = create_app(task_instance=True)
    repo = repository.EligibilityMemberRepository()
    st = time.time()
    processed: int = 0
    log.info("Starting batch", batch_size=batch_size)
    for oe_user in get_batch(app=app, batch_size=batch_size):
        verification: e9y.EligibilityVerification | None = (
            repo.get_verification_for_user(user_id=oe_user.user_id)
        )
        update_oe_user(app=app, oe_user=oe_user, verification=verification)
        processed += 1

    et = time.time()
    elapsed = et - st
    log.info("Batch completed", processed_count=processed, time_seconds=elapsed)


def _format_fetch_query(
    backfill_status_filter: List[
        BackfillStatus
    ] = [],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
    organization_id_filter: List[
        int
    ] = [],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
    verification_type_filter: List[
        enterprise_models.OrganizationEligibilityType
    ] = [],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
) -> Select[Tuple[Any, ...]]:  # type: ignore[type-arg] # "Select" expects no type arguments, but 1 given
    query = sql.select([sql.text("*")]).select_from(  # type: ignore[list-item] # List item 0 has incompatible type "TextClause"; expected "Union[ColumnElement[Any], FromClause, int]"
        sql.table("eligibility_verification_state")
    )
    if backfill_status_filter or organization_id_filter or verification_type_filter:
        query = query.where(
            and_(
                sql.text("backfill_status IN :status")
                if backfill_status_filter
                else sql.text("TRUE"),
                sql.text("organization_id IN :org_ids")
                if organization_id_filter
                else sql.text("TRUE"),
                sql.text("verification_type IN :elig_types")
                if verification_type_filter
                else sql.text("TRUE"),
            )
        )
    return query


def fetch_for_backfill(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    app,
    backfill_status_filter: List[
        BackfillStatus
    ] = [],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
    organization_id_filter: List[
        int
    ] = [],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
    verification_type_filter: List[
        enterprise_models.OrganizationEligibilityType
    ] = [],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
    batch_size: int = 5_000,
) -> List[OrganizationEmployeeForUser]:
    """Fetch the relevant users for backfill"""
    with app.app_context():
        query = _format_fetch_query(
            backfill_status_filter=backfill_status_filter,
            organization_id_filter=organization_id_filter,
            verification_type_filter=verification_type_filter,
        ).limit(batch_size)
        res = db.session.execute(
            query,
            {
                "status": [s.value for s in backfill_status_filter],
                "org_ids": organization_id_filter,
                "elig_types": [v.value for v in verification_type_filter],
            },
        )

    return [OrganizationEmployeeForUser(**dict(r)) for r in res]


def _create_missing(
    oe_for_user: OrganizationEmployeeForUser,
    repo: repository.EligibilityMemberRepository,
) -> e9y.EligibilityVerification | None:
    """Attempt to create missing verification"""
    verification = repo.create_verification_for_user(
        user_id=oe_for_user.user_id,
        verification_type=_get_e9y_verification_type(
            eligibility_type=oe_for_user.verification_type,
            eligibility_member_id=oe_for_user.oe_member_id,
        ),
        date_of_birth=oe_for_user.date_of_birth,
        email=oe_for_user.email,
        first_name=oe_for_user.first_name,
        last_name=oe_for_user.last_name,
        work_state=oe_for_user.work_state,
        unique_corp_id=oe_for_user.unique_corp_id,
        dependent_id=oe_for_user.dependent_id,
        organization_id=oe_for_user.organization_id,
        additional_fields={
            "organization_employee_id": oe_for_user.organization_employee_id,
            "user_organization_employee_id": oe_for_user.user_organization_employee_id,
        },
        eligibility_member_id=oe_for_user.oe_member_id,
    )

    if verification:
        log.info(
            "Successfully created verification during backfill",
            user_id=oe_for_user.user_id,
            oe_for_user_id=oe_for_user.id,
            verification_id=verification.verification_id,
        )
    else:
        log.info(
            "Failed to create verification during backfill",
            user_id=oe_for_user.user_id,
            oe_for_user_id=oe_for_user.id,
        )

    return verification


def _update_oe_user(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    app,
    oe_user: OrganizationEmployeeForUser,
    verification: e9y.EligibilityVerification | None,
):
    """Update an existing OE user based on results of backfill"""
    with app.app_context():
        try:
            db.session.execute(
                """
                update maven.`eligibility_verification_state`
                    set e9y_member_id = :e9y_member_id,
                        e9y_verification_id = :e9y_verification_id,
                        e9y_organization_id = :e9y_organization_id,
                        e9y_unique_corp_id = :e9y_unique_corp_id,
                        e9y_dependent_id = :e9y_dependent_id,
                        backfill_status = :backfill_status
                where id = :id
                """,
                {
                    "id": oe_user.id,
                    "e9y_member_id": verification.eligibility_member_id
                    if verification
                    else None,
                    "e9y_verification_id": verification.verification_id
                    if verification
                    else None,
                    "e9y_organization_id": verification.organization_id
                    if verification
                    else None,
                    "e9y_unique_corp_id": verification.unique_corp_id
                    if verification
                    else None,
                    "e9y_dependent_id": verification.dependent_id
                    if verification
                    else None,
                    "backfill_status": BackfillStatus.SUCCESS.value
                    if verification
                    else BackfillStatus.FAILED.value,
                },
            )
            db.session.commit()
            log.info(
                "Updated eligibility_verification_state successfully",
                user_id=oe_user.user_id,
            )
        except Exception as e:
            log.error(
                f"Updated eligibility_verification_state failed: exception={str(e)}"
            )


@job
def backfill_verification(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    backfill_status_filter: List[
        BackfillStatus
    ] = [  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
        BackfillStatus.ORG_MISMATCH,
        BackfillStatus.NOT_FOUND,
    ],
    organization_id_filter: List[
        int
    ] = [],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
    verification_type_filter: List[
        enterprise_models.OrganizationEligibilityType
    ] = [],  # noqa  B006  TODO:  Do not use mutable data structures for argument defaults.  They are created during function definition time. All calls to the function reuse this one instance of that data structure, persisting changes between them.
    dry_run: bool = False,
    batch_size: int = 5_000,
):
    """
    Run backfill of verifications on a batch depending on filters
    Will default to backfilling BackfillStatus.ORG_MISMATCH and BackfillStatus.NOT_FOUND
    """
    app = create_app(task_instance=True)
    repo = repository.EligibilityMemberRepository()

    created: int = 0
    total: int = 0

    log.info("Starting backfill....")

    for oe_for_user in fetch_for_backfill(
        app=app,
        backfill_status_filter=backfill_status_filter,
        organization_id_filter=organization_id_filter,
        verification_type_filter=verification_type_filter,
        batch_size=batch_size,
    ):
        total += 1

        if not dry_run:
            verification: e9y.EligibilityVerification | None = _create_missing(
                oe_for_user=oe_for_user, repo=repo
            )
            _update_oe_user(app=app, oe_user=oe_for_user, verification=verification)
            if verification:
                created += 1

    log.info("Backfill completed....", total=total, created=created, dry_run=dry_run)
