import asyncio
import dataclasses
import logging
import time
from typing import List, Optional, Tuple

from app import create_app
from common import stats
from eligibility.e9y import grpc_service
from storage.connection import db
from tasks.queues import job
from utils.log import logger

logging.basicConfig(level=logging.CRITICAL)
log = logger(__name__)

BATCH_SIZE = 50
MAX_CONCURRENCY = 5


@dataclasses.dataclass(frozen=True)
class BackfillSummary:
    min_id: int
    max_id: int
    success_count: int
    error_count: int
    process_seconds: int


def get_max_oe_id() -> None:
    """
    get max id of organization_employee
    it will be used just before we turn on dual write, so we know what data need backfilled
    @return: max id of OE
    """
    app = create_app(task_instance=True)
    with app.app_context():
        res = db.session.execute(
            """SELECT MAX(id) as id FROM maven.organization_employee"""
        ).fetchall()
        log.info(f"organization_employee max_oe_id={res[0].id}")


def get_max_uoe_id() -> None:
    """
    get max id of user_organization_employee
    it will be used just before we turn on dual write, so we know what data need backfilled
    @return: max id of UOE
    """
    app = create_app(task_instance=True)
    with app.app_context():
        res = db.session.execute(
            """SELECT MAX(id) as id FROM maven.user_organization_employee"""
        ).fetchall()
        log.info(f"user_organization_employee max_uoe_id={res[0].id}")


def get_backfilled_count() -> None:
    """
    @return: count fo backfilled rows
    """
    app = create_app(task_instance=True)
    with app.app_context():
        app = create_app()
        with app.app_context():
            res = db.session.execute(
                """SELECT count(*) as cnt FROM maven.backfill_verification_state bvs 
                    WHERE  backfill_verification_id IS NOT NULL 
                    OR backfill_error IS NOT NULL"""
            ).fetchall()
            log.info(f"backfilled_count={res[0].cnt}")


def get_backfilled_error_count() -> None:
    """
    @return: count fo backfilled rows which has error
    """
    app = create_app(task_instance=True)
    with app.app_context():
        app = create_app()
        with app.app_context():
            res = db.session.execute(
                """SELECT count(*) as cnt FROM maven.backfill_verification_state bvs 
                    WHERE backfill_error IS NOT NULL"""
            ).fetchall()
            log.info(f"backfilled_error_count={res[0].cnt}")


def get_backfill_pending_count() -> None:
    """
    @return: count of pending backfill rows
    """
    app = create_app(task_instance=True)
    with app.app_context():
        res = db.session.execute(
            """SELECT count(*) as cnt FROM maven.backfill_verification_state bvs 
                WHERE  backfill_verification_id IS NULL 
                AND backfill_error IS NULL"""
        ).fetchall()
        log.info(f"pending_backfill_count=={res[0].cnt}")


def get_max_pending_backfill_id() -> int:
    """
    @return: max id of pending backfill row
    """
    app = create_app(task_instance=True)
    with app.app_context():
        res = db.session.execute(
            """SELECT MAX(id) as id FROM maven.backfill_verification_state
                WHERE  backfill_verification_id IS NULL 
                AND backfill_error IS NULL
            """
        ).fetchall()
        log.info(f"max_pending_backfill={res[0].id}")
        return res[0].id


def get_min_pending_backfill_id() -> int:
    """
    @return: min id of pending backfill row
    """
    app = create_app(task_instance=True)
    with app.app_context():
        res = db.session.execute(
            """SELECT MIN(id) as id FROM maven.backfill_verification_state
                WHERE  backfill_verification_id IS NULL 
                AND backfill_error IS NULL
            """
        ).fetchall()
        log.info(f"min_pending_backfill={res[0].id}")
        return res[0].id


def populate_backfill_data(min_id: int, max_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Prepare backfill data,
    We fill the backfill_verification_state with all data required for making the GRPC call
    min_id, max_id is the range of user_organization_employee.id,
    so it will give us flexibility to make small batch on which data to backfill
    @param min_id: min id of UOE
    @param max_id: max id of UOE
    @return:
    """
    app = create_app(task_instance=True)
    with app.app_context():
        try:
            db.session.execute(
                """
            INSERT INTO maven.`backfill_verification_state` 
                ( `user_organization_employee_id`
                , `organization_employee_id`
                , `user_id`
                , `organization_id`
                , `eligibility_member_id`
                , `verification_type`
                , `unique_corp_id`
                , `dependent_id`
                , `first_name`
                , `last_name`
                , `date_of_birth`
                , `email`
                , `work_state`
                , `verified_at`
                , `deactivated_at`) 
            select uoe.id as user_organization_employee_id
                , oe.id as organization_employee_id
                , uoe.user_id
                , oe.organization_id
                , oe.eligibility_member_id
                , o.eligibility_type
                , oe.unique_corp_id
                , oe.dependent_id
                , oe.first_name
                , oe.last_name
                , oe.date_of_birth
                , oe.email
                , oe.work_state	
                , oe.created_at as verified_at
                , oe.deleted_at as deactivate_at
                 from maven.user_organization_employee uoe 
            inner  join maven.organization_employee oe on uoe.organization_employee_id  = oe.id
            inner  join maven.organization o on o.id = oe.organization_id
            where uoe.id >= :min_id and uoe.id <=:max_id
            """,
                {
                    "min_id": min_id,
                    "max_id": max_id,
                },
            )
            db.session.commit()
            log.info(
                f"populated backfill data success: min_id={min_id}, max_id={max_id}"
            )
        except Exception as e:
            log.error(
                f"populated backfill data failed: min_id={min_id}, max_id={max_id}, exception={str(e)}"
            )


def _make_batches(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    min_id: int, max_id: int, batch_size=BATCH_SIZE
) -> List[Tuple[int, int]]:
    batches = []
    start = min_id
    while start < max_id:
        end = min(start + batch_size - 1, max_id)
        batches.append((start, end))
        start = end + 1
    return batches


def _backfill_e9y_verification(min_id: int, max_id: int, app) -> BackfillSummary:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    log.info(f"backfill batch started. min_id={min_id}, max_id={max_id}")
    success_count = 0
    error_count = 0
    with app.app_context():
        session = db.session
        st = time.time()
        res = session.execute(
            """
                SELECT id, user_organization_employee_id, organization_employee_id, user_id, verification_type, 
                    organization_id, unique_corp_id, dependent_id, first_name, last_name, email, work_state, 
                    date_of_birth, eligibility_member_id, verified_at, deactivated_at
                FROM maven.backfill_verification_state WHERE backfill_verification_id IS NULL 
                    AND backfill_error IS NULL
                    AND id >= :min_id AND id <= :max_id""",
            {
                "min_id": min_id,
                "max_id": max_id,
            },
        ).fetchall()

        backfill_results: List[Tuple[int, Optional[int], Optional[str]]] = []
        for row in res:
            e9y_verification_type = _get_e9y_verification_type(
                row.verification_type, row.eligibility_member_id
            )
            additional_fields = {
                "user_organization_employee_id": row.user_organization_employee_id,
                "organization_employee_id": row.organization_employee_id,
            }
            if e9y_verification_type != "UNKNOWN":
                verification_created, grpc_error = grpc_service.create_verification(
                    user_id=row.user_id,
                    verification_type=e9y_verification_type,
                    organization_id=row.organization_id,
                    unique_corp_id=row.unique_corp_id,
                    dependent_id=row.dependent_id,
                    first_name=row.first_name,
                    last_name=row.last_name,
                    email=row.email,
                    work_state=row.work_state,
                    date_of_birth=row.date_of_birth,
                    eligibility_member_id=row.eligibility_member_id,
                    additional_fields=additional_fields,
                    verified_at=row.verified_at,
                    deactivated_at=row.deactivated_at,
                )
            else:
                # in case of 'UNKNOWN', we repeat the multistep logic here:
                # refer: https://gitlab.mvnapp.net/maven/maven/-/blob/main/api/eligibility/service.py#L679
                has_necessary_standard_params = row.email is not None
                has_necessary_alternate_params = (row.first_name, row.last_name) != (
                    None,
                    None,
                )
                has_work_state = row.work_state is not None

                if has_necessary_alternate_params:
                    verification_created, grpc_error = grpc_service.create_verification(
                        user_id=row.user_id,
                        verification_type="ALTERNATE",
                        organization_id=row.organization_id,
                        unique_corp_id=row.unique_corp_id,
                        dependent_id=row.dependent_id,
                        first_name=row.first_name,
                        last_name=row.last_name,
                        email=row.email,
                        work_state=row.work_state,
                        date_of_birth=row.date_of_birth,
                        eligibility_member_id=row.eligibility_member_id,
                        additional_fields=additional_fields,
                        verified_at=row.verified_at,
                        deactivated_at=row.deactivated_at,
                    )
                    if verification_created is None and has_work_state:
                        (
                            verification_created,
                            grpc_error,
                        ) = grpc_service.create_verification(
                            user_id=row.user_id,
                            verification_type="ALTERNATE",
                            organization_id=row.organization_id,
                            unique_corp_id=row.unique_corp_id,
                            dependent_id=row.dependent_id,
                            first_name=row.first_name,
                            last_name=row.last_name,
                            email=row.email,
                            work_state=None,
                            date_of_birth=row.date_of_birth,
                            eligibility_member_id=row.eligibility_member_id,
                            additional_fields=additional_fields,
                            verified_at=row.verified_at,
                            deactivated_at=row.deactivated_at,
                        )
                if verification_created is None and has_necessary_standard_params:
                    (
                        verification_created,
                        grpc_error,
                    ) = grpc_service.create_verification(
                        user_id=row.user_id,
                        verification_type="STANDARD",
                        organization_id=row.organization_id,
                        unique_corp_id=row.unique_corp_id,
                        dependent_id=row.dependent_id,
                        first_name=row.first_name,
                        last_name=row.last_name,
                        email=row.email,
                        work_state=None,
                        date_of_birth=row.date_of_birth,
                        eligibility_member_id=row.eligibility_member_id,
                        additional_fields=additional_fields,
                        verified_at=row.verified_at,
                        deactivated_at=row.deactivated_at,
                    )

            if verification_created:
                backfill_results.append(
                    (row.id, verification_created.verification_id, None)
                )
                success_count += 1

            else:
                backfill_results.append((row.id, None, str(grpc_error)))
                error_count += 1
        try:
            for id, verification_id, grpc_error in backfill_results:
                if verification_id is not None:
                    session.execute(
                        """
                        UPDATE maven.backfill_verification_state SET backfill_verification_id = :verification_id
                            WHERE id = :id""",
                        {
                            "verification_id": verification_id,
                            "id": id,
                        },
                    )
                else:
                    session.execute(
                        """
                        UPDATE maven.backfill_verification_state SET backfill_error = :backfill_error
                            WHERE id=:id
                        """,
                        {"backfill_error": str(grpc_error), "id": id},
                    )
            session.commit()
        except Exception as e:
            session.rollback()
            log.exception(
                "Unhandled exception occurred on backfill verification to e9y",
                exception=e,
                results=backfill_results,
            )

    et = time.time()
    elapsed_time = et - st

    summary = BackfillSummary(
        min_id, max_id, success_count, error_count, int(elapsed_time)
    )
    stats.increment(
        metric_name="eligibility.backfill_oe.success",
        pod_name=stats.PodNames.ELIGIBILITY,
        metric_value=success_count,
        tags=["eligibility:info", "backfill_oe_success"],
    )
    stats.increment(
        metric_name="eligibility.backfill_oe.error",
        pod_name=stats.PodNames.ELIGIBILITY,
        metric_value=error_count,
        tags=["eligibility:info", "backfill_oe_error"],
    )
    stats.increment(
        metric_name="eligibility.backfill_oe.batch_complete",
        pod_name=stats.PodNames.ELIGIBILITY,
        tags=["eligibility:info", "backfill_oe"],
    )
    log.info(f"backfill batch finished. summary={summary}")
    return summary


def _get_e9y_verification_type(
    eligibility_type: str, eligibility_member_id: Optional[int]
) -> str:
    # Mono
    # `eligibility_type` enum('STANDARD','ALTERNATE','FILELESS','CLIENT_SPECIFIC','SAML','HEALTHPLAN','UNKNOWN')
    eligibility_type_to_verification_type = {
        "STANDARD": "PRIMARY",
        "ALTERNATE": "ALTERNATE",
        "FILELESS": "FILELESS",
        "CLIENT_SPECIFIC": "CLIENT_SPECIFIC",
        "SAML": "ALTERNATE",
        "HEALTHPLAN": "ALTERNATE",
        "UNKNOWN": "ALTERNATE",
    }

    if eligibility_member_id is None and eligibility_type not in {
        "CLIENT_SPECIFIC",
        "FILELESS",
    }:
        return "MANUAL"

    if eligibility_type in eligibility_type_to_verification_type:
        return eligibility_type_to_verification_type[eligibility_type]
    # if nothing matches - just return it
    return eligibility_type


async def backfill_verification(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    min_id: int, max_id: int, *, batch_size=BATCH_SIZE, max_con=MAX_CONCURRENCY
):
    """
    backfill verification by calling GRPC to e9y with in inclusive range[min_id, max_id]
    here the min_id, max_id is the backfill_verification_state id, so we know how many records will be processed
    @param min_id: min_id of backfill_verification_state.id
    @param max_id: max_id of backfill_verification_state.id
    @param batch_size: how many rows will be in a batch to backfill
    @param max_con: max concurrency batches runs in parallel.
    @return:

    To call :
    await backfill_verification(1008, 2007, batch_size=100, max_concurrency=10)
    """

    log.info(f"starting backill from={min_id}, to={max_id}")
    st = time.time()
    batches = _make_batches(min_id, max_id, batch_size)
    sem = asyncio.Semaphore(max_con)

    async def limited_exec(start, end, app):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        async with sem:
            loop = asyncio.get_event_loop()

            await loop.run_in_executor(
                None, lambda: _backfill_e9y_verification(start, end, app)
            )

    tasks = []
    app = create_app(task_instance=True)
    for start, end in batches:
        task = asyncio.create_task(limited_exec(start, end, app))
        tasks.append(task)

    _ = await asyncio.gather(*tasks)

    et = time.time()
    elapsed_time = et - st
    log.info(
        f"all batches finished. rows={max_id-min_id+1}, batch_size={batch_size}, max_con={max_con} takes {elapsed_time} second"
    )


@job
def backfill_verification_job() -> None:
    min_id = get_min_pending_backfill_id()
    max_id = get_max_pending_backfill_id()
    # prod allow 10 mins for each job to run. 5k should be finished within about 7-8 mins
    job_max_id = min(min_id + 4999, max_id)
    asyncio.run(backfill_verification(min_id, job_max_id))


def re_backfill(id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Use this function to re-backfill 1 row
    In this function:
    backfill_error will be reset to NULL for the target row
    backfill verification will be re-porocessed
    @param id: backfill_verification_state.id for the row need to be re-backfilled
    @return: None
    """
    if id is None:
        log.error(f"id is required for re back fill: id={id}")
    app = create_app(task_instance=True)
    with app.app_context():
        session = db.session
        session.execute(
            """
            UPDATE maven.backfill_verification_state SET backfill_error=NULL WHERE id = :id
            """,
            {"id": id},
        )
        session.commit()

    _backfill_e9y_verification(id, id, app)
