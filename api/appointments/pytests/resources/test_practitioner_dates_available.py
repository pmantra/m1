import datetime
import json

from appointments.utils.booking import DATE_STRING_FORMAT
from pytests import freezegun


class TestPractitionerDatesAvailablePartitionedDates:
    @freezegun.freeze_time("2022-11-11 06:00:00.0")
    def test_post_practitioner_dates_available(
        self,
        api_helpers,
        client,
        create_practitioner,
        factories,
        add_schedule_event,
    ):
        """
        Tests that combined practitioner availability is provided in the appropriate response object
        """
        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()

        available_dates = [
            now,
            (now + datetime.timedelta(days=1)),
            (now + datetime.timedelta(days=5)),
            (now + datetime.timedelta(days=8)),
        ]

        available_date_set = {date.strftime("%Y-%m-%d") for date in available_dates}

        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
        )
        add_schedule_event(practitioner, available_dates[0], 1)
        add_schedule_event(practitioner, available_dates[1], 1)

        practitioner2 = create_practitioner(
            practitioner_profile__next_availability=now,
        )
        add_schedule_event(practitioner2, available_dates[2], 1)
        add_schedule_event(practitioner2, available_dates[3], 1)

        data = {
            "practitioner_ids": [practitioner.id, practitioner2.id],
            "member_timezone": "America/New_York",
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        for availability_result in availabilities:
            if availability_result["date"] in available_date_set:
                assert availability_result["hasAvailability"] is True
            else:
                assert availability_result["hasAvailability"] is False

    @freezegun.freeze_time("2022-11-11 12:00:00.0")
    def test_post_practitioner_returns_error_on_invalid_input(
        self,
        api_helpers,
        client,
        create_practitioner,
        factories,
        add_schedule_event,
    ):
        """
        Tests that endpoint correctly errors when input is invalid
        """

        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()

        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
        )
        add_schedule_event(practitioner, now, 1)

        data = {
            "practitioner_ids": [practitioner.id],
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        assert res.status_code == 400
        expected_err = {
            "error": "Invalid timezone request",
            "errors": [
                {
                    "status": 400,
                    "title": "Bad Request",
                    "detail": "Invalid timezone request",
                }
            ],
        }
        assert res.json == expected_err

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
            "start_time": "2022-11-12T12:00:00+00:00",
            "end_time": "2023-01-12T12:00:00+00:00",
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        assert res.status_code == 400
        expected_err = {
            "error": "Requested date range exceeds limit",
            "errors": [
                {
                    "status": 400,
                    "title": "Bad Request",
                    "detail": "Requested date range exceeds limit",
                }
            ],
        }
        assert res.json == expected_err

    @freezegun.freeze_time("2022-11-11 12:00:00.0")
    def test_post_practitioner_dates_available_no_availability(
        self,
        api_helpers,
        client,
        create_practitioner,
        factories,
        add_schedule_event,
    ):
        """
        Tests that no availability is returned when open appointments are beyond the default date range
        """
        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()

        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
        )
        add_schedule_event(practitioner, (now + datetime.timedelta(days=40)), 1)

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        assert all(
            availability_result["hasAvailability"] is False
            for availability_result in availabilities
        )

    @freezegun.freeze_time("2022-11-11 12:00:00.0")
    def test_post_practitioner_dates_available_searches_provided_time_frame(
        self,
        api_helpers,
        client,
        create_practitioner,
        factories,
        add_schedule_event,
    ):
        """
        Tests that endpoint returns only appointment availability within provided date range
        """
        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()

        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
        )

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
            "start_time": "2022-11-12T12:00:00+00:00",
            "end_time": "2022-11-16T12:00:00+00:00",
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        expected_start_date = datetime.datetime.strptime(
            data["start_time"][:19], "%Y-%m-%dT%H:%M:%S"
        )
        _assert_proper_response_data(
            availabilities,
            expected_start_date,
            5,
        )

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
            "start_time": "2022-11-12T12:00:00+00:00",
            "end_time": "2022-12-02T12:00:00+00:00",
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(
            availabilities,
            expected_start_date,
            21,
        )

    @freezegun.freeze_time("2022-11-11 12:00:00.0")
    def test_post_practitioner_dates_available_filters_by_provider_type(
        self,
        api_helpers,
        client,
        create_practitioner,
        factories,
        add_schedule_event,
    ):
        """
        Tests that endpoint filters practitioners by provided vertical value
        """
        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()

        vertical_name = "Availability Vertical"
        test_vertical = factories.VerticalFactory(name=vertical_name)
        test_product = factories.ProductFactory(vertical=test_vertical)

        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
            practitioner_profile__verticals=[test_vertical],
            products=[test_product],
        )

        available_date = now + datetime.timedelta(days=10)
        add_schedule_event(practitioner, available_date, 1)

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
            "provider_type": "Incorrect Vertical",
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        assert all(
            availability_result["hasAvailability"] is False
            for availability_result in availabilities
        )

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
            "provider_type": vertical_name,
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        available_date_str = available_date.strftime(DATE_STRING_FORMAT)
        for availability_result in availabilities:
            if availability_result["date"] == available_date_str:
                assert availability_result["hasAvailability"] is True
            else:
                assert availability_result["hasAvailability"] is False

    @freezegun.freeze_time("2022-11-11 12:00:00.0")
    def test_post_practitioner_dates_available_queries_can_prescribe(
        self,
        api_helpers,
        client,
        create_practitioner,
        factories,
        add_schedule_event,
    ):
        """
        Tests that endpoint filters practitioners by "can_prescribe" value
        """
        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()

        non_prescribe_vertical_name = "Non-Prescribe Vertical"
        non_prescribe_vertical = factories.VerticalFactory(
            name=non_prescribe_vertical_name, can_prescribe=False
        )
        non_prescribe_product = factories.ProductFactory(
            vertical=non_prescribe_vertical
        )

        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
            practitioner_profile__verticals=[non_prescribe_vertical],
            practitioner_profile__dosespot=json.dumps({"abc": 123}),
            products=[non_prescribe_product],
        )

        add_schedule_event(practitioner, (now + datetime.timedelta(days=10)), 1)

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
            "can_prescribe": True,
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        assert all(
            availability_result["hasAvailability"] is False
            for availability_result in availabilities
        )

        prescribe_vertical_name = "Prescribe Vertical"
        prescribe_vertical = factories.VerticalFactory(
            name=prescribe_vertical_name, can_prescribe=True
        )
        prescribe_product = factories.ProductFactory(vertical=prescribe_vertical)

        can_prescribe_practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
            practitioner_profile__verticals=[prescribe_vertical],
            practitioner_profile__dosespot=json.dumps({"abc": 123}),
            products=[prescribe_product],
        )

        available_date = now + datetime.timedelta(days=11)
        add_schedule_event(can_prescribe_practitioner, available_date, 1)

        data = {
            "practitioner_ids": [practitioner.id, can_prescribe_practitioner.id],
            "member_timezone": "America/New_York",
            "can_prescribe": True,
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        available_date_str = available_date.strftime(DATE_STRING_FORMAT)
        for availability_result in availabilities:
            if availability_result["date"] == available_date_str:
                assert availability_result["hasAvailability"] is True
            else:
                assert availability_result["hasAvailability"] is False

    @freezegun.freeze_time("2022-11-11 09:00:00.0")
    def test_post_practitioner_filter_unavailable_dates(
        self,
        api_helpers,
        client,
        create_practitioner,
        factories,
        add_schedule_event,
        valid_appointment_with_user,
    ):
        """
        Tests that availability is False for any dates that are marked as "unavailable"
        """

        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()
        member_schedule = factories.ScheduleFactory.create(user=member)

        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
        )
        product = practitioner.products[0]

        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        unavailable_date = now + datetime.timedelta(days=3)
        event = add_schedule_event(practitioner, unavailable_date, 20)

        scheduled_start = event.starts_at
        scheduled_end = scheduled_start + datetime.timedelta(minutes=product.minutes)

        for _ in range(aa.max_capacity):
            valid_appointment_with_user(
                practitioner,
                scheduled_start=scheduled_start,
                scheduled_end=scheduled_end,
                member_schedule=member_schedule,
            )

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        assert all(
            availability_result["hasAvailability"] is False
            for availability_result in availabilities
        )

    @freezegun.freeze_time("2022-11-11 09:00:00.0")
    def test_post_practitioners_availabilities_no_product(
        self,
        factories,
        client,
        api_helpers,
        create_practitioner,
    ):
        """
        Tests that endpoint filters practitioners with no available products
        """
        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()
        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
        )
        practitioner.products = []

        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=now,
            ends_at=now + datetime.timedelta(minutes=60),
        )

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        assert all(
            availability_result["hasAvailability"] is False
            for availability_result in availabilities
        )

    @freezegun.freeze_time("2022-11-11 23:00:00.0")
    def test_post_practitioners_computes_availability_for_schedules_overlapping_dates(
        self,
        factories,
        client,
        api_helpers,
        create_practitioner,
        add_schedule_event,
    ):
        """
        Tests that endpoint filters accurately handles a schedule that overlaps two dates (after timezone conversion)
        """
        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()
        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
        )

        available_dates = [
            now,
            now + datetime.timedelta(days=1),
        ]

        available_date_set = {date.strftime("%Y-%m-%d") for date in available_dates}
        add_schedule_event(practitioner, available_dates[0], 60)

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        for availability_result in availabilities:
            if availability_result["date"] in available_date_set:
                assert availability_result["hasAvailability"] is True
            else:
                assert availability_result["hasAvailability"] is False

    @freezegun.freeze_time("2022-11-11 23:00:00.0")
    def test_post_practitioners_computes_availability_for_schedules_spanning_several_dates(
        self,
        factories,
        client,
        api_helpers,
        create_practitioner,
        add_schedule_event,
    ):
        """
        Tests that endpoint filters accurately handles a schedule that overlaps two dates (after timezone conversion)
        """
        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()
        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
        )

        available_dates = [(now + datetime.timedelta(days=i)) for i in range(21)]

        available_date_set = {date.strftime("%Y-%m-%d") for date in available_dates}
        add_schedule_event(practitioner, available_dates[0], 2880)

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        for availability_result in availabilities:
            if availability_result["date"] in available_date_set:
                assert availability_result["hasAvailability"] is True
            else:
                assert availability_result["hasAvailability"] is False

    @freezegun.freeze_time("2022-11-11 02:00:00.0")
    def test_post_practitioner_adds_buffer_to_availability_search_end_date(
        self,
        api_helpers,
        client,
        create_practitioner,
        factories,
        add_schedule_event,
    ):
        """
        Tests that endpoint captures ScheduledEvent that is before searchable time range in UTC but
        within range after timezone conversion
        """
        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()

        available_date = (now + datetime.timedelta(days=29)).strftime("%Y-%m-%d")

        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
        )
        # Add appointment for the 31st day from now (in UTC)
        add_schedule_event(practitioner, (now + datetime.timedelta(days=30)), 1)

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        for availability_result in availabilities:
            if availability_result["date"] == available_date:
                assert availability_result["hasAvailability"] is True
            else:
                assert availability_result["hasAvailability"] is False

    @freezegun.freeze_time("2022-11-11 20:00:00.0")
    def test_post_practitioner_adds_buffer_to_availability_search_start_date(
        self,
        api_helpers,
        client,
        create_practitioner,
        factories,
        add_schedule_event,
    ):
        """
        Tests that endpoint captures ScheduledEvent that is after the searchable time range in UTC but
        within range after timezone conversion
        """
        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()
        available_date = now.strftime("%Y-%m-%d")

        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
        )
        # Add appointment for the 31st day from now (in UTC)
        add_schedule_event(practitioner, (now - datetime.timedelta(days=1)), 1)

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "Japan",
        }

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        for availability_result in availabilities:
            if availability_result["date"] == available_date:
                assert availability_result["hasAvailability"] is True
            else:
                assert availability_result["hasAvailability"] is False

    @freezegun.freeze_time("2022-11-11 06:00:00.0")
    def test_post_practitioner_handles_availability_duration_smaller_than_appointment_duration(
        self,
        api_helpers,
        client,
        create_practitioner,
        factories,
        add_schedule_event,
        valid_appointment_with_user,
    ):
        """
        Tests that endpoint properly filters potential appointments that overlap the end of
        the practitioner's schedule end time
        """
        now = datetime.datetime.utcnow()
        member = factories.EnterpriseUserFactory.create()
        member_schedule = factories.ScheduleFactory.create(user=member)

        practitioner = create_practitioner(
            practitioner_profile__next_availability=now,
        )
        event = add_schedule_event(practitioner, now, 1.5)

        data = {
            "practitioner_ids": [practitioner.id],
            "member_timezone": "America/New_York",
        }

        valid_appointment_with_user(
            practitioner,
            scheduled_start=event.starts_at,
            scheduled_end=event.starts_at
            + datetime.timedelta(minutes=practitioner.default_product.minutes),
            member_schedule=member_schedule,
        )

        res = client.post(
            "/api/v1/practitioners/dates_available",
            data=json.dumps(data),
            headers=api_helpers.json_headers(member),
        )

        res_data = json.loads(res.data)
        availabilities = res_data.get("data")

        _assert_proper_response_data(availabilities, now)
        assert all(
            availability_result["hasAvailability"] is False
            for availability_result in availabilities
        )


def _assert_proper_response_data(availabilities, start_date, expected_range=30):
    assert len(availabilities) == expected_range

    # ensure all dates are unique
    availability_dates = [
        availability_result["date"] for availability_result in availabilities
    ]
    assert len(set(availability_dates)) == len(availability_dates)

    expected_date_set = {
        (start_date + datetime.timedelta(days=delta)).strftime(DATE_STRING_FORMAT)
        for delta in range(0, expected_range)
    }

    assert all(
        availability_date in expected_date_set
        for availability_date in availability_dates
    )
