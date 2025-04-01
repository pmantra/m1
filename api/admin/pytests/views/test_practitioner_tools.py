import datetime
from unittest import mock
from unittest.mock import call

import factory
import pytest

from appointments.models.schedule_event import ScheduleEvent
from appointments.services.common import round_to_nearest_minutes
from authn.models.user import MFAState
from pytests.factories import PractitionerUserFactory
from pytests.freezegun import freeze_time


class TestPromoTimeRange:
    def test_set_promo_time_range(self, admin_client):
        valid_range = "2018-05-25 00:00:00 to 2018-05-25 23:59:59"
        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/set_promo_time_range",
                data={"promo_time_range": valid_range},
            )

        assert res.status_code == 302
        assert flash.call_args == call("success!")
        # assert "Invalid range" not in html
        # assert "success!" in html
        # assert "2018-05-25T00:00:00 to 2018-05-25T23:59:59" in html

    @pytest.mark.parametrize(
        "bad_input",
        [
            "blah",
            "blah to blah",
            "2018-05-25 00:00:00 to blerp",
            "blorp to 2018-05-25 23:59:59",
            "2018-05-25 23:59:59 to 2018-05-25 00:00:00",
        ],
    )
    def test_set_promo_time_range_bad_input(self, admin_client, bad_input):
        res = admin_client.post(
            "/admin/actions/set_promo_time_range",
            data={"promo_time_range": bad_input},
            follow_redirects=True,
        )
        html = res.data.decode("utf8")
        assert "Invalid range" in html


class TestRecurringAvailability:
    @freeze_time("2021-05-25T17:00:00")
    def test_set_recurring_availability(self, admin_client, db):
        practitioner = PractitionerUserFactory.create()
        initial_event_count = db.session.query(ScheduleEvent).count()
        assert initial_event_count == 0

        starts_at = datetime.datetime.utcnow()
        until = starts_at + datetime.timedelta(weeks=10)

        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/set_recurring_availability",
                data={
                    "practitioner_id": str(practitioner.id),
                    "starts_at": starts_at.isoformat(),
                    "duration": "60",
                    "until": until.isoformat(),
                    "week_days_index": ["0", "2", "4"],
                },
            )

        assert res.status_code == 302
        assert flash.call_count == 1
        assert flash.call_args == call("success!")
        event_count = db.session.query(ScheduleEvent).count()
        assert event_count == 30

    def test_set_is_not_recurring(self, admin_client, db):
        practitioner = PractitionerUserFactory.create()
        initial_event_count = db.session.query(ScheduleEvent).count()
        assert initial_event_count == 0

        now = datetime.datetime.utcnow()
        starts_at = datetime.datetime(now.year + 1, 5, 25)
        until = datetime.date(now.year + 1, 5, 25)

        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/set_recurring_availability",
                data={
                    "practitioner_id": str(practitioner.id),
                    "starts_at": starts_at.isoformat(),
                    "duration": "60",
                    "until": until.isoformat(),
                    "week_days_index": ["0", "1", "2", "3", "4", "5", "6"],
                },
            )

        assert res.status_code == 302
        assert flash.call_count == 1
        assert flash.call_args == call("success!")
        event_count = db.session.query(ScheduleEvent).count()
        assert event_count == 1

    def test_cant_set_across_dst_change(self, admin_client, db):
        practitioner = PractitionerUserFactory.create()
        initial_event_count = db.session.query(ScheduleEvent).count()
        assert initial_event_count == 0

        now = datetime.datetime.utcnow()
        starts_at = datetime.datetime(now.year + 1, 5, 25)
        until = datetime.date(now.year + 1, 12, 25)

        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/set_recurring_availability",
                data={
                    "practitioner_id": str(practitioner.id),
                    "starts_at": starts_at.isoformat(),
                    "duration": "60",
                    "until": until.isoformat(),
                    "week_days_index": ["0", "2", "4"],
                },
            )

        assert res.status_code == 302
        assert flash.call_count == 1
        assert "Error: Time range crosses DST change" in flash.call_args[0][0]
        event_count = db.session.query(ScheduleEvent).count()
        assert event_count == 0

    def test_cant_set_availability_in_the_past(self, admin_client, db):
        practitioner = PractitionerUserFactory.create()
        initial_event_count = db.session.query(ScheduleEvent).count()
        assert initial_event_count == 0

        starts_at = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        until = starts_at

        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/set_recurring_availability",
                data={
                    "practitioner_id": str(practitioner.id),
                    "starts_at": starts_at.isoformat(),
                    "duration": "60",
                    "until": until.isoformat(),
                    "week_days_index": ["0", "2", "4"],
                },
            )

        assert res.status_code == 302
        assert flash.call_count == 1
        assert "Error: starts_at must be in the future!" in flash.call_args[0][0]
        event_count = db.session.query(ScheduleEvent).count()
        assert event_count == 0

    def test_set_recurring_availability_conflict(self, admin_client, db, factories):
        practitioner = PractitionerUserFactory.create()
        initial_event_count = db.session.query(ScheduleEvent).count()
        assert initial_event_count == 0

        # Set a static time to avoid the "Error: Time range crosses DST change" in set_recurring_availability
        starts_at = datetime.datetime(
            year=2025, month=9, day=1, hour=13, minute=30, second=0, microsecond=0
        )

        recurring_block = factories.ScheduleRecurringBlockFactory.create(
            schedule=practitioner.schedule,
            starts_at=round_to_nearest_minutes(starts_at),
            ends_at=round_to_nearest_minutes(starts_at) + datetime.timedelta(hours=2),
            until=round_to_nearest_minutes(starts_at) + datetime.timedelta(weeks=1),
        )
        factories.ScheduleRecurringBlockWeekdayIndexFactory.create(
            schedule_recurring_block=recurring_block,
        )
        factories.ScheduleRecurringBlockWeekdayIndexFactory.create(
            schedule_recurring_block=recurring_block,
            week_days_index=3,
        )
        factories.ScheduleEventFactory.create(
            schedule=practitioner.schedule,
            starts_at=round_to_nearest_minutes(starts_at),
            ends_at=round_to_nearest_minutes(starts_at) + datetime.timedelta(hours=2),
            schedule_recurring_block_id=recurring_block.id,
        )

        schedule_start = recurring_block.starts_at
        schedule_until = recurring_block.until

        with mock.patch("admin.blueprints.actions.flash") as flash:
            res = admin_client.post(
                "/admin/actions/set_recurring_availability",
                data={
                    "practitioner_id": str(practitioner.id),
                    "starts_at": schedule_start.isoformat(),
                    "duration": "120",
                    "until": schedule_until.isoformat(),
                    "week_days_index": ["0", "1", "2", "3", "4", "5", "6"],
                },
            )

        assert res.status_code == 302
        assert flash.call_count == 1
        assert "Conflict with existing availability!" in flash.call_args[0][0]


@pytest.fixture
def bulk_practitioners():
    return PractitionerUserFactory.create_batch(
        size=7,
        mfa_state=factory.Iterator(
            [
                MFAState.DISABLED,
                MFAState.ENABLED,
                MFAState.DISABLED,
                MFAState.PENDING_VERIFICATION,
                MFAState.ENABLED,
                MFAState.DISABLED,
                MFAState.PENDING_VERIFICATION,
            ]
        ),
        sms_phone_number=factory.Iterator(
            [
                "",
                "(704) 739-6817",
                "(704) 739-6817",
                "(704) 739-6817",
                "(704) 739-6817",
                "(704) 739-6817",
                "",
            ]
        ),
    )


class TestBulkMFA:
    def test_bulk_mfa_enable(self, admin_client, bulk_practitioners):
        prac1, prac2, prac3, prac4, prac5, prac6, prac7 = bulk_practitioners
        res = admin_client.post(
            "/admin/practitioner_management/enable_mfa", follow_redirects=True
        )
        assert res.status_code == 200
        assert prac1.mfa_state == MFAState.DISABLED
        assert prac2.mfa_state == MFAState.ENABLED
        assert prac3.mfa_state == MFAState.ENABLED
        assert prac4.mfa_state == MFAState.PENDING_VERIFICATION
        assert prac5.mfa_state == MFAState.ENABLED
        assert prac6.mfa_state == MFAState.ENABLED
        assert prac7.mfa_state == MFAState.PENDING_VERIFICATION

    def test_bulk_mfa_disable(self, admin_client, bulk_practitioners):
        prac1, prac2, prac3, prac4, prac5, prac6, prac7 = bulk_practitioners
        res = admin_client.post(
            "/admin/practitioner_management/disable_mfa", follow_redirects=True
        )
        assert res.status_code == 200
        assert prac1.mfa_state == MFAState.DISABLED
        assert prac2.mfa_state == MFAState.DISABLED
        assert prac3.mfa_state == MFAState.DISABLED
        assert prac4.mfa_state == MFAState.DISABLED
        assert prac5.mfa_state == MFAState.DISABLED
        assert prac6.mfa_state == MFAState.DISABLED
        assert prac7.mfa_state == MFAState.PENDING_VERIFICATION
