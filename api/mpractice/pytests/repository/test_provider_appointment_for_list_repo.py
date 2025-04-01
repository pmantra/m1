from __future__ import annotations

from datetime import datetime
from typing import List

import pytest
from _pytest.fixtures import FixtureRequest
from flask_sqlalchemy import SQLAlchemy

from appointments.models.appointment import Appointment
from appointments.models.constants import APPOINTMENT_STATES
from appointments.models.reschedule_history import RescheduleHistory
from mpractice.models.appointment import ProviderAppointmentForList
from mpractice.models.common import OrderDirection, ProviderAppointmentFilter
from mpractice.models.note import SessionMetaInfo
from mpractice.repository.provider_appointment_for_list import (
    ProviderAppointmentForListRepository,
)
from pytests.db_util import enable_db_performance_warnings


class TestProviderAppointmentForListRepository:
    @pytest.mark.parametrize(
        argnames="practitioner_id,appointment_by_practitioner,expected_appt_ids,expected_total_count",
        argvalues=[
            (None, None, [100, 200], 2),
            (None, "appointment_200", [200], 1),
            (404, None, [], 0),
        ],
        ids=[
            "no_practitioner_id_filter",
            "filter_by_practitioner_id_non_empty_result",
            "filter_by_practitioner_id_empty_result",
        ],
    )
    def test_get_appointment_ids_filter_by_practitioner_id(
        self,
        db: SQLAlchemy,
        provider_appointment_for_list_repo: ProviderAppointmentForListRepository,
        appointment_100: Appointment,
        appointment_200: Appointment,
        practitioner_id: Appointment,
        appointment_by_practitioner: str,
        expected_appt_ids: List[int],
        expected_total_count: int,
        request: FixtureRequest,
    ):
        if appointment_by_practitioner:
            practitioner_id = request.getfixturevalue(
                appointment_by_practitioner
            ).product.user_id
        filters = ProviderAppointmentFilter(practitioner_id=practitioner_id)
        with enable_db_performance_warnings(database=db, failure_threshold=3):
            (
                appt_ids,
                total_count,
            ) = provider_appointment_for_list_repo.get_appointment_ids_and_total_appointment_count(
                filters=filters
            )
            assert appt_ids == expected_appt_ids
            assert total_count == expected_total_count

    def test_get_appointment_ids_filter_by_member_id(
        self,
        db: SQLAlchemy,
        provider_appointment_for_list_repo: ProviderAppointmentForListRepository,
        appointment_100: Appointment,
        appointment_400: Appointment,
        appointment_500: Appointment,
        appointment_600: Appointment,
    ):
        filters = ProviderAppointmentFilter(
            member_id=appointment_400.member_schedule.user_id
        )
        with enable_db_performance_warnings(database=db, failure_threshold=3):
            (
                appt_ids,
                total_count,
            ) = provider_appointment_for_list_repo.get_appointment_ids_and_total_appointment_count(
                filters=filters, order_direction=OrderDirection.ASC
            )
            # appointment 100 should be filtered out
            assert appt_ids == [400, 500, 600]
            assert total_count == 3

    @pytest.mark.parametrize(
        argnames="scheduled_start,scheduled_end,expected_appt_ids,expected_total_count",
        argvalues=[
            (
                None,
                None,
                [100, 200, 300],
                3,
            ),
            (
                datetime(2023, 2, 1, 0, 0, 0),
                None,
                [200, 300],
                2,
            ),
            (
                None,
                datetime(2023, 2, 1, 11, 0, 0),
                [100, 200],
                2,
            ),
            (
                datetime(2023, 2, 1, 0, 0, 0),
                datetime(2023, 2, 15, 0, 0, 0),
                [200],
                1,
            ),
            (
                datetime(2024, 9, 1, 0, 0, 0),
                datetime(2024, 9, 15, 0, 0, 0),
                [],
                0,
            ),
        ],
        ids=[
            "no_time_filter",
            "filter_by_start_time",
            "filter_by_end_time",
            "filter_by_start_and_end_time_non_empty_result",
            "filter_by_start_and_end_time_empty_result",
        ],
    )
    def test_get_appointment_ids_filter_by_time(
        self,
        db: SQLAlchemy,
        provider_appointment_for_list_repo: ProviderAppointmentForListRepository,
        appointment_100: Appointment,
        appointment_200: Appointment,
        appointment_300: Appointment,
        scheduled_start: datetime,
        scheduled_end: datetime,
        expected_appt_ids: List[int],
        expected_total_count: int,
    ):
        filters = ProviderAppointmentFilter(
            scheduled_start=scheduled_start, scheduled_end=scheduled_end
        )
        with enable_db_performance_warnings(database=db, failure_threshold=3):
            (
                appt_ids,
                total_count,
            ) = provider_appointment_for_list_repo.get_appointment_ids_and_total_appointment_count(
                filters=filters
            )
            assert appt_ids == expected_appt_ids
            assert total_count == expected_total_count

    def test_get_appointment_ids_filter_by_schedule_event_ids(
        self,
        db: SQLAlchemy,
        provider_appointment_for_list_repo: ProviderAppointmentForListRepository,
        appointment_700: Appointment,
        appointment_800_cancelled: Appointment,
    ):
        filters = ProviderAppointmentFilter(
            schedule_event_ids=[
                appointment_700.schedule_event_id,
                appointment_800_cancelled.schedule_event_id,
            ]
        )
        with enable_db_performance_warnings(database=db, failure_threshold=3):
            (
                appt_ids,
                total_count,
            ) = provider_appointment_for_list_repo.get_appointment_ids_and_total_appointment_count(
                filters=filters
            )
            assert appt_ids == [700, 800]
            assert total_count == 2

    def test_get_appointment_ids_filter_out_cancelled_appointment(
        self,
        db: SQLAlchemy,
        provider_appointment_for_list_repo: ProviderAppointmentForListRepository,
        appointment_700: Appointment,
        appointment_800_cancelled: Appointment,
    ):
        filters = ProviderAppointmentFilter(
            schedule_event_ids=[
                appointment_700.schedule_event_id,
                appointment_800_cancelled.schedule_event_id,
            ],
            exclude_statuses=[APPOINTMENT_STATES.cancelled],
        )
        with enable_db_performance_warnings(database=db, failure_threshold=3):
            (
                appt_ids,
                total_count,
            ) = provider_appointment_for_list_repo.get_appointment_ids_and_total_appointment_count(
                filters=filters
            )
            # appointment 800 should be filtered out since it's cancelled
            assert appt_ids == [700]
            assert total_count == 1

    @pytest.mark.parametrize(
        argnames="order_direction,expected_appt_ids,expected_total_count",
        argvalues=[
            (None, [100, 200, 300], 3),
            (OrderDirection.ASC, [100, 200, 300], 3),
            (OrderDirection.DESC, [300, 200, 100], 3),
        ],
        ids=[
            "no_order_direction_default_to_asc",
            "order_direction_asc",
            "order_direction_desc",
        ],
    )
    def test_get_appointment_ids_with_order_direction(
        self,
        db: SQLAlchemy,
        provider_appointment_for_list_repo: ProviderAppointmentForListRepository,
        appointment_100: Appointment,
        appointment_200: Appointment,
        appointment_300: Appointment,
        order_direction: OrderDirection,
        expected_appt_ids: List[int],
        expected_total_count: int,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=3):
            (
                appt_ids,
                total_count,
            ) = provider_appointment_for_list_repo.get_appointment_ids_and_total_appointment_count(
                order_direction=order_direction
            )
            assert appt_ids == expected_appt_ids
            assert total_count == expected_total_count

    @pytest.mark.parametrize(
        argnames="limit,offset,expected_appt_ids,expected_total_count",
        argvalues=[
            (None, None, [100, 200, 300, 400, 500], 6),
            (1, None, [100], 6),
            (2, 1, [200, 300], 6),
        ],
        ids=[
            "no_limit_and_no_offset_use_default_value",
            "has_limit_but_no_offset",
            "has_limit_and_offset",
        ],
    )
    def test_get_appointment_ids_with_limit_and_offset(
        self,
        db: SQLAlchemy,
        provider_appointment_for_list_repo: ProviderAppointmentForListRepository,
        appointment_100: Appointment,
        appointment_200: Appointment,
        appointment_300: Appointment,
        appointment_400: Appointment,
        appointment_500: Appointment,
        appointment_600: Appointment,
        limit: int | None,
        offset: int | None,
        expected_appt_ids: List[int],
        expected_total_count: int,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=3):
            (
                appt_ids,
                total_count,
            ) = provider_appointment_for_list_repo.get_appointment_ids_and_total_appointment_count(
                limit=limit, offset=offset
            )
            assert appt_ids == expected_appt_ids
            assert total_count == expected_total_count

    @pytest.mark.parametrize(
        argnames="order_direction,expected_appts",
        argvalues=[
            (
                None,
                [
                    "appointment_for_list_100",
                    "appointment_for_list_200",
                    "appointment_for_list_300",
                    "appointment_for_list_400",
                    "appointment_for_list_500",
                    "appointment_for_list_600",
                ],
            ),
            (
                OrderDirection.ASC,
                [
                    "appointment_for_list_100",
                    "appointment_for_list_200",
                    "appointment_for_list_300",
                    "appointment_for_list_400",
                    "appointment_for_list_500",
                    "appointment_for_list_600",
                ],
            ),
            (
                OrderDirection.DESC,
                [
                    "appointment_for_list_600",
                    "appointment_for_list_500",
                    "appointment_for_list_400",
                    "appointment_for_list_300",
                    "appointment_for_list_200",
                    "appointment_for_list_100",
                ],
            ),
        ],
        ids=[
            "no_order_direction_default_to_asc",
            "order_direction_acs",
            "order_direction_desc",
        ],
    )
    def test_get_appointments_by_ids(
        self,
        db: SQLAlchemy,
        provider_appointment_for_list_repo: ProviderAppointmentForListRepository,
        appointment_100: Appointment,
        appointment_200: Appointment,
        appointment_300: Appointment,
        appointment_400: Appointment,
        appointment_500: Appointment,
        appointment_600: Appointment,
        reschedule_history_101: RescheduleHistory,
        reschedule_history_102: RescheduleHistory,
        reschedule_history_201: RescheduleHistory,
        appointment_for_list_100: ProviderAppointmentForList,
        appointment_for_list_200: ProviderAppointmentForList,
        appointment_for_list_300: ProviderAppointmentForList,
        appointment_for_list_400: ProviderAppointmentForList,
        appointment_for_list_500: ProviderAppointmentForList,
        appointment_for_list_600: ProviderAppointmentForList,
        order_direction: OrderDirection,
        expected_appts: List[str],
        request: FixtureRequest,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = provider_appointment_for_list_repo.get_appointments_by_ids(
                [
                    appointment_100.id,
                    appointment_200.id,
                    appointment_300.id,
                    appointment_400.id,
                    appointment_500.id,
                    appointment_600.id,
                ],
                order_direction,
            )
            expected_appts_for_list = []
            for appt in expected_appts:
                expected_appts_for_list.append(request.getfixturevalue(appt))
            assert result == expected_appts_for_list

    def test_get_paginated_appointments_with_total_count(
        self,
        db: SQLAlchemy,
        provider_appointment_for_list_repo: ProviderAppointmentForListRepository,
        appointment_100: Appointment,
        appointment_200: Appointment,
        appointment_300: Appointment,
        appointment_400: Appointment,
        appointment_500: Appointment,
        appointment_for_list_500: ProviderAppointmentForList,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=4):
            filters = ProviderAppointmentFilter(
                practitioner_id=appointment_for_list_500.practitioner_id,
                scheduled_start=datetime(2023, 4, 1, 10, 0, 0),
                scheduled_end=datetime(2024, 4, 1, 10, 0, 0),
            )
            (
                appts,
                total_count,
            ) = provider_appointment_for_list_repo.get_paginated_appointments_with_total_count(
                filters=filters, order_direction=OrderDirection.DESC, limit=1, offset=0
            )
            assert appts == [appointment_for_list_500]
            assert total_count == 2

    def test_get_paginated_appointments_with_total_count_order_by_desc(
        self,
        db: SQLAlchemy,
        provider_appointment_for_list_repo: ProviderAppointmentForListRepository,
        appointment_100: Appointment,
        appointment_200: Appointment,
        appointment_300: Appointment,
        appointment_400: Appointment,
        appointment_500: Appointment,
        appointment_600: Appointment,
        appointment_for_list_200: ProviderAppointmentForList,
        appointment_for_list_300: ProviderAppointmentForList,
        appointment_for_list_400: ProviderAppointmentForList,
        appointment_for_list_500: ProviderAppointmentForList,
        appointment_for_list_600: ProviderAppointmentForList,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=4):
            (
                appts,
                total_count,
            ) = provider_appointment_for_list_repo.get_paginated_appointments_with_total_count(
                filters=ProviderAppointmentFilter(), order_direction=OrderDirection.DESC
            )
            # when limit is not in request, the default value is 5
            assert appts == [
                appointment_for_list_600,
                appointment_for_list_500,
                appointment_for_list_400,
                appointment_for_list_300,
                appointment_for_list_200,
            ]
            assert total_count == 6

    def test_get_appointment_id_to_latest_post_session_note_no_data(
        self,
        db: SQLAlchemy,
        provider_appointment_for_list_repo: ProviderAppointmentForListRepository,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=1):
            result = provider_appointment_for_list_repo.get_appointment_id_to_latest_post_session_note(
                appointment_ids=[]
            )
            assert result == {}

        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = provider_appointment_for_list_repo.get_appointment_id_to_latest_post_session_note(
                appointment_ids=[404]
            )
            assert result == {}

    def test_get_appointment_id_to_latest_post_session_note_with_data(
        self,
        db: SQLAlchemy,
        provider_appointment_for_list_repo: ProviderAppointmentForListRepository,
        appointment_100: Appointment,
        appointment_200: Appointment,
        appointment_300: Appointment,
    ):
        with enable_db_performance_warnings(database=db, failure_threshold=2):
            result = provider_appointment_for_list_repo.get_appointment_id_to_latest_post_session_note(
                appointment_ids=[100, 200, 300]
            )
            assert len(result) == 2
            assert result[100] == SessionMetaInfo(
                created_at=datetime(2023, 2, 1, 10, 0, 0),
                notes="metadata content 103",
                draft=False,
            )
            assert result[300] == SessionMetaInfo(
                created_at=datetime(2023, 3, 2, 10, 00, 00),
                notes="metadata content 301",
                draft=True,
            )
