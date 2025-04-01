import datetime
import json
from unittest import mock
from unittest.mock import call

import factory
import pytest

from admin.views.models.practitioner import PractitionerHelpers
from appointments.models.appointment import Appointment
from appointments.models.constants import ScheduleStates


@pytest.fixture
def eligible_member(factories):
    member = factories.EnterpriseUserFactory.create()
    factories.ScheduleFactory.create(user=member)
    return member


@pytest.fixture
def eligible_practitioner(factories):
    product = factories.ProductFactory.create(
        minutes=60, price=60, vertical__products=[{"minutes": 60, "price": 60}]
    )
    practitioner = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[product.vertical], products=[product]
    )
    product.practitioner = practitioner
    assert practitioner.products == [product]
    return practitioner


@pytest.fixture
def schedule_start_date():
    return datetime.datetime.utcnow().replace(second=0, microsecond=0)


@pytest.fixture
def practitioner_schedule(factories, eligible_practitioner, schedule_start_date):
    factories.ScheduleEventFactory.create(
        schedule=eligible_practitioner.schedule,
        starts_at=schedule_start_date,
        ends_at=schedule_start_date + datetime.timedelta(minutes=120),
        state=ScheduleStates.available,
    )


@pytest.fixture
def complicated_schedule_start_date():
    return datetime.datetime.utcnow().replace(
        hour=0, second=0, minute=0, microsecond=0
    ) + datetime.timedelta(days=2)


@pytest.fixture
def complicated_practitioner_schedule(
    factories, eligible_practitioner, eligible_member, complicated_schedule_start_date
):
    # set up availability
    date = complicated_schedule_start_date
    factories.ScheduleEventFactory.create_batch(
        size=2,
        schedule=eligible_practitioner.schedule,
        starts_at=factory.Iterator(
            [
                date + datetime.timedelta(hours=17),
                date + datetime.timedelta(hours=17, days=1),
            ]
        ),
        ends_at=factory.Iterator(
            [
                date + datetime.timedelta(hours=21),
                date + datetime.timedelta(hours=21, days=1),
            ]
        ),
        state=ScheduleStates.available,
    )

    # add 40m product
    new_product = factories.ProductFactory.create(
        practitioner=eligible_practitioner, minutes=40, price=40
    )

    # Add appointments:
    factories.AppointmentFactory.create_batch(
        size=3,
        member_schedule=eligible_member.schedule,
        scheduled_start=factory.Iterator(
            [
                date + datetime.timedelta(hours=17),
                date + datetime.timedelta(hours=17),
                date + datetime.timedelta(hours=18),
            ]
        ),
        scheduled_end=factory.Iterator(
            [
                date + datetime.timedelta(hours=17, minutes=40),
                date + datetime.timedelta(hours=17, minutes=40),
                date + datetime.timedelta(hours=18, minutes=40),
            ]
        ),
        cancelled_at=factory.Iterator(
            [None, datetime.datetime.utcnow(), datetime.datetime.utcnow()]
        ),
        product=new_product,
    )


@pytest.fixture
def ten_minute_product(factories, eligible_practitioner):
    return factories.ProductFactory.create(
        practitioner=eligible_practitioner, minutes=10, price=10
    )


class TestProactiveBookingShow:
    def test_showing_avail_times(
        self,
        admin_client,
        factories,
        eligible_member,
        eligible_practitioner,
        schedule_start_date,
        ten_minute_product,
    ):
        product = ten_minute_product
        factories.ScheduleEventFactory.create(
            schedule=eligible_practitioner.schedule,
            starts_at=schedule_start_date + datetime.timedelta(minutes=30),
            ends_at=schedule_start_date + datetime.timedelta(minutes=120),
            state=ScheduleStates.available,
        )
        factories.AppointmentFactory.create(
            member_schedule=eligible_member.schedule,
            product=product,
            scheduled_start=schedule_start_date + datetime.timedelta(minutes=30),
            scheduled_end=schedule_start_date + datetime.timedelta(minutes=60),
        )
        res = admin_client.get(
            f"/admin/practitionerprofile/bookable_times?id={eligible_practitioner.id}&product_id={product.id}",
            follow_redirects=True,
        )

        data = json.loads(res.data.decode("utf8"))
        assert len(data["available_times"]) == 6

    @pytest.mark.parametrize(
        "start_days,end_days,append_url",
        [
            (55, 80, "&days=55"),
            (24, 30, ""),
            (24, 30, "&days=foo"),
        ],
        ids=["with_days", "with_default_days", "with_invalid_days"],
    )
    def test_bookable_times(
        self,
        admin_client,
        factories,
        eligible_member,
        eligible_practitioner,
        ten_minute_product,
        start_days,
        end_days,
        append_url,
    ):
        product = ten_minute_product
        start_date = datetime.datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        date_in_range = start_date + datetime.timedelta(days=start_days)
        date_out_of_range = start_date + datetime.timedelta(days=end_days)
        factories.ScheduleEventFactory.create_batch(
            size=4,
            schedule=eligible_practitioner.schedule,
            starts_at=factory.Iterator(
                [
                    date_in_range + datetime.timedelta(hours=17),
                    date_in_range + datetime.timedelta(hours=18),
                    date_out_of_range + datetime.timedelta(hours=17),
                    date_out_of_range + datetime.timedelta(hours=18),
                ]
            ),
            ends_at=factory.Iterator(
                [
                    date_in_range + datetime.timedelta(hours=18),
                    date_in_range + datetime.timedelta(hours=19),
                    date_out_of_range + datetime.timedelta(hours=18),
                    date_out_of_range + datetime.timedelta(hours=19),
                ]
            ),
            state=ScheduleStates.available,
        )
        res = admin_client.get(
            f"/admin/practitionerprofile/bookable_times?"
            f"id={eligible_practitioner.id}"
            f"&product_id={product.id}"
            f"{append_url}",
            follow_redirects=True,
        )

        data = json.loads(res.data.decode("utf8"))
        """
        The number of items returned from bookable_times is based on 10 minute time blocks
        for the number of hours of availability.

        In this case: we have 2 hours of availability (5pm - 7pm) in day range with 10 minute blocks.
        This means we have 6 bookable times per hour for 2 hours = 12 bookable times.
        """
        assert len(data["scheduled_availability"]) == 4
        assert len(data["available_times"]) == 12

    @pytest.mark.parametrize("days", [100, 20], ids=["above_max", "below_min"])
    def test_bookable_times_with_invalid_days(
        self, admin_client, eligible_practitioner, days
    ):
        product = eligible_practitioner.products[0]
        res = admin_client.get(
            f"/admin/practitionerprofile/bookable_times?"
            f"id={eligible_practitioner.id}&product_id={product.id}&days={days}",
            follow_redirects=True,
        )
        data = json.loads(res.data.decode("utf8"))
        assert data == {
            "error": f"Please enter a time span between {PractitionerHelpers.BOOKABLE_TIMES_MIN_DAYS} and {PractitionerHelpers.BOOKABLE_TIMES_MAX_DAYS} days"
        }

    def test_showing_avail_times_with_canceled_appts(
        self,
        admin_client,
        factories,
        eligible_member,
        eligible_practitioner,
        complicated_practitioner_schedule,
    ):
        product = eligible_practitioner.products[0]
        res = admin_client.get(
            f"/admin/practitionerprofile/bookable_times?id={eligible_practitioner.id}&product_id={product.id}",
            follow_redirects=True,
        )

        data = json.loads(res.data.decode("utf8"))
        assert len(data["available_times"]) == 7
        assert len(data["scheduled_availability"]) == 2


class TestProactiveBooking:
    @pytest.mark.parametrize(
        "original_purpose,calculated_purpose,expected",
        [
            ("", "introduction", "introduction"),
            ("introduction", "birth_needs_assessment", "introduction"),
            ("childbirth_ed", "postpartum_planning", "childbirth_ed"),
            ("childbirth_ed", "introduction", "introduction"),
        ],
        ids=[
            "no_purpose_provided",
            "both_intros",
            "neither_intros",
            "calculated_intro_original_not_intro",
        ],
    )
    def test_proactive_booking_purpose(
        self,
        admin_client,
        factories,
        eligible_member,
        eligible_practitioner,
        practitioner_schedule,
        schedule_start_date,
        original_purpose,
        calculated_purpose,
        expected,
    ):
        scheduled_start = schedule_start_date + datetime.timedelta(minutes=60)
        product = eligible_practitioner.products[0]
        factories.CreditFactory.create(user=eligible_member, amount=product.price)

        with mock.patch("admin.blueprints.actions.flash") as flash, mock.patch(
            "admin.blueprints.actions.check_intro_appointment_purpose"
        ) as mock_calculated_purpose:
            mock_calculated_purpose.return_value = calculated_purpose
            res = admin_client.post(
                "/admin/actions/proactive_booking",
                data={
                    "product_id": product.id,
                    "user_id": eligible_member.id,
                    "purpose": original_purpose,
                    "scheduled_start": scheduled_start.isoformat(),
                },
            )

        assert res.status_code == 302
        assert res.location == f"/admin/memberprofile/edit/?id={eligible_member.id}"
        appt = Appointment.query.filter(Appointment.product_id == product.id).one()
        assert appt.purpose == expected
        assert (
            f"Appointment was booked!<Appointment {appt.id} [SCHEDULED @ {scheduled_start.strftime('%Y-%m-%d %H:%M:%S')}]>"
            == flash.call_args[0][0]
        )

    def test_proactive_booking_credits(
        self,
        admin_client,
        factories,
        eligible_member,
        eligible_practitioner,
        practitioner_schedule,
        schedule_start_date,
    ):
        scheduled_start = schedule_start_date + datetime.timedelta(minutes=60)
        product = eligible_practitioner.products[0]
        factories.CreditFactory.create(user=eligible_member, amount=product.price)

        with mock.patch("admin.blueprints.actions.flash"), mock.patch(
            "admin.blueprints.actions.check_intro_appointment_purpose"
        ) as mock_calculated_purpose:
            mock_calculated_purpose.return_value = "introduction"
            res = admin_client.post(
                "/admin/actions/proactive_booking",
                data={
                    "product_id": product.id,
                    "user_id": eligible_member.id,
                    "purpose": "introduction",
                    "scheduled_start": scheduled_start.isoformat(),
                },
            )

        assert res.status_code == 302
        appt = Appointment.query.filter(Appointment.product_id == product.id).one()
        assert len(appt.credits) > 0

    def test_proactive_booking_purpose_error_not_intro(
        self,
        admin_client,
        factories,
        eligible_member,
        eligible_practitioner,
        practitioner_schedule,
        schedule_start_date,
    ):
        scheduled_start = schedule_start_date + datetime.timedelta(minutes=60)
        product = eligible_practitioner.products[0]
        factories.CreditFactory.create(user=eligible_member, amount=product.price)
        original_purpose = "introduction"
        calculated_purpose = "postpartum_planning"

        with mock.patch("admin.blueprints.actions.flash") as flash, mock.patch(
            "admin.blueprints.actions.check_intro_appointment_purpose"
        ) as mock_calculated_purpose:
            mock_calculated_purpose.return_value = calculated_purpose
            res = admin_client.post(
                "/admin/actions/proactive_booking",
                data={
                    "product_id": product.id,
                    "user_id": eligible_member.id,
                    "purpose": original_purpose,
                    "scheduled_start": scheduled_start.isoformat(),
                },
            )

        assert res.status_code == 302
        assert res.location == f"/admin/memberprofile/edit/?id={eligible_member.id}"
        assert (
            "This appointment does not appear to be an intro appointment. "
            "The member may have had a previous CA appointment in their current track or a previous track. "
            "Please choose a different purpose or leave the field blank."
            == flash.call_args[0][0]
        )

    def test_proactive_booking(
        self,
        admin_client,
        factories,
        eligible_member,
        eligible_practitioner,
        practitioner_schedule,
        schedule_start_date,
    ):
        scheduled_start = schedule_start_date + datetime.timedelta(minutes=60)
        product = eligible_practitioner.products[0]
        factories.CreditFactory.create(user=eligible_member, amount=product.price)

        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/proactive_booking",
                data={
                    "product_id": product.id,
                    "user_id": eligible_member.id,
                    "purpose": "",
                    "scheduled_start": scheduled_start.isoformat(),
                },
            )
        assert res.status_code == 302
        assert res.location == f"/admin/memberprofile/edit/?id={eligible_member.id}"
        assert "Appointment was booked!" in flash.call_args[0][0]

    def test_proactive_booking_without_credit_does_not_work(
        self,
        admin_client,
        factories,
        eligible_member,
        eligible_practitioner,
        practitioner_schedule,
        schedule_start_date,
    ):
        scheduled_start = schedule_start_date + datetime.timedelta(minutes=60)
        product = eligible_practitioner.products[0]
        factories.CreditFactory.create(
            user=eligible_member, amount=0  # not enough credits
        )

        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/proactive_booking",
                data={
                    "product_id": product.id,
                    "user_id": eligible_member.id,
                    "purpose": "",
                    "scheduled_start": scheduled_start.isoformat(),
                },
            )
        assert res.status_code == 302
        assert res.location == f"/admin/memberprofile/edit/?id={eligible_member.id}"
        assert "Payment issue!" == flash.call_args[0][0]

    def test_proactive_booking_bad_tz(
        self,
        admin_client,
        factories,
        eligible_member,
        eligible_practitioner,
        practitioner_schedule,
        schedule_start_date,
    ):
        scheduled_start = schedule_start_date + datetime.timedelta(minutes=60)
        product = eligible_practitioner.products[0]
        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/proactive_booking",
                data={
                    "product_id": product.id,
                    "user_id": eligible_member.id,
                    "purpose": "",
                    "scheduled_start": scheduled_start.isoformat() + "+5",
                },
            )
        assert res.status_code == 302
        assert res.location == f"/admin/memberprofile/edit/?id={eligible_member.id}"
        assert flash.call_args == call(
            "Error: Do not specify timezone in date", category="error"
        )

    def test_proactive_booking_over_canceled_appointment_of_different_product(
        self,
        admin_client,
        factories,
        eligible_member,
        eligible_practitioner,
        complicated_practitioner_schedule,
        complicated_schedule_start_date,
    ):
        product = eligible_practitioner.products[0]
        scheduled_start = complicated_schedule_start_date + datetime.timedelta(hours=18)
        factories.CreditFactory.create(user=eligible_member, amount=product.price)

        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/proactive_booking",
                data={
                    "product_id": product.id,
                    "user_id": eligible_member.id,
                    "purpose": "",
                    "scheduled_start": scheduled_start.isoformat(),
                },
            )
        assert res.status_code == 302
        assert res.location == f"/admin/memberprofile/edit/?id={eligible_member.id}"
        assert "Appointment was booked!" in flash.call_args[0][0]
        appt = Appointment.query.order_by(Appointment.id.desc()).first()
        assert appt.scheduled_start == scheduled_start
        assert appt.scheduled_end == scheduled_start + datetime.timedelta(
            minutes=product.minutes
        )

    def test_proactive_booking_schedule_event_set(
        self,
        admin_client,
        factories,
        eligible_member,
        eligible_practitioner,
        complicated_practitioner_schedule,
        complicated_schedule_start_date,
    ):
        product = eligible_practitioner.products[0]
        scheduled_start = complicated_schedule_start_date + datetime.timedelta(hours=20)
        factories.CreditFactory.create(user=eligible_member, amount=product.price)

        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/proactive_booking",
                data={
                    "product_id": product.id,
                    "user_id": eligible_member.id,
                    "anonymous_appointment": "False",
                    "purpose": "",
                    "scheduled_start": scheduled_start.isoformat(),
                },
            )
        assert res.status_code == 302
        assert res.location == f"/admin/memberprofile/edit/?id={eligible_member.id}"
        assert "Appointment was booked!" in flash.call_args[0][0]

        appt = Appointment.query.order_by(Appointment.id.desc()).first()
        assert appt.scheduled_start == scheduled_start
        assert appt.scheduled_end == scheduled_start + datetime.timedelta(
            minutes=product.minutes
        )
        assert appt.schedule_event_id is not None
        assert appt.scheduled_start >= appt.schedule_event.starts_at
        assert appt.scheduled_end <= appt.schedule_event.ends_at

    def test_proactive_booking_schedule_event_missing(
        self,
        admin_client,
        eligible_member,
        eligible_practitioner,
        complicated_practitioner_schedule,
        complicated_schedule_start_date,
    ):
        product = eligible_practitioner.products[1]
        scheduled_start = complicated_schedule_start_date + datetime.timedelta(hours=5)

        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/proactive_booking",
                data={
                    "product_id": product.id,
                    "user_id": eligible_member.id,
                    "anonymous_appointment": "False",
                    "purpose": "",
                    "scheduled_start": scheduled_start.isoformat(),
                },
            )
        assert res.status_code == 302
        assert res.location == f"/admin/memberprofile/edit/?id={eligible_member.id}"
        assert "No availability for " in flash.call_args[0][0]

    @pytest.mark.skip(reason="flaky when running in evening")
    def test_proactive_booking__unavailable_due_to_max_capacity(
        self,
        admin_client,
        factories,
        eligible_member,
        eligible_practitioner,
        practitioner_schedule,
        schedule_start_date,
    ):
        scheduled_start = schedule_start_date + datetime.timedelta(minutes=60)
        product = eligible_practitioner.products[0]
        factories.CreditFactory.create(user=eligible_member, amount=product.price)

        # Create appts for today to fill up max capacity
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=eligible_practitioner
        )
        aa.max_capacity = 6
        aa.daily_intro_capacity = 4
        today = datetime.datetime.utcnow().replace(hour=12)
        for _ in range(aa.max_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=eligible_practitioner,
                scheduled_start=today,
                scheduled_end=today
                + datetime.timedelta(minutes=eligible_practitioner.products[0].minutes),
            )

        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/proactive_booking",
                data={
                    "product_id": product.id,
                    "user_id": eligible_member.id,
                    "purpose": "",
                    "scheduled_start": scheduled_start.isoformat(),
                },
            )

        assert res.status_code == 302
        assert res.location == f"/admin/memberprofile/edit/?id={eligible_member.id}"
        assert "No availability for " in flash.call_args[0][0]
        assert "due to the practitioner's max capacity" in flash.call_args[0][0]
