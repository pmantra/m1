from __future__ import annotations

import functools
from typing import Dict, List, Tuple

import ddtrace.ext
import sqlalchemy.orm

from appointments.models.appointment import Appointment
from appointments.models.constants import APPOINTMENT_STATES
from appointments.models.schedule import Schedule
from appointments.utils import query_utils
from models.products import Product
from mpractice.error import MissingQueryError, QueryNotFoundError
from mpractice.models.appointment import ProviderAppointmentForList
from mpractice.models.common import OrderDirection, ProviderAppointmentFilter
from mpractice.models.note import SessionMetaInfo
from storage.repository.base import BaseRepository

__all__ = ("ProviderAppointmentForListRepository",)

trace_wrapper = ddtrace.tracer.wrap(
    span_type=ddtrace.ext.SpanTypes.SQL,
)


class ProviderAppointmentForListRepository(BaseRepository[ProviderAppointmentForList]):
    model = ProviderAppointmentForList

    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        is_in_uow: bool = False,
    ):
        super().__init__(session=session, is_in_uow=is_in_uow)
        queries = query_utils.load_queries_from_file(
            "mpractice/repository/queries/appointment.sql"
        )
        if len(queries) == 0:
            raise QueryNotFoundError()
        if len(queries) != 3:
            raise MissingQueryError()
        self._get_post_session_notes_by_appointment_ids_query = queries[2]

    def get_appointment_ids_and_total_appointment_count(
        self,
        filters: ProviderAppointmentFilter | None = None,
        order_direction: OrderDirection | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Tuple[List[int], int]:
        """
        Get a list of appointment IDs to be loaded and total appointment count for pagination
        """
        appts = self.appointment_table()
        products = self.product_table()
        schedules = self.schedule_table()

        joined = appts
        where = []
        if filters:
            if filters.practitioner_id:
                practitioner_id = filters.practitioner_id
                joined = joined.join(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Join", variable has type "Table")
                    products, onclause=appts.c.product_id == products.c.id, isouter=True
                )
                where.append(products.c.user_id == practitioner_id)
            if filters.member_id:
                joined = joined.join(  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Join", variable has type "Table")
                    schedules,
                    onclause=appts.c.member_schedule_id == schedules.c.id,
                    isouter=True,
                )
                where.append(schedules.c.user_id == filters.member_id)
            if filters.scheduled_start:
                scheduled_start = filters.scheduled_start
                where.append(appts.c.scheduled_start >= scheduled_start)
            if filters.scheduled_end:
                scheduled_end = filters.scheduled_end
                where.append(appts.c.scheduled_end <= scheduled_end)
            if filters.schedule_event_ids and len(filters.schedule_event_ids) > 0:
                schedule_event_ids = filters.schedule_event_ids
                where.append(appts.c.schedule_event_id.in_(schedule_event_ids))
            if filters.exclude_statuses and len(filters.exclude_statuses) > 0:
                if APPOINTMENT_STATES.cancelled in filters.exclude_statuses:
                    where.append(appts.c.cancelled_at.is_(None))

        if not order_direction or order_direction == OrderDirection.ASC:
            order_by = appts.c.scheduled_start.asc()
        else:
            order_by = appts.c.scheduled_start.desc()

        # If SELECT count becomes a performance bottleneck, consider alternatives to get an estimated count
        count_query = sqlalchemy.select(
            columns=(sqlalchemy.func.count(appts.c.id),),
            from_obj=joined,
            whereclause=sqlalchemy.and_(*where),
        )
        total_appt_count = self.session.execute(count_query).scalar()

        limit = limit if limit else 5
        offset = offset if offset else 0
        ids_query = sqlalchemy.select(
            columns=(appts.c.id,),
            from_obj=joined,
            whereclause=sqlalchemy.and_(*where),
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        rows = self.session.execute(ids_query).fetchall()
        appt_ids = [row.id for row in rows]
        return appt_ids, total_appt_count

    def get_appointments_by_ids(
        self, appointment_ids: List[int], order_direction: OrderDirection | None = None
    ) -> List[ProviderAppointmentForList]:
        """
        Each provider appointment for list contains
            - core appointment data
            - reschedule history
            - previous appointments between the same member and practitioner on the same schedule
        """
        if not appointment_ids:
            return []

        order_direction_string = ""
        if order_direction and order_direction == OrderDirection.DESC:
            order_direction_string = "DESC"

        # TODO: move query string to sql file
        query = f"""
            SELECT 
                loaded_appts.id,
                loaded_appts.privacy,
                loaded_appts.privilege_type,
                loaded_appts.scheduled_start,
                loaded_appts.scheduled_end,
                loaded_appts.cancelled_at,
                loaded_appts.disputed_at,
                loaded_appts.member_started_at,
                loaded_appts.member_ended_at,
                loaded_appts.practitioner_started_at,
                loaded_appts.practitioner_ended_at,
                loaded_appts.json,
                loaded_appts.practitioner_id,
                loaded_appts.member_id,
                loaded_appts.member_first_name,
                loaded_appts.member_last_name,
                loaded_appts.member_country_code,
                loaded_appts.payment_captured_at,
                loaded_appts.payment_amount,
                appt_reschedule_history.scheduled_start AS rescheduled_from_previous_appointment_time,
                previous_appts.count                    AS repeat_patient_appointment_count,
                appt_credits.latest_used_at             AS credit_latest_used_at,
                appt_credits.total_used_credits,
                appt_fees.count                         AS fees_count
            FROM (
                -- Step 1: get core appointment data from relevant tables
                SELECT 
                    appointment.id,
                    appointment.privacy,
                    appointment.privilege_type,
                    appointment.product_id,
                    appointment.member_schedule_id,
                    appointment.scheduled_start,
                    appointment.scheduled_end,
                    appointment.cancelled_at,
                    appointment.disputed_at,
                    appointment.member_started_at,
                    appointment.member_ended_at,
                    appointment.practitioner_started_at,
                    appointment.practitioner_ended_at,
                    appointment.json,
                    payment_accounting_entry.captured_at AS payment_captured_at,
                    payment_accounting_entry.amount      AS payment_amount,
                    product.user_id                      AS practitioner_id,
                    user.id                              AS member_id,
                    user.first_name                      AS member_first_name,
                    user.last_name                       AS member_last_name,
                    member_profile.country_code          AS member_country_code
                FROM appointment
                    LEFT OUTER JOIN payment_accounting_entry ON payment_accounting_entry.appointment_id = appointment.id
                    LEFT OUTER JOIN product ON product.id = appointment.product_id
                    LEFT OUTER JOIN schedule ON schedule.id = appointment.member_schedule_id
                    LEFT OUTER JOIN user ON user.id = schedule.user_id
                    LEFT OUTER JOIN member_profile ON user.id = member_profile.user_id
                WHERE appointment.id IN :appointment_ids
            ) AS loaded_appts

            LEFT OUTER JOIN (
                -- Step 2: for appointments loaded in step 1, get the latest reschedule history if exists
                SELECT appointment_id, scheduled_start
                FROM reschedule_history
                WHERE id IN (
                    SELECT max(id) FROM reschedule_history 
                    WHERE appointment_id IN :appointment_ids 
                    GROUP BY appointment_id
                )
            ) AS appt_reschedule_history
            ON loaded_appts.id = appt_reschedule_history.appointment_id

            LEFT OUTER JOIN (
                -- Step 3: for each appointments loaded in step 1, get other appointments that are
                -- 1) with the same practitioner, indicated by product_id.user_id
                -- 2) with the same member and on the same schedule, indicated by member_schedule_id
                -- 3) is not cancelled, indicated by cancelled_at
                -- 4) started before the loaded appointment and current time, indicated by scheduled_start
                -- The count of such appointments is used for repeat patient info.
                SELECT 
                    loaded_appt.id                AS loaded_appt_id,
                    count(*)                      AS count
                FROM appointment other_appt INNER JOIN appointment loaded_appt
                    ON other_appt.member_schedule_id = loaded_appt.member_schedule_id
                LEFT OUTER JOIN product loaded_product on loaded_appt.product_id = loaded_product.id
                LEFT OUTER JOIN product other_product on other_appt.product_id = other_product.id
                WHERE loaded_appt.id IN :appointment_ids
                    AND other_appt.cancelled_at IS NULL
                    AND other_appt.scheduled_start < now()
                    AND other_appt.scheduled_start < loaded_appt.scheduled_start
                    AND loaded_product.user_id = other_product.user_id
                GROUP BY loaded_appt.id
            ) AS previous_appts
            ON loaded_appts.id = previous_appts.loaded_appt_id
            
            LEFT OUTER JOIN (
                -- Step 4: for each appointment loaded in step 1, 
                -- get the latest credit.used_at and the sum of all used credits
                SELECT
                    appointment_id,
                    max(used_at)   AS latest_used_at,
                    sum(amount)    AS total_used_credits
                FROM credit
                WHERE appointment_id IN :appointment_ids AND used_at IS NOT NULL
                GROUP BY appointment_id
            ) AS appt_credits
            ON loaded_appts.id = appt_credits.appointment_id
            
            LEFT OUTER JOIN (
                -- Step 5: for each appointment loaded in step 1, get the count of associated fees
                SELECT appointment_id, count(*) AS count
                FROM fee_accounting_entry
                WHERE appointment_id IN :appointment_ids
                GROUP BY appointment_id
            ) as appt_fees
            ON loaded_appts.id = appt_fees.appointment_id

            ORDER BY loaded_appts.scheduled_start {order_direction_string}
        """

        result = self.session.execute(
            query, {"appointment_ids": appointment_ids}
        ).fetchall()
        return self.deserialize_list(result)

    def get_paginated_appointments_with_total_count(
        self,
        filters: ProviderAppointmentFilter | None = None,
        order_direction: OrderDirection | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Tuple[List[ProviderAppointmentForList], int]:
        (
            appointment_ids,
            total_count,
        ) = self.get_appointment_ids_and_total_appointment_count(
            filters, order_direction, limit, offset
        )
        appointments = self.get_appointments_by_ids(appointment_ids, order_direction)
        return appointments, total_count

    def get_appointment_id_to_latest_post_session_note(
        self, appointment_ids: List[int]
    ) -> Dict[int, SessionMetaInfo]:
        if not appointment_ids:
            return {}
        rows = self.session.execute(
            self._get_post_session_notes_by_appointment_ids_query,
            {"appointment_ids": appointment_ids},
        ).fetchall()
        if rows is None:
            return {}

        appt_id_to_latest_post_session_note = {}
        last_seen_appointment_id = None
        for row in rows:
            if row.appointment_id != last_seen_appointment_id:
                appt_id_to_latest_post_session_note[
                    row.appointment_id
                ] = SessionMetaInfo(
                    created_at=row.created_at,
                    draft=row.draft,
                    notes=row.notes,
                )
            last_seen_appointment_id = row.appointment_id

        return appt_id_to_latest_post_session_note

    @classmethod
    @functools.lru_cache(maxsize=1)
    def make_table(cls) -> sqlalchemy.Table:
        return cls.appointment_table()

    @classmethod
    def table_columns(cls) -> tuple[sqlalchemy.sql.ColumnElement, ...]:  # type: ignore[override] # Return type "Tuple[ColumnElement[Any], ...]" of "table_columns" incompatible with return type "Tuple[Column[Any], ...]" in supertype "BaseRepository"
        return cls.appointment_columns()

    @classmethod
    @functools.lru_cache(maxsize=1)
    def appointment_table(cls) -> sqlalchemy.Table:
        return Appointment.__table__

    @classmethod
    @functools.lru_cache(maxsize=1)
    def product_table(cls) -> sqlalchemy.Table:
        return Product.__table__

    @classmethod
    @functools.lru_cache(maxsize=1)
    def schedule_table(cls) -> sqlalchemy.Table:
        return Schedule.__table__

    @classmethod
    @functools.lru_cache(maxsize=1)
    def appointment_columns(cls) -> tuple[sqlalchemy.sql.ColumnElement, ...]:
        appointment_table = cls.appointment_table()
        return (
            appointment_table.c.id,
            appointment_table.c.privacy,
            appointment_table.c.privilege_type,
            appointment_table.c.member_schedule_id,
            appointment_table.c.product_id,
            appointment_table.c.scheduled_start,
            appointment_table.c.scheduled_end,
            appointment_table.c.cancelled_at,
            appointment_table.c.disputed_at,
            appointment_table.c.member_started_at,
            appointment_table.c.member_ended_at,
            appointment_table.c.practitioner_started_at,
            appointment_table.c.practitioner_ended_at,
            appointment_table.c.json,
        )
