from collections import defaultdict, namedtuple
from datetime import date, datetime, time, timedelta
from unittest import mock

import pytest
from dateutil.relativedelta import relativedelta
from pytz import UTC, timezone

from appointments.utils.booking import (
    MassAvailabilityCalculator,
    TimeRange,
    is_in_date_ranges,
)
from care_advocates.models.assignable_advocates import (
    AssignableAdvocate,
    sort_and_merge_dates,
)
from health.models.risk_enums import RiskFlagName
from models.enterprise import Organization
from models.profiles import CareTeamTypes, MemberPractitionerAssociation
from pytests.factories import (
    AppointmentFactory,
    AssignableAdvocateFactory,
    ClientTrackFactory,
    DefaultUserFactory,
    MemberFactory,
    MemberTrackFactory,
    PractitionerProfileFactory,
    PractitionerUserFactory,
    ScheduleEventFactory,
)
from pytests.freezegun import freeze_time
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class AssignableAdvocateTestHelper:
    @classmethod
    def create_member(cls, org_name="Big Bucks Big Biz Co", track="pregnancy"):
        member = MemberFactory.create()
        if org_name:
            org = Organization(name=org_name)
            db.session.add(org)
            db.session.flush()
            if track:
                MemberTrackFactory.create(
                    name=track,
                    user=member,
                    client_track=ClientTrackFactory(organization=org),
                )
        return member

    @classmethod
    def create_advocate(cls, **kwargs):
        prac = PractitionerUserFactory.create(**kwargs)
        aa = AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)
        return aa

    @classmethod
    def create_aa_prac_profile(cls):
        prac = DefaultUserFactory.create()
        prac_profile = PractitionerProfileFactory.create(user_id=prac.id)
        AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)
        return prac_profile

    @classmethod
    def create_appt(cls, prac, start=None, length=None):
        if not start:
            start = datetime.utcnow()
        if not length and len(prac.user.products):
            length = prac.user.products[0].minutes
        elif not length:
            length = 10
        length = length if length else prac.user.products[0].minutes
        start = start if start else datetime.utcnow()
        return AppointmentFactory.create_with_practitioner(
            practitioner=prac.user,
            scheduled_start=start,
            scheduled_end=start + timedelta(minutes=length),
        )

    @classmethod
    def create_event(cls, prac, start, hours=8):
        return ScheduleEventFactory.create(
            starts_at=start,
            ends_at=start + timedelta(hours=hours),
            schedule=prac.user.schedule,
        )


@freeze_time("2022-01-01T00:00:00")
class TestUnavailableDatesEndToEnd:
    def test_unavailable_dates__member_has_had_ca_intro_appt__practitioner_at_max_capacity(
        self, factories
    ):
        # Given a member that needs a follow up appt and a practitioner with n appointments = max_capacity today
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        aa.max_capacity = 6
        aa.daily_intro_capacity = 4

        today = datetime.now().replace(hour=12)

        # Create appts for today to fill up max capacity
        for _ in range(aa.max_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=today,
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        # When
        unavailable_dates = aa.unavailable_dates(
            start_date=today,
            end_date=today,
            member_has_had_ca_intro_appt=True,
        )

        # Then, practitioner should not be available today
        assert is_in_date_ranges(today, unavailable_dates)

    def test_unavailable_dates__member_has_had_ca_intro_appt__practitioner_at_daily_intro_capacity(
        self, factories
    ):
        # Given a member that needs a follow up appt and a practitioner with n appointments = daily_intro today
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        aa.max_capacity = 6
        aa.daily_intro_capacity = 4

        today = datetime.now().replace(hour=12)

        # Create appts for today to fill up daily_intro
        for _ in range(aa.daily_intro_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=today,
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        # When
        unavailable_dates = aa.unavailable_dates(
            start_date=today,
            end_date=today,
            member_has_had_ca_intro_appt=True,
        )

        # Then, practitioner should be available today cause their appt is a follow up
        assert not is_in_date_ranges(today, unavailable_dates)

    def test_unavailable_dates__member_has_not_had_ca_intro_appt__practitioner_not_at_daily_intro_capacity(
        self, factories
    ):
        # Given a member that needs an intro appt and a practitioner with n appointments = daily_intro today-1
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        aa.max_capacity = 6
        aa.daily_intro_capacity = 4

        today = datetime.now().replace(hour=12)

        # Create appts for today but do not fill up daily_intro
        for _ in range(aa.daily_intro_capacity - 1):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=today,
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        # When
        unavailable_dates = aa.unavailable_dates(
            start_date=today,
            end_date=today,
            member_has_had_ca_intro_appt=False,
        )

        # Then, practitioner should be available today
        assert not is_in_date_ranges(today, unavailable_dates)

    def test_unavailable_dates__member_has_not_had_ca_intro_appt__practitioner_not_at_daily_intro_capacity_cause_of_only_followups(
        self, factories
    ):
        # Given a member that needs an intro appt and a practitioner with n appointments = daily_intro today but all but one are follow up appointments
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        aa.max_capacity = 6
        aa.daily_intro_capacity = 4

        member = factories.EnterpriseUserFactory.create()
        ms = factories.ScheduleFactory.create(user=member)

        today = datetime.now().replace(hour=12)

        # Create daily_intro_capacity appts for today but we will not actually fill up daily_intro cause they are all for the same mamber so all but one will be follow up appts
        for i in range(aa.daily_intro_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                member_schedule=ms,
                scheduled_start=today
                + timedelta(
                    minutes=i
                ),  # We want appts to start as different times so only one is picked up as the intro appt
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes)
                + timedelta(minutes=i),
            )

        # When
        unavailable_dates = aa.unavailable_dates(
            start_date=today,
            end_date=today,
            member_has_had_ca_intro_appt=False,
        )

        # Then, practitioner should be available today
        assert not is_in_date_ranges(today, unavailable_dates)

    def test_unavailable_dates__member_has_not_had_ca_intro_appt__practitioner_at_max_capacity_only_with_followups(
        self, factories
    ):
        # Given a member that needs an intro appt and a practitioner with n appointments = max_capacity and where all of them but one are followups
        # Then, even if the practitioner has daily_intro_capacity left, given that theyve met their max capacity they should not be available
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        aa.max_capacity = 6
        aa.daily_intro_capacity = 4

        member = factories.EnterpriseUserFactory.create()
        ms = factories.ScheduleFactory.create(user=member)

        today = datetime.now().replace(hour=12)

        # Create max_capacity n appts for today, all for the same member
        for _ in range(aa.max_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                member_schedule=ms,
                scheduled_start=today,
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        # When
        unavailable_dates = aa.unavailable_dates(
            start_date=today,
            end_date=today,
            member_has_had_ca_intro_appt=False,
        )

        # Then, practitioner should not be available today
        assert is_in_date_ranges(today, unavailable_dates)

    def test_unavailable_dates__member_has_not_had_ca_intro_appt__practitioner_at_daily_intro_capacity(
        self, factories
    ):
        # Given a member that needs an intro appt and a practitioner with n appointments = daily_intro today
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        aa.max_capacity = 6
        aa.daily_intro_capacity = 4

        today = datetime.now().replace(hour=12)

        # Create appts for today to fill up daily_intro
        for _ in range(aa.daily_intro_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=today,
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes),
                purpose="introduction",
            )

        # When
        unavailable_dates = aa.unavailable_dates(
            start_date=today,
            end_date=today,
            member_has_had_ca_intro_appt=False,
        )

        # Then, practitioner should not be available today
        assert is_in_date_ranges(today, unavailable_dates)

    def test_unavailable_dates__member_has_not_had_ca_intro_appt__practitioner_at_daily_intro_capacity_check_daily_intro_capacity_false(
        self, factories
    ):
        # Given a member that needs an intro appt and a practitioner with n appointments = daily_intro today
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        aa.max_capacity = 6
        aa.daily_intro_capacity = 4

        today = datetime.now().replace(hour=12)

        # Create appts for today filling up daily_intro
        for _ in range(aa.daily_intro_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=today,
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        # When
        unavailable_dates = aa.unavailable_dates(
            start_date=today,
            end_date=today,
            member_has_had_ca_intro_appt=False,
            check_daily_intro_capacity=False,
        )

        # Then, practitioner should be available today
        assert not is_in_date_ranges(today, unavailable_dates)
        assert len(unavailable_dates) == 0

    def test_unavailable_dates__availabilty_in_middle_of_week__member_has_had_ca_intro_appt(
        self, factories
    ):
        # Given, a practitioner with appointments today and in three days, but not tomorrow nor day after
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        today = datetime.now().replace(hour=12)
        one_day_later = today + timedelta(days=1)
        two_days_later = today + timedelta(days=2)
        three_days_later = today + timedelta(days=3)

        # Create appts for today
        for _ in range(aa.max_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=today,
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        # Create appts for three days later
        for _ in range(aa.max_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=three_days_later,
                scheduled_end=three_days_later
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        # When
        dates = aa.unavailable_dates(
            start_date=today,
            end_date=three_days_later,
            member_has_had_ca_intro_appt=True,
        )

        # Then, practitioner should not be available today nor in three days, but yes tomorrow and day after
        assert is_in_date_ranges(today, dates)
        assert not is_in_date_ranges(one_day_later, dates)
        assert not is_in_date_ranges(two_days_later, dates)
        assert is_in_date_ranges(three_days_later, dates)

    def test_unavailable_dates__availabilty_in_middle_of_week__member_has_not_had_ca_intro_appt(
        self, factories
    ):
        # Given, a practitioner with appointments today and in three days, but not tomorrow nor day after
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        # Being explicit about the fact that the CA's daily intro capacity is different to max capacity
        aa.max_capacity = 6
        aa.daily_intro_capacity = 4

        today = datetime.now().replace(hour=12)
        one_day_later = today + timedelta(days=1)
        two_days_later = today + timedelta(days=2)
        three_days_later = today + timedelta(days=3)

        # Create appts for today, up to daily_intro_capacity
        for _ in range(aa.daily_intro_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=today,
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes),
                purpose="introduction",
            )

        # Create appts for three days later, up to daily_intro_capacity
        for _ in range(aa.daily_intro_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=three_days_later,
                scheduled_end=three_days_later
                + timedelta(minutes=practitioner.products[0].minutes),
                purpose="introduction",
            )

        # When
        dates = aa.unavailable_dates(
            start_date=today,
            end_date=three_days_later,
            member_has_had_ca_intro_appt=False,
        )

        # Then, practitioner should not be available today nor in three days, but yes tomorrow and day after
        assert is_in_date_ranges(today, dates)
        assert not is_in_date_ranges(one_day_later, dates)
        assert not is_in_date_ranges(two_days_later, dates)
        assert is_in_date_ranges(three_days_later, dates)

    def test_unavailable_dates__max_capacity_zero(self, factories):
        # Given
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        aa.max_capacity = 0

        now = datetime.utcnow()
        one_day_later = now + timedelta(days=1)
        two_days_later = now + timedelta(days=2)
        three_days_later = now + timedelta(days=3)

        # When
        dates = aa.unavailable_dates(
            start_date=now, end_date=three_days_later, member_has_had_ca_intro_appt=True
        )

        # Then, no day has availabilty
        assert is_in_date_ranges(now, dates)
        assert is_in_date_ranges(one_day_later, dates)
        assert is_in_date_ranges(two_days_later, dates)
        assert is_in_date_ranges(three_days_later, dates)

    def test_unavailable_dates__on_vacations(self, factories, db):
        # Given
        practitioner = factories.PractitionerUserFactory.create()

        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        today = datetime.utcnow()
        one_day_later = today + timedelta(days=1)
        two_days_later = today + timedelta(days=2)
        three_days_later = today + timedelta(days=3)
        four_days_later = today + timedelta(days=4)
        yesterday = today - timedelta(days=1)

        aa.vacation_started_at = yesterday
        aa.vacation_ended_at = four_days_later
        db.session.commit()

        # When
        dates = aa.unavailable_dates(
            start_date=today,
            end_date=three_days_later,
            member_has_had_ca_intro_appt=True,
        )

        # Then, practitioner is never available
        assert is_in_date_ranges(yesterday, dates)
        assert is_in_date_ranges(today, dates)
        assert is_in_date_ranges(one_day_later, dates)
        assert is_in_date_ranges(two_days_later, dates)
        assert is_in_date_ranges(three_days_later, dates)
        assert is_in_date_ranges(four_days_later, dates)

    def test_unavailable_dates__on_vacations_with_appointments(self, factories):
        # Given
        practitioner = factories.PractitionerUserFactory.create(timezone="UTC")

        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        today = datetime.utcnow()
        one_day_later = today + timedelta(days=1)
        two_days_later = today + timedelta(days=2)
        three_days_later = today + timedelta(days=3)
        four_days_later = today + timedelta(days=4)

        # Practitioner has appts today and in three days
        for _ in range(aa.max_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=today,
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        for _ in range(aa.max_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=three_days_later,
                scheduled_end=three_days_later
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        # Practitioner has vacations tomorrow and day after
        aa.vacation_started_at = one_day_later
        aa.vacation_ended_at = two_days_later

        # When
        dates = aa.unavailable_dates(
            start_date=today,
            end_date=four_days_later,
            member_has_had_ca_intro_appt=True,
        )

        # Then, practitioner is only available on the fourth day
        assert is_in_date_ranges(today, dates)
        assert is_in_date_ranges(one_day_later, dates)
        assert is_in_date_ranges(two_days_later, dates)
        assert is_in_date_ranges(three_days_later, dates)
        assert not is_in_date_ranges(four_days_later, dates)

    def test_unavailable_dates__on_vacations_partial_day(self, factories):
        # Given

        practitioner = factories.PractitionerUserFactory.create()

        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        today = datetime.utcnow()
        one_day_9am_later = today + timedelta(days=1, hours=9)
        one_day_noon_later = today + timedelta(days=1, hours=12)
        two_days_later = today + timedelta(days=2)
        two_days_noon_later = today + timedelta(days=2, hours=12)

        aa.vacation_started_at = one_day_noon_later
        aa.vacation_ended_at = two_days_later

        # When
        dates = aa.unavailable_dates(
            start_date=today, end_date=two_days_later, member_has_had_ca_intro_appt=True
        )

        # Then
        assert not is_in_date_ranges(today, dates)
        assert not is_in_date_ranges(one_day_9am_later, dates)
        assert is_in_date_ranges(one_day_noon_later, dates)
        assert is_in_date_ranges(two_days_later, dates)
        assert not is_in_date_ranges(two_days_noon_later, dates)

    def test_unavailable_dates__on_vacations_partial_day_max_capacity(
        self,
        factories,
    ):
        # Given
        practitioner = factories.PractitionerUserFactory.create(timezone="UTC")

        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        today = datetime.utcnow()
        today_midnight = today.replace(hour=0, minute=1, second=0, microsecond=0)
        one_day_9am_later = today_midnight + timedelta(days=1, hours=9)
        one_day_noon_later = today_midnight + timedelta(days=1, hours=12)
        two_days_later = today_midnight + timedelta(days=2)
        two_days_noon_later = today_midnight + timedelta(days=2, hours=12)
        three_days_later = today_midnight + timedelta(days=3)

        for _ in range(aa.max_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=today,
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        for _ in range(aa.max_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=three_days_later,
                scheduled_end=three_days_later
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        aa.vacation_started_at = one_day_noon_later
        aa.vacation_ended_at = two_days_later

        # Given
        dates = aa.unavailable_dates(
            start_date=today_midnight,
            end_date=three_days_later,
            member_has_had_ca_intro_appt=True,
        )

        # Then
        assert is_in_date_ranges(today_midnight, dates)
        assert not is_in_date_ranges(one_day_9am_later, dates)
        assert is_in_date_ranges(one_day_noon_later, dates)
        assert is_in_date_ranges(two_days_later, dates)
        assert not is_in_date_ranges(two_days_noon_later, dates)
        assert is_in_date_ranges(three_days_later, dates)

    def test_unavailable_dates__on_vacations_partial_day_with_overlapping_max_capacity(
        self, factories
    ):
        # Given
        practitioner = factories.PractitionerUserFactory.create(timezone="UTC")

        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        one_day_9am_later = today + timedelta(days=1, hours=9)
        one_day_11pm_later = today + timedelta(days=1, hours=23)
        two_days_later = today + timedelta(days=2)
        two_days_noon_later = today + timedelta(days=2, hours=12)
        three_days_later = today + timedelta(days=3)

        for _ in range(aa.max_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=one_day_11pm_later,
                scheduled_end=one_day_11pm_later
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        aa.vacation_started_at = one_day_11pm_later
        aa.vacation_ended_at = two_days_later

        # When
        dates = aa.unavailable_dates(
            start_date=today,
            end_date=three_days_later,
            member_has_had_ca_intro_appt=True,
        )

        # Then
        assert not is_in_date_ranges(today, dates)
        assert is_in_date_ranges(one_day_9am_later, dates)
        assert is_in_date_ranges(one_day_11pm_later, dates)
        assert is_in_date_ranges(two_days_later, dates)
        assert not is_in_date_ranges(two_days_noon_later, dates)

    # TODO: This one feels like a weird test. Not sure what are we testing.
    def test_unavailable_dates__assignable_advocate_max_capacity_timezone(
        self, factories
    ):
        """Test that max capacity is calculated in the advocate's timezone"""

        # Given
        practitioner = factories.PractitionerUserFactory.create(
            timezone="America/Los_Angeles"
        )
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        aa.vacation_started_at = None
        aa.vacation_ended_at = None
        aa.max_capacity = 3

        # pick a date in the future to test around
        now = datetime.now().replace(hour=12)
        five_days_out = now + timedelta(days=5)
        five_days_out_eod = five_days_out.replace(hour=23, minute=59, second=59)

        for _ in range(aa.max_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=five_days_out_eod
                - timedelta(minutes=practitioner.products[0].minutes),
                scheduled_end=five_days_out_eod,
            )

        # When
        dates = aa.unavailable_dates(
            start_date=now, end_date=five_days_out, member_has_had_ca_intro_appt=True
        )
        # Then
        assert len(dates) == 1

        # if they were created in UTC or EST, they would be available the day after
        day_after = five_days_out + timedelta(days=1)
        # When
        dates = aa.unavailable_dates(
            start_date=day_after, end_date=day_after, member_has_had_ca_intro_appt=True
        )
        # Then
        assert len(dates) == 0

    def test_user_assignable_advocate_max_capacity__utc_split(
        self,
        factories,
    ):
        """
        Tests that max capacity works when searching for the next day in UTC,
        but the same day in the practitioner's timezone
        """
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner,
        )
        aa.max_capacity = 4
        db.session.commit()

        NY_TZ = timezone("America/New_York")
        today = NY_TZ.normalize(UTC.localize(datetime.utcnow()))

        # Calculate all times in EST
        today = today.replace(hour=0, minute=0)
        appt_times = [
            today.replace(hour=17, minute=30),
            today.replace(hour=18, minute=15),
            today.replace(hour=19, minute=0),  # Midnight in UTC
            today.replace(hour=20, minute=0),
        ]
        next_appt = today.replace(hour=21, minute=10)

        # Make all times UTC and tz naive
        today = UTC.normalize(today).replace(tzinfo=None)
        appt_times = [UTC.normalize(at).replace(tzinfo=None) for at in appt_times]
        next_appt = UTC.normalize(next_appt).replace(tzinfo=None)

        for appt_time in appt_times:
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=appt_time,
                scheduled_end=appt_time
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        member_has_had_ca_intro_appt = True

        dates = aa.unavailable_dates(
            next_appt,
            next_appt + timedelta(hours=1),
            member_has_had_ca_intro_appt,
        )
        assert is_in_date_ranges(today, dates)

    def test_user_assignable_advocate_daily_intro_capacity__utc_split(
        self,
        factories,
    ):
        """
        Tests that daily intro capacity works when searching for the next day in UTC,
        but the same day in the practitioner's timezone
        """
        # Given a practitioner with full daily_intro_capacity in their own time zone
        # but the appointments are split over two days UTC
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner,
        )
        aa.daily_intro_capacity = 4
        aa.max_capacity = 10
        db.session.commit()

        NY_TZ = timezone("America/New_York")
        today = NY_TZ.normalize(UTC.localize(datetime.utcnow()))

        # Calculate all times in EST
        today = today.replace(hour=0, minute=0)
        appt_times = [
            today.replace(hour=17, minute=30),
            today.replace(hour=18, minute=15),
            today.replace(hour=19, minute=0),  # Midnight in UTC
            today.replace(hour=20, minute=0),
        ]
        next_appt = today.replace(hour=21, minute=10)

        # Make all times UTC and tz naive
        today = UTC.normalize(today).replace(tzinfo=None)
        appt_times = [UTC.normalize(at).replace(tzinfo=None) for at in appt_times]
        next_appt = UTC.normalize(next_appt).replace(tzinfo=None)

        for appt_time in appt_times:
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=appt_time,
                scheduled_end=appt_time
                + timedelta(minutes=practitioner.products[0].minutes),
                purpose="introduction",
            )

        member_has_had_ca_intro_appt = False

        # When we check for unavailable dates for a member that has not had a ca intro appointment
        dates = aa.unavailable_dates(
            next_appt,
            next_appt + timedelta(hours=1),
            member_has_had_ca_intro_appt,
        )
        # Then the date of the appointments is included as an unavailable date
        assert is_in_date_ranges(today, dates)


@freeze_time("2022-01-01T00:00:00")
class TestSortAndMergeDates:
    def test_sort_and_merge_dates(self):
        now = datetime.utcnow()
        noon = now + timedelta(hours=12)
        eleven_pm = now + timedelta(hours=23)
        eleven_twenty_five_pm = now + timedelta(hours=23, minutes=25)
        eleven_thirty_pm = now + timedelta(hours=23, minutes=30)
        tomorrow = now + timedelta(days=1)

        datetimes = []
        datetimes.append(TimeRange(noon, eleven_pm))
        datetimes.append(TimeRange(now, eleven_pm))
        datetimes.append(TimeRange(eleven_thirty_pm, tomorrow))

        sorted_and_merged_dates = sort_and_merge_dates(dates=datetimes)

        assert is_in_date_ranges(now, sorted_and_merged_dates)
        assert not is_in_date_ranges(eleven_twenty_five_pm, sorted_and_merged_dates)
        assert sorted_and_merged_dates[0] == TimeRange(now, eleven_pm)
        assert len(sorted_and_merged_dates) == 2


class TestGetAdvocatesNotOnVacation:
    # TODO: Create more tests for TestGetAdvocatesNotOnVacation
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.log_advocates_on_vacation"
    )
    def test_get_advocates_not_on_vacation__aa_without_vacation_start_nor_end_date(
        self, mock_log_advocates_on_vacation, factories
    ):
        # Given
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )
        aa.vacation_started_at = None
        aa.vacation_ended_at = None
        now = datetime.utcnow()
        expected_advocates_not_on_vacation = [aa]

        # When
        advocates_not_on_vacation = AssignableAdvocate.get_advocates_not_on_vacation(
            user=practitioner, date=now
        ).all()

        # Then
        mock_log_advocates_on_vacation.assert_called_once()
        assert advocates_not_on_vacation == expected_advocates_not_on_vacation


class TestGetAdvocatesWithNextAvailability(AssignableAdvocateTestHelper):
    @pytest.mark.parametrize(
        argnames="days_out_from_today,time_interval",
        argvalues=[
            (3, timedelta(days=1)),
            (3, timedelta(days=2)),
            (3, timedelta(days=3)),
            (7, timedelta(days=1)),
            (7, timedelta(days=2)),
            (7, timedelta(days=3)),
            (7, timedelta(days=4)),
            (7, timedelta(days=5)),
            (7, timedelta(days=6)),
            (7, timedelta(days=7)),
        ],
    )
    def test_get_advocate_with_next_availability__has_availability(
        self,
        days_out_from_today,
        time_interval,
        datetime_today,
    ):
        user = self.create_member()

        # Given - a practitioner with next_availability within next 3 days
        prac_profile = self.create_aa_prac_profile()

        prac_profile.next_availability = datetime_today + time_interval

        # When we call advocates next availability
        available_advocate_ids = (
            AssignableAdvocate.get_advocates_with_next_availability(
                days_out_from_today=days_out_from_today, user=user
            )
        )

        # Then the advocate with availability will be returned
        expected_available_advocate_ids = [prac_profile.user_id]
        assert available_advocate_ids == expected_available_advocate_ids

    @pytest.mark.parametrize(
        argnames="days_out_from_today,time_interval",
        argvalues=[
            (3, timedelta(hours=-1)),
            (3, timedelta(days=-1)),
            (7, timedelta(hours=-1)),
            (7, timedelta(days=-1)),
        ],
    )
    def test_get_advocate_with_next_availability__no_availability(
        self,
        days_out_from_today,
        time_interval,
        datetime_today,
    ):
        user = self.create_member()

        # Given - a practitioner with next_availability 1 hour ago
        prac_profile = self.create_aa_prac_profile()

        prac_profile.next_availability = datetime_today + time_interval

        # When we call advocates with next availability
        available_advocate_ids = (
            AssignableAdvocate.get_advocates_with_next_availability(
                days_out_from_today=days_out_from_today, user=user
            )
        )
        # Then the advocate with availability will not be returned
        assert available_advocate_ids == []

    def test_get_advocate_with_next_availability__none(
        self,
    ):
        days_out_from_today = 3
        user = self.create_member()

        # Given - a practitioner with next availability None
        prac_profile = self.create_aa_prac_profile()

        prac_profile.next_availability = None

        # When
        available_advocate_ids = (
            AssignableAdvocate.get_advocates_with_next_availability(
                days_out_from_today=days_out_from_today, user=user
            )
        )
        # Then the assignable advocate's ID is not in the results
        assert available_advocate_ids == []


class TestGetAdvocatesWithCapacityAndAvailability(AssignableAdvocateTestHelper):
    def test_get_advocate_with_capacity_availability__some_capacity(
        self,
        factories,
    ):
        days_out_from_today = 3
        user = self.create_member()

        today = datetime.utcnow()

        # Given - a practitioner with availability next week, but no capacity
        aa = self.create_advocate()
        aa.practitioner.next_availability = today + timedelta(days=10)
        aa.vacation_started_at = None
        aa.vacation_ended_at = None
        aa.daily_intro_capacity = 3
        db.session.commit()

        for i in range(days_out_from_today):
            start_time = (
                (today + timedelta(days=i)).replace(hour=9, minute=0, second=0),
            )
            end_time = (
                (today + timedelta(days=i)).replace(hour=17, minute=0, second=0),
            )

            factories.ScheduleEventFactory.create(
                schedule=aa.practitioner.user.schedule,
                starts_at=start_time,
                ends_at=end_time,
            )

        # fill their days with appointments until they're at capacity
        for i in range(days_out_from_today):
            date = datetime.utcnow() + timedelta(days=i)
            for _ in range(aa.daily_intro_capacity - 2):
                factories.AppointmentFactory.create_with_practitioner(
                    practitioner=aa.practitioner.user,
                    scheduled_start=date,
                    scheduled_end=date
                    + timedelta(minutes=aa.practitioner.user.products[0].minutes),
                )

        # When we call advocates with next availability
        available_advocate_ids = (
            AssignableAdvocate.get_advocates_with_capacity_and_availability(
                days_out_from_today=days_out_from_today, user=user
            )
        )

        # Then the assignable advocate's ID is not in the results
        assert available_advocate_ids == []


class TestGetAvailableAdvocatesWithDailyIntroCapacity:
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocate_ids"
    )
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_with_daily_intro_capacity_query"
    )
    def test_get_advocates_with_max_capacity(
        self,
        mock_get_advocates_with_daily_intro_capacity_query,
        mock_get_advocate_ids,
        factories,
    ):

        # Given
        days_out_from_today = 1
        user = factories.DefaultUserFactory()

        expected_available_advocate_ids = [1]
        mock_get_advocate_ids.return_value = expected_available_advocate_ids

        # When
        available_advocate_ids = (
            AssignableAdvocate.get_advocates_with_daily_intro_capacity(
                days_out_from_today=days_out_from_today, user=user
            )
        )

        # Then
        mock_get_advocates_with_daily_intro_capacity_query.assert_called_once_with(
            days_out_from_today, user
        )
        mock_get_advocate_ids.assert_called_once()
        assert available_advocate_ids == expected_available_advocate_ids


class TestGetAvailableAdvocatesWithMaxCapacity:
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocate_ids"
    )
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_with_max_capacity_query"
    )
    def test_get_advocates_with_max_capacity(
        self,
        mock_get_advocates_with_max_capacity_query,
        mock_get_advocate_ids,
        factories,
    ):

        # Given
        days_out_from_today = 1
        user = factories.DefaultUserFactory()

        expected_available_advocate_ids = [1]
        mock_get_advocate_ids.return_value = expected_available_advocate_ids

        # When
        available_advocate_ids = AssignableAdvocate.get_advocates_with_max_capacity(
            days_out_from_today=days_out_from_today, user=user
        )

        # Then
        mock_get_advocates_with_max_capacity_query.assert_called_once_with(
            days_out_from_today, user
        )

        mock_get_advocate_ids.assert_called_once()
        assert available_advocate_ids == expected_available_advocate_ids


@freeze_time("2022-01-01T00:00:00")
class TestGetAvailableAdvocatesWithDailyIntroCapacityQuery:
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_not_on_vacation"
    )
    def test_get_advocates_with_daily_intro_capacity_query__one_advocate_with_capacity(
        self, mock_get_advocates_not_on_vacation, factories
    ):
        # Given: two practitioners that are fully booked for the coming days
        mock_get_advocates_not_on_vacation.return_value = AssignableAdvocate.query
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        # Create appointments but make the AA not fully booked
        days_out_from_today = 1
        for i in range(days_out_from_today):
            date = datetime.utcnow() + timedelta(days=i)
            for _ in range(aa.daily_intro_capacity - 1):
                factories.AppointmentFactory.create_with_practitioner(
                    practitioner=practitioner,
                    scheduled_start=date,
                    scheduled_end=date
                    + timedelta(minutes=practitioner.products[0].minutes),
                )

        # Then, CA is available
        expected_available_advocates = [aa]
        available_advocates = (
            AssignableAdvocate.get_advocates_with_daily_intro_capacity_query(
                days_out_from_today=days_out_from_today, user=None
            ).all()
        )
        mock_get_advocates_not_on_vacation.assert_called_once()
        assert available_advocates == expected_available_advocates

    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_not_on_vacation"
    )
    def test_get_advocates_with_daily_intro_capacity_query__advocate_with_capacity_on_their_last_days(
        self, mock_get_advocates_not_on_vacation, factories
    ):
        # Given: a practitioner that is fully booked today but not tomorrow
        mock_get_advocates_not_on_vacation.return_value = AssignableAdvocate.query
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        # Create appointments to fill their daily intro today
        today = datetime.utcnow()
        for _ in range(aa.daily_intro_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=today,
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes),
            )
        # Create appointments to fill all but one slot of their daily intro capacity tomorrow
        tomorrow = today + timedelta(days=1)
        for _ in range(aa.daily_intro_capacity - 1):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=tomorrow,
                scheduled_end=tomorrow
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        # When
        expected_available_advocates = [aa]
        available_advocates = (
            AssignableAdvocate.get_advocates_with_daily_intro_capacity_query(
                days_out_from_today=2, user=None
            ).all()
        )
        # Then: the AA should be found available
        mock_get_advocates_not_on_vacation.assert_called_once()
        assert available_advocates == expected_available_advocates

    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_not_on_vacation"
    )
    def test_get_advocates_with_daily_intro_capacity_query__advocate_with_capacity_on_their_first_days(
        self, mock_get_advocates_not_on_vacation, factories
    ):
        # Given a practitioner that is booked at the end of the week but not at the beginning
        mock_get_advocates_not_on_vacation.return_value = AssignableAdvocate.query
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        # Create appointments from day 3 to day 6, so they have availability on the first 3 days of the days out
        days_out_start_day = 3
        days_out_from_today = 6
        for i in range(days_out_start_day, days_out_from_today):
            date = datetime.utcnow() + timedelta(days=i)
            for _ in range(aa.daily_intro_capacity):
                factories.AppointmentFactory.create_with_practitioner(
                    practitioner=practitioner,
                    scheduled_start=date,
                    scheduled_end=date
                    + timedelta(minutes=practitioner.products[0].minutes),
                )

        # Then, they should have availability when searching in the next 4 days
        expected_available_advocates = [aa]
        available_advocates = (
            AssignableAdvocate.get_advocates_with_daily_intro_capacity_query(
                days_out_from_today=4, user=None
            ).all()
        )
        mock_get_advocates_not_on_vacation.assert_called_once()
        assert available_advocates == expected_available_advocates


@freeze_time("2022-01-01T00:00:00")
class TestGetAvailableAdvocatesWithMaxCapacityQuery:
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_not_on_vacation"
    )
    def test_get_advocates_with_max_capacity_query__advocate_with_capacity_on_their_last_days(
        self, mock_get_advocates_not_on_vacation, factories
    ):
        # Given: a practitioner that is fully booked today but not tomorrow
        mock_get_advocates_not_on_vacation.return_value = AssignableAdvocate.query
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        # Create appointments to fill their max capacity today
        today = datetime.utcnow()
        for _ in range(aa.max_capacity):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=today,
                scheduled_end=today
                + timedelta(minutes=practitioner.products[0].minutes),
            )
        # Create appointments to fill all but one slot of their max capacity tomorrow
        tomorrow = today + timedelta(days=1)
        for _ in range(aa.max_capacity - 1):
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner,
                scheduled_start=tomorrow,
                scheduled_end=tomorrow
                + timedelta(minutes=practitioner.products[0].minutes),
            )

        # When
        expected_available_advocates = [aa]
        available_advocates = AssignableAdvocate.get_advocates_with_max_capacity_query(
            days_out_from_today=2, user=None
        ).all()
        # Then: the AA should be found available
        mock_get_advocates_not_on_vacation.assert_called_once()
        assert available_advocates == expected_available_advocates

    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_not_on_vacation"
    )
    def test_get_advocates_with_max_capacity_query__advocate_with_capacity_on_their_first_days(
        self, mock_get_advocates_not_on_vacation, factories
    ):
        # Given a practitioner that is booked at the end of the week but not at the beginning
        mock_get_advocates_not_on_vacation.return_value = AssignableAdvocate.query
        practitioner = factories.PractitionerUserFactory.create()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        # Create appointments from day 3 to day 6, so they have availability on the first 3 days of the days out
        days_out_start_day = 3
        days_out_from_today = 6
        for i in range(days_out_start_day, days_out_from_today):
            date = datetime.utcnow() + timedelta(days=i)
            for _ in range(aa.max_capacity):
                factories.AppointmentFactory.create_with_practitioner(
                    practitioner=practitioner,
                    scheduled_start=date,
                    scheduled_end=date
                    + timedelta(minutes=int(practitioner.products[0].minutes)),
                )

        # Then, they should have availability when searching in the next 4 days
        expected_available_advocates = [aa]
        available_advocates = AssignableAdvocate.get_advocates_with_max_capacity_query(
            days_out_from_today=4, user=None
        ).all()
        mock_get_advocates_not_on_vacation.assert_called_once()
        assert available_advocates == expected_available_advocates


# TODO: Add e2e test
@freeze_time("2022-01-01T00:00:00")
class TestValidateConsistentNextAvailability(AssignableAdvocateTestHelper):
    @mock.patch("care_advocates.models.assignable_advocates.log")
    def test_validate_consistent_next_availability__next_availability_is_none(
        self, log_mock, factories
    ):
        # Given a CA with None next availability
        prac = factories.DefaultUserFactory()
        prac_profile = factories.PractitionerProfileFactory.create(user_id=prac.id)
        prac_profile.next_availability = None
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)

        # When
        AssignableAdvocate.validate_consistent_next_availability(prac.id)

        # Then log.warning called
        log_mock.warn.assert_called_once_with(
            "ca member matching - advocate has next_availability None",
            user_id=prac.id,
            next_availability=None,
        )

    @mock.patch("care_advocates.models.assignable_advocates.log")
    def test_validate_consistent_next_availability__next_availability_after_7_days(
        self, log_mock, factories
    ):
        # Given a CA with next availability after 7 days
        prac = factories.DefaultUserFactory()
        prac_profile = factories.PractitionerProfileFactory.create(user_id=prac.id)
        prac_profile.next_availability = datetime.utcnow().replace(
            minute=0, second=0, microsecond=0
        ) + timedelta(days=10)
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)

        # When
        AssignableAdvocate.validate_consistent_next_availability(prac.id)

        # Then log.warning called
        log_mock.warn.assert_called_once_with(
            "ca member matching - advocate has next_availability in more than 7 days",
            user_id=prac.id,
            next_availability=prac_profile.next_availability.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            today=mock.ANY,
        )

    @mock.patch(
        "care_advocates.models.assignable_advocates.Appointment.intro_appointments_from_date_range_with_tz"
    )
    @mock.patch("care_advocates.models.assignable_advocates.log")
    @freeze_time(datetime.utcnow().replace(minute=0, second=0, microsecond=0))
    def test_validate_consistent_next_availability__no_capacity_on_next_availability(
        self, log_mock, intro_appointments_from_date_range_with_tz_mock, factories
    ):
        # Given a CA with no capacity on their next availability day
        prac = factories.DefaultUserFactory()
        prac_profile = factories.PractitionerProfileFactory.create(user_id=prac.id)
        prac_profile.next_availability = datetime.utcnow() + timedelta(days=1)
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=prac
        )
        aa.daily_intro_capacity = 5
        aa.max_capacity = 5
        mocked_n_intro_appts = aa.daily_intro_capacity

        intro_appointments_from_date_range_with_tz_mock.return_value.with_entities.return_value.one.return_value = (
            mocked_n_intro_appts,
        )

        # When
        AssignableAdvocate.validate_consistent_next_availability(prac.id)

        # Then log.warn called
        log_mock.warn.assert_called_once_with(
            "ca member matching - advocate has no daily_intro_capacity remaining on next_availability date",
            user_id=prac.id,
            next_availability=prac_profile.next_availability.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            daily_intro_capacity=aa.daily_intro_capacity,
            number_of_intro_appointments=mocked_n_intro_appts,
        )

    @mock.patch(
        "care_advocates.models.assignable_advocates.Appointment.intro_appointments_from_date_range_with_tz"
    )
    @mock.patch("care_advocates.models.assignable_advocates.log")
    @freeze_time(datetime.utcnow().replace(minute=0, second=0, microsecond=0))
    def test_validate_consistent_next_availability__capacity_on_next_availability(
        self, log_mock, intro_appointments_from_date_range_with_tz_mock, factories
    ):
        # Given a CA with capacity on their next availability day
        prac = factories.DefaultUserFactory()
        prac_profile = factories.PractitionerProfileFactory.create(user_id=prac.id)
        prac_profile.next_availability = datetime.utcnow() + timedelta(days=1)
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=prac
        )
        aa.daily_intro_capacity = 5
        aa.max_capacity = 5
        mocked_n_intro_appts = 2
        intro_appointments_from_date_range_with_tz_mock.return_value.with_entities.return_value.one.return_value = (
            mocked_n_intro_appts,
        )

        # When
        AssignableAdvocate.validate_consistent_next_availability(prac.id)

        # Then log.info called
        log_mock.info.assert_called_once_with(
            "ca member matching - advocate has daily_intro_capacity remaining on next_availability date",
            user_id=prac.id,
            next_availability=prac_profile.next_availability.strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            daily_intro_capacity=aa.daily_intro_capacity,
            number_of_intro_appointments=mocked_n_intro_appts,
        )


# TODO: Add e2e tests
class TestRemoveCareAdvocateFromMember:
    def test_remove_care_advocate_from_member__has_ca(self, default_user, factories):
        # Given a user and an assigned CA
        factories.MemberProfileFactory.create(user=default_user)
        prac = factories.PractitionerUserFactory()
        factories.MemberPractitionerAssociationFactory.create(
            type=CareTeamTypes.CARE_COORDINATOR,
            user_id=default_user.id,
            practitioner_id=prac.id,
        )
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac)

        # When
        assigned_prac_id = AssignableAdvocate.remove_care_advocate_from_member(
            default_user
        )
        mpa_after_assignment = MemberPractitionerAssociation.query.filter_by(
            user_id=default_user.id,
            practitioner_id=prac.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        ).one_or_none()
        # Then
        assert assigned_prac_id == prac.id
        assert not mpa_after_assignment

    def test_remove_care_advocate_from_member__no_ca(self, default_user):
        # Given a user and no ca
        # When
        AssignableAdvocate.remove_care_advocate_from_member(default_user)
        mpa_after_assignment = MemberPractitionerAssociation.query.filter_by(
            user_id=default_user.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        ).one_or_none()
        # Then
        assert not mpa_after_assignment


class TestAssignSelectedCA(AssignableAdvocateTestHelper):
    @mock.patch("tasks.braze.update_care_advocate_attrs.delay")
    def test_assign_selected_care_advocate(
        self, mock_update_care_advocate_attrs, default_user, factories
    ):
        # Given a user and AssignableAdvocate
        prac = factories.PractitionerUserFactory()
        aa = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=prac
        )

        # When
        AssignableAdvocate.assign_selected_care_advocate(default_user, aa)

        # Then
        mpa_after_assignment = MemberPractitionerAssociation.query.filter_by(
            user_id=default_user.id,
            practitioner_id=prac.id,
            type=CareTeamTypes.CARE_COORDINATOR,
        ).one()
        assert mpa_after_assignment
        mock_update_care_advocate_attrs.assert_called_once_with(default_user.id)


class TestFindPotentialCareAdvocates(AssignableAdvocateTestHelper):
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_cx_choices_from_member_matching"
    )
    @freeze_time(datetime.utcnow().replace(minute=0, second=0, microsecond=0))
    def test_find_potential_care_advocates__7_day(
        self,
        get_cx_choices_from_member_matching_mock,
    ):
        # Given a practitioner with next_availability in the next 7 days
        member = self.create_member()
        prac_profile = self.create_aa_prac_profile()
        prac_profile.next_availability = datetime.utcnow() + timedelta(days=5)
        aa = AssignableAdvocate.query.get(prac_profile.user_id)
        get_cx_choices_from_member_matching_mock.return_value = [aa]

        # When
        (
            cx_choices,
            available_advocate_ids_7days,
        ) = AssignableAdvocate.find_potential_care_advocates(member, None)

        # Then
        assert cx_choices == [aa]
        assert available_advocate_ids_7days == [aa.practitioner_id]

    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_catch_all_cx_choices_from_member_matching"
    )
    @freeze_time(datetime.utcnow().replace(minute=0, second=0, microsecond=0))
    def test_find_potential_care_advocates__7_day_catch_all(
        self,
        get_catch_all_cx_choices_from_member_matching,
    ):
        # Given a practitioner with next_availability in the next 3 days
        member = self.create_member()
        prac_profile = self.create_aa_prac_profile()
        prac_profile.next_availability = datetime.utcnow() + timedelta(days=5)
        aa = AssignableAdvocate.query.get(prac_profile.user_id)
        get_catch_all_cx_choices_from_member_matching.return_value = [aa]

        logs_to_emit = []

        # When
        (
            cx_choices,
            available_advocate_ids_7days,
        ) = AssignableAdvocate.find_potential_care_advocates(
            member, None, logs_to_emit_with_matched_ca=logs_to_emit
        )

        # Then
        assert cx_choices == [aa]
        assert available_advocate_ids_7days == [aa.practitioner_id]
        assert len(logs_to_emit) == 1

    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_cx_choices_from_member_matching"
    )
    @freeze_time(datetime.utcnow().replace(minute=0, second=0, microsecond=0))
    def test_find_potential_care_advocates__filter_by_language(
        self,
        get_cx_choices_from_member_matching_mock,
        factories,
    ):
        # Given four practitioners with next_availability in the next 7 days
        member = self.create_member()

        # Two expected practitioners have the same language
        fr = factories.LanguageFactory.create(name="French", iso_639_3="fra")
        prac_profile_1 = self.create_aa_prac_profile()
        prac_profile_1.next_availability = datetime.utcnow() + timedelta(days=5)
        prac_profile_1.languages = [fr]
        expected_aa_1 = AssignableAdvocate.query.get(prac_profile_1.user_id)
        prac_profile_2 = self.create_aa_prac_profile()
        prac_profile_2.next_availability = datetime.utcnow() + timedelta(days=5)
        prac_profile_2.languages = [fr]
        expected_aa_2 = AssignableAdvocate.query.get(prac_profile_2.user_id)

        # This practitioner should be filtered due to having the wrong language
        prac_profile_2 = self.create_aa_prac_profile()
        prac_profile_2.next_availability = datetime.utcnow() + timedelta(days=5)
        eng = factories.LanguageFactory.create(name="English", iso_639_3="eng")
        prac_profile_2.languages = [eng]

        # This practitioner should be filtered due to having no language
        prac_profile_3 = self.create_aa_prac_profile()
        prac_profile_3.next_availability = datetime.utcnow() + timedelta(days=5)

        get_cx_choices_from_member_matching_mock.return_value = [
            expected_aa_1,
            expected_aa_2,
        ]

        # When
        (
            cx_choices,
            available_advocate_ids_7days,
        ) = AssignableAdvocate.find_potential_care_advocates(member, None, fr.iso_639_3)

        # Then
        get_cx_choices_from_member_matching_mock.assert_called_with(
            [expected_aa_1.practitioner_id, expected_aa_2.practitioner_id],
            user=mock.ANY,
            risk_factors=mock.ANY,
            logs_to_emit_with_matched_ca=[],
        )
        assert cx_choices == [expected_aa_1, expected_aa_2]
        assert available_advocate_ids_7days == [
            expected_aa_1.practitioner_id,
            expected_aa_2.practitioner_id,
        ]


class TestAddCareCoordinatorCALoadBalancingON(AssignableAdvocateTestHelper):
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_with_next_availability"
    )
    @mock.patch.object(AssignableAdvocate, "get_cx_choices_from_member_matching")
    @mock.patch.object(AssignableAdvocate, "validate_consistent_next_availability")
    def test_add_care_coordinator_for_member__ca_load_balancing_on__cascade_three_day_availability(
        self,
        mock_validate_consistent_next_availability,
        mock_get_cx_choices_from_member_matching,
        mock_get_advocates_with_next_availability,
        mock_ca_validate_availability_flag,
        factories,
    ):
        # set feature flag on
        mock_ca_validate_availability_flag(True)

        # Given
        member = factories.MemberFactory.create()
        track = factories.MemberTrackFactory.create(name="pregnancy", user=member)

        prac_profile = self.create_aa_prac_profile()
        aa = AssignableAdvocate.query.get(prac_profile.user_id)
        mock_get_cx_choices_from_member_matching.return_value = [aa]

        # When
        AssignableAdvocate.add_care_coordinator_for_member(user=track.user)

        # Then
        assert mock_get_advocates_with_next_availability.call_count == 1
        assert mock_get_cx_choices_from_member_matching.call_count == 1
        assert member.care_coordinators == [aa.practitioner.user]
        assert mock_validate_consistent_next_availability.call_count == 1

    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_with_next_availability"
    )
    @mock.patch.object(AssignableAdvocate, "get_cx_choices_from_member_matching")
    @mock.patch.object(
        AssignableAdvocate, "get_catch_all_cx_choices_from_member_matching"
    )
    @mock.patch.object(AssignableAdvocate, "validate_consistent_next_availability")
    def test_add_care_coordinator_for_member__ca_load_balancing_on__cascade_catch_all_three_day_availability(
        self,
        mock_validate_consistent_next_availability,
        mock_get_catch_all_cx_choices_from_member_matching,
        mock_get_cx_choices_from_member_matching,
        mock_get_advocates_with_next_availability,
        mock_ca_validate_availability_flag,
        factories,
    ):
        # set feature flag on
        mock_ca_validate_availability_flag(True)

        # Given
        member = factories.MemberFactory.create()
        track = factories.MemberTrackFactory.create(name="pregnancy", user=member)

        prac_profile = self.create_aa_prac_profile()
        aa = AssignableAdvocate.query.get(prac_profile.user_id)

        mock_get_advocates_with_next_availability.return_value = []
        mock_get_cx_choices_from_member_matching.return_value = []
        mock_get_catch_all_cx_choices_from_member_matching.return_value = [aa]

        # When
        AssignableAdvocate.add_care_coordinator_for_member(user=track.user)

        # Then
        assert mock_get_advocates_with_next_availability.call_count == 1
        assert mock_get_cx_choices_from_member_matching.call_count == 1
        assert mock_get_catch_all_cx_choices_from_member_matching.call_count == 1
        assert member.care_coordinators == [aa.practitioner.user]
        assert mock_validate_consistent_next_availability.call_count == 1

    @mock.patch.object(AssignableAdvocate, "get_cx_choices_from_member_matching")
    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_with_capacity_and_availability"
    )
    @mock.patch.object(AssignableAdvocate, "validate_consistent_next_availability")
    @freeze_time(datetime.utcnow().replace(minute=0, second=0, microsecond=0))
    def test_add_care_coordinator_for_member__ca_load_balancing_on__capacity_availability_calls_seven_days(
        self,
        mock_validate_consistent_next_availability,
        mock_get_advocates_with_capacity_and_availability,
        mock_get_cx_choices_from_member_matching,
        mock_ca_validate_availability_flag,
    ):
        # set feature flag on
        mock_ca_validate_availability_flag(True)

        # Given a member
        now = datetime.utcnow()
        member = self.create_member()

        # And Practitioner next availability within the next 3 days
        prac_profile = self.create_aa_prac_profile()
        prac_profile.next_availability = now + timedelta(1)
        aa = AssignableAdvocate.query.get(prac_profile.user_id)

        # assume that they passed the member-matching algorithm
        mock_get_cx_choices_from_member_matching.return_value = [aa]

        # When we try to add a care coordinator for that member
        AssignableAdvocate.add_care_coordinator_for_member(user=member)

        # Then get_advocates_with_capacity_and_availability is called with 7 days out; and only once
        mock_get_advocates_with_capacity_and_availability.assert_called_with(
            days_out_from_today=7, user=member
        )
        assert mock_get_advocates_with_capacity_and_availability.call_count == 1
        assert mock_validate_consistent_next_availability.call_count == 1

    @mock.patch(
        "care_advocates.models.assignable_advocates.AssignableAdvocate.get_advocates_with_next_availability"
    )
    @mock.patch.object(
        AssignableAdvocate, "get_catch_all_cx_choices_from_member_matching"
    )
    @mock.patch.object(AssignableAdvocate, "get_cx_choices_from_member_matching")
    def test_add_care_coordinator_for_member__ca_load_balancing_on__cascade_random_assignment(
        self,
        mock_get_cx_choices_from_member_matching,
        mock_get_catch_all_cx_choices_from_member_matching,
        mock_get_advocates_with_next_availability,
        factories,
    ):
        # Given
        member = factories.MemberFactory.create()
        track = factories.MemberTrackFactory.create(name="pregnancy", user=member)

        prac_profile = self.create_aa_prac_profile()
        aa = AssignableAdvocate.query.get(prac_profile.user_id)

        mock_get_advocates_with_next_availability.side_effect = [
            [],
            [aa.practitioner_id],
        ]
        mock_get_cx_choices_from_member_matching.side_effect = [[], []]
        mock_get_catch_all_cx_choices_from_member_matching.side_effect = [[], []]
        # set feature flag on

        # When
        AssignableAdvocate.add_care_coordinator_for_member(user=track.user)

        # Then
        assert mock_get_advocates_with_next_availability.call_count == 1
        assert mock_get_cx_choices_from_member_matching.call_count == 1
        assert mock_get_catch_all_cx_choices_from_member_matching.call_count == 1
        assert member.care_coordinators == [aa.practitioner.user]

    @mock.patch.object(
        AssignableAdvocate, "get_advocates_with_capacity_and_availability"
    )
    @mock.patch.object(AssignableAdvocate, "get_cx_choices_from_member_matching")
    @mock.patch.object(AssignableAdvocate, "get_cx_with_lowest_weekly_utilization")
    @mock.patch("authn.models.user.User.add_care_team_via_care_coordination")
    @mock.patch.object(AssignableAdvocate, "validate_consistent_next_availability")
    def test_add_care_coordinator_for_member__ca_load_balancing_on__get_cx_utilization_toggle_enabled_called(
        self,
        mock_validate_consistent_next_availability,
        mock_add_care_team_via_care_coordination,
        mock_get_cx_with_lowest_weekly_utilization,
        mock_get_cx_choices_from_member_matching,
        mock_get_advocates_with_capacity_and_availability,
        mock_ca_validate_availability_flag,
        mock_intro_appointment_flag,
    ):
        # Given
        # set feature flag on
        mock_ca_validate_availability_flag(True)
        mock_intro_appointment_flag(
            "pregnancy, menopause, postpartum, fertility, pregnancyloss, trying_to_conceive, egg_freezing, adoption, surrogacy"
        )

        member = self.create_member()
        aa = self.create_advocate()

        mocked_response_get_advocates_with_capacity_and_availability = []
        mock_get_advocates_with_capacity_and_availability.return_value = (
            mocked_response_get_advocates_with_capacity_and_availability
        )
        mock_get_cx_choices_from_member_matching.return_value = [aa]
        mock_get_cx_with_lowest_weekly_utilization.return_value = aa

        # When
        AssignableAdvocate.add_care_coordinator_for_member(user=member)

        # Then
        mock_get_advocates_with_capacity_and_availability.assert_called_once_with(
            days_out_from_today=7, user=member
        )

        mock_get_cx_choices_from_member_matching.assert_called_once_with(
            mocked_response_get_advocates_with_capacity_and_availability,
            user=member,
            risk_factors=[],
            logs_to_emit_with_matched_ca=[],
        )

        mock_get_cx_with_lowest_weekly_utilization.assert_called_once_with(
            [aa], mock.ANY, mock.ANY, member.id
        )
        mock_add_care_team_via_care_coordination.assert_called_once_with(
            aa.practitioner_id
        )
        mock_validate_consistent_next_availability.assert_called_once_with(
            aa.practitioner_id
        )


class TestGetCXWithLowestWeeklyUtilization(AssignableAdvocateTestHelper):
    @pytest.fixture
    def start_date(self):
        return date(2023, 5, 23)

    @pytest.fixture
    def end_date(self):
        return date(2023, 5, 29)

    @pytest.fixture
    def now(self):
        return datetime(2023, 5, 23, 9, 0, 0)

    @pytest.mark.parametrize("invalid_cx_value", [None, [], 123456789])
    @mock.patch.object(MassAvailabilityCalculator, "get_mass_existing_appointments")
    def test_get_cx_with_lowest_weekly_utilization__invalid_cx_value(
        self,
        mock_get_mass_existing_appointments,
        invalid_cx_value,
        start_date,
        end_date,
    ):
        # Given - invalid cx values (parametrized above)
        # When - we request the lowest utlization
        selected_cx = AssignableAdvocate.get_cx_with_lowest_weekly_utilization(
            invalid_cx_value,
            start_date,
            end_date,
        )

        # Then - None is returned
        assert selected_cx is None
        mock_get_mass_existing_appointments.assert_not_called()

    @mock.patch.object(MassAvailabilityCalculator, "get_mass_existing_appointments")
    def test_get_cx_with_lowest_weekly_utilization__one_cx(
        self,
        mock_get_mass_existing_appointments,
        start_date,
        end_date,
    ):
        # Given
        member = self.create_member()
        aa = self.create_advocate()

        # When
        selected_cx = AssignableAdvocate.get_cx_with_lowest_weekly_utilization(
            [aa],
            member.id,
            start_date,
            end_date,
        )

        # Then
        assert selected_cx.practitioner_id == aa.practitioner_id
        mock_get_mass_existing_appointments.assert_not_called()

    def test_get_cx_with_lowest_weekly_utilization__practitioner_with_lower_utilization(
        self,
        start_date,
        end_date,
        now,
    ):
        # Given - 2 practitioners with different utilization
        member = self.create_member()

        # Practitioner 1: 2 appts, 2 events
        aa_1 = self.create_advocate()
        self.create_appt(aa_1.practitioner, now)
        self.create_appt(aa_1.practitioner, now + relativedelta(days=1))
        self.create_event(aa_1.practitioner, now)
        self.create_event(aa_1.practitioner, now + relativedelta(days=1))

        # Practitioner 2: 1 appt, 2 events
        aa_2 = self.create_advocate()
        self.create_appt(aa_2.practitioner, now)
        self.create_event(aa_2.practitioner, now)
        self.create_event(aa_2.practitioner, now + relativedelta(days=1))

        # When
        cx_choices = [aa_1, aa_2]
        expected_cx = aa_2
        selected_cx = AssignableAdvocate.get_cx_with_lowest_weekly_utilization(
            cx_choices, start_date, end_date, member.id
        )

        # Then - we get the expected cx with the lower utilization
        assert selected_cx == expected_cx

    @mock.patch.object(MassAvailabilityCalculator, "get_mass_existing_appointments")
    @mock.patch.object(
        MassAvailabilityCalculator, "get_mass_existing_available_schedule_events"
    )
    def test_get_cx_with_lowest_weekly_utilization__practitioner_with_lower_utilization_mocked(
        self,
        mock_get_mass_existing_available_schedule_events,
        mock_get_mass_existing_appointments,
        start_date,
        end_date,
        now,
    ):
        # Given
        member = self.create_member()
        mock_all_appts = defaultdict(list)
        mock_all_events = defaultdict(list)

        # Practitioner 1: 2 appts, 2 events
        aa_1 = self.create_advocate()
        mock_all_appts[aa_1.practitioner_id] = [
            self.create_appt(aa_1.practitioner, now),
            self.create_appt(aa_1.practitioner, now + relativedelta(days=1)),
        ]
        mock_all_events[aa_1.practitioner_id] = [
            self.create_event(aa_1.practitioner, now),
            self.create_event(aa_1.practitioner, now + relativedelta(days=1)),
        ]

        # Practitioner 2: 1 appt, 2 events
        aa_2 = self.create_advocate()
        mock_all_appts[aa_2.practitioner_id] = [
            self.create_appt(aa_2.practitioner, now),
        ]
        mock_all_events[aa_2.practitioner_id] = [
            self.create_event(aa_2.practitioner, now),
            self.create_event(aa_2.practitioner, now + relativedelta(days=1)),
        ]

        # Practitioner 3: 3 appts, 2 events
        aa_3 = self.create_advocate()
        mock_all_appts[aa_3.practitioner_id] = [
            self.create_appt(aa_3.practitioner, now),
            self.create_appt(aa_3.practitioner, now + timedelta(hours=1)),
            self.create_appt(aa_3.practitioner, now + relativedelta(days=1)),
        ]
        mock_all_events[aa_3.practitioner_id] = [
            self.create_event(aa_3.practitioner, now),
            self.create_event(aa_3.practitioner, now + relativedelta(days=1)),
        ]

        # Mock the appts and schedule_events return values
        mock_get_mass_existing_appointments.return_value = mock_all_appts, None
        mock_get_mass_existing_available_schedule_events.return_value = mock_all_events

        # When
        cx_choices = [aa_1, aa_2, aa_3]
        expected_cx = aa_2
        selected_cx = AssignableAdvocate.get_cx_with_lowest_weekly_utilization(
            cx_choices,
            start_date,
            end_date,
            member.id,
        )

        # Then
        assert selected_cx == expected_cx

    def test_get_cx_with_lowest_weekly_utilization__practitioner_with_same_utilization(
        self,
        start_date,
        end_date,
        now,
    ):
        # Given
        member = self.create_member()

        # Practitioner 1: 2 appts, 2 events
        aa_1 = self.create_advocate()
        self.create_appt(aa_1.practitioner, now)
        self.create_appt(aa_1.practitioner, now + relativedelta(days=1))
        self.create_event(aa_1.practitioner, now)
        self.create_event(aa_1.practitioner, now + relativedelta(days=1))

        # Practitioner 2: 2 appts, 2 events
        aa_2 = self.create_advocate()
        self.create_appt(aa_2.practitioner, now)
        self.create_appt(aa_2.practitioner, now + relativedelta(days=1))
        self.create_event(aa_2.practitioner, now)
        self.create_event(aa_2.practitioner, now + relativedelta(days=1))

        # Practitioner 3: 2 appts, 1 event
        aa_3 = self.create_advocate()
        self.create_appt(aa_3.practitioner, now)
        self.create_appt(aa_3.practitioner, now + relativedelta(hours=1))
        self.create_event(aa_3.practitioner, now)

        # Mock random.choice - creates error for factories as a decorator
        with mock.patch("random.choice") as mock_random_choice:
            # Force the random choice
            expected_cx_ids = [aa_1.practitioner_id, aa_2.practitioner_id]
            expected_cx = aa_1
            mock_random_choice.return_value = expected_cx.practitioner_id

            # When
            cx_choices = [aa_1, aa_2, aa_3]
            AssignableAdvocate.get_cx_with_lowest_weekly_utilization(
                cx_choices,
                start_date,
                end_date,
                member.id,
            )

            # Than
            mock_random_choice.assert_called_once()
            mock_call_args, _ = mock_random_choice.call_args
            mock_possible_cx_ids = mock_call_args[0]
            mock_possible_cx_ids.sort()
            assert mock_possible_cx_ids == expected_cx_ids

    @freeze_time("2023-03-14T09:00:00")
    @mock.patch.object(MassAvailabilityCalculator, "get_mass_existing_appointments")
    @mock.patch.object(
        MassAvailabilityCalculator, "get_mass_existing_available_schedule_events"
    )
    def test_get_cx_with_lowest_weekly_utilization__practitioner_with_same_utilization_mocked(
        self,
        mock_get_mass_existing_available_schedule_events,
        mock_get_mass_existing_appointments,
        start_date,
        end_date,
        now,
    ):
        # Given
        member = self.create_member()
        mock_all_appts = defaultdict(list)
        mock_all_events = defaultdict(list)

        # Practitioner 1: 2 appts, 2 events
        aa_1 = self.create_advocate()
        mock_all_appts[aa_1.practitioner_id] = [
            self.create_appt(aa_1.practitioner, now),
            self.create_appt(aa_1.practitioner, now + relativedelta(days=1)),
        ]
        mock_all_events[aa_1.practitioner_id] = [
            self.create_event(aa_1.practitioner, now),
            self.create_event(aa_1.practitioner, now + relativedelta(days=1)),
        ]

        # Practitioner 2: 2 appts, 2 events
        aa_2 = self.create_advocate()
        mock_all_appts[aa_2.practitioner_id] = [
            self.create_appt(aa_2.practitioner, now),
            self.create_appt(aa_2.practitioner, now + relativedelta(days=1)),
        ]
        mock_all_events[aa_2.practitioner_id] = [
            self.create_event(aa_2.practitioner, now),
            self.create_event(aa_2.practitioner, now + relativedelta(days=1)),
        ]

        # Mock the appts and schedule_events return values
        mock_get_mass_existing_appointments.return_value = mock_all_appts, None
        mock_get_mass_existing_available_schedule_events.return_value = mock_all_events

        # Mock random.choice - creates error for factories as a decorator
        with mock.patch("random.choice") as mock_random_choice:
            # Force the random choice
            expected_cx = aa_2
            mock_random_choice.return_value = expected_cx.practitioner_id

            # When
            cx_choices = [aa_1, aa_2]
            selected_cx = AssignableAdvocate.get_cx_with_lowest_weekly_utilization(
                cx_choices,
                start_date,
                end_date,
                member.id,
            )

            # Than
            # Random should be called with 2 cxs with the same utilization
            mock_random_choice.assert_called_once_with(
                [aa_1.practitioner_id, aa_2.practitioner_id]
            )
            assert selected_cx == expected_cx

    @mock.patch.object(MassAvailabilityCalculator, "get_mass_existing_appointments")
    @mock.patch.object(
        MassAvailabilityCalculator, "get_mass_existing_available_schedule_events"
    )
    def test_get_cx_with_lowest_weekly_utilization__practitioner_no_appts(
        self,
        mock_get_mass_existing_available_schedule_events,
        mock_get_mass_existing_appointments,
        start_date,
        end_date,
        now,
    ):
        # Given
        member = self.create_member()
        mock_all_appts = defaultdict(list)
        mock_all_events = defaultdict(list)

        # Practitioner 1: 0 appts, 2 events
        aa_1 = self.create_advocate()
        mock_all_events[aa_1.practitioner_id] = [
            self.create_event(aa_1.practitioner, now),
            self.create_event(aa_1.practitioner, now + relativedelta(days=1)),
        ]

        # Practitioner 2: 2 appts, 2 events
        aa_2 = self.create_advocate()
        mock_all_appts[aa_2.practitioner_id] = [
            self.create_appt(aa_2.practitioner, now),
            self.create_appt(aa_2.practitioner, now + relativedelta(days=1)),
        ]
        mock_all_events[aa_2.practitioner_id] = [
            self.create_event(aa_2.practitioner, now),
            self.create_event(aa_2.practitioner, now + relativedelta(days=1)),
        ]

        # Mock the appts and schedule_events return values
        mock_get_mass_existing_appointments.return_value = mock_all_appts, None
        mock_get_mass_existing_available_schedule_events.return_value = mock_all_events

        # When
        cx_choices = [aa_1, aa_2]
        expected_cx = aa_1
        selected_cx = AssignableAdvocate.get_cx_with_lowest_weekly_utilization(
            cx_choices,
            start_date,
            end_date,
            member.id,
        )

        # Then
        assert selected_cx == expected_cx

    @mock.patch.object(MassAvailabilityCalculator, "get_mass_existing_appointments")
    @mock.patch.object(
        MassAvailabilityCalculator, "get_mass_existing_available_schedule_events"
    )
    @freeze_time(datetime.utcnow().replace(minute=0, second=0, microsecond=0))
    def test_get_cx_with_lowest_weekly_utilization__start_date_stop_date_provided(
        self,
        mock_get_mass_existing_available_schedule_events,
        mock_get_mass_existing_appointments,
    ):
        # Given - a provided time
        now = datetime.utcnow()
        member = self.create_member()
        start_date = date(2023, 5, 19)
        start_datetime = datetime.combine(start_date, time(0, 0, 0, 0))
        end_date = date(2023, 5, 25)
        end_datetime = datetime.combine(end_date, time(23, 59, 59, 999))
        now = datetime.combine(start_date, time(13, 30, 15, 123))
        mock_get_mass_existing_appointments.return_value = (None, None)
        mock_get_mass_existing_available_schedule_events.return_value = None

        # Practitioner 1: 2 appts, 2 events
        aa_1 = self.create_advocate()
        self.create_appt(aa_1.practitioner, now)
        self.create_appt(aa_1.practitioner, now + relativedelta(days=1))
        self.create_event(aa_1.practitioner, now)
        self.create_event(aa_1.practitioner, now + relativedelta(days=1))

        # Practitioner 2: 1 appt, 2 events
        aa_2 = self.create_advocate()
        self.create_appt(aa_2.practitioner, now)
        self.create_event(aa_2.practitioner, now)
        self.create_event(aa_2.practitioner, now + relativedelta(days=1))

        # When
        cx_choices = [aa_1, aa_2]
        AssignableAdvocate.get_cx_with_lowest_weekly_utilization(
            cx_choices,
            start_date,
            end_date,
            member.id,
        )

        # Then - the correct values are passed
        mock_get_mass_existing_appointments.assert_called_with(
            start_time=start_datetime,
            end_time=end_datetime,
            provider_ids=[aa_1.practitioner_id, aa_2.practitioner_id],
        )
        mock_get_mass_existing_available_schedule_events.assert_called_with(
            start_time=start_datetime,
            end_time=end_datetime,
            user_ids=[aa_1.practitioner_id, aa_2.practitioner_id],
        )

    @mock.patch.object(AssignableAdvocate, "_lowest_utilization_cx_ids")
    def test_get_cx_with_lowest_weekly_utilization__correct_utilizations(
        self,
        mock_lowest_utilization_cx_ids,
    ):
        # Given
        start_date = date(2023, 5, 19)
        end_date = date(2023, 5, 25)
        aa1_utilization = 0.125
        aa2_utilization = 0.143
        member = self.create_member()

        # Practitioner 1: 7 appts, 7 events
        aa_1 = self.create_advocate()
        # Appts - create for 19-25
        for day in range(19, 26):
            self.create_appt(aa_1.practitioner, datetime(2023, 5, day, 9, 0, 0, 0))
        # These appts should NOT be in the calculation (outside of range)
        self.create_appt(aa_1.practitioner, datetime(2023, 5, 26, 9, 0, 0, 0))
        self.create_appt(aa_1.practitioner, datetime(2023, 5, 26, 10, 0, 0, 0))
        # Events - create for 19-25
        for day in range(19, 26):
            self.create_event(aa_1.practitioner, datetime(2023, 5, day, 9, 0, 0, 0))
        # This event should NOT be in the calculation (outside of range)
        self.create_event(aa_1.practitioner, datetime(2023, 5, 26, 9, 0, 0, 0))

        # Practitioner 2: 8 appt, 7 events
        aa_2 = self.create_advocate()
        # Appts - create for 19-25
        for day in range(19, 26):
            self.create_appt(aa_2.practitioner, datetime(2023, 5, day, 9, 0, 0, 0))
        # Add additional appt
        self.create_appt(aa_2.practitioner, datetime(2023, 5, 25, 10, 0, 0, 0))
        # Events - create for 19-25
        for day in range(19, 26):
            self.create_event(aa_2.practitioner, datetime(2023, 5, day, 9, 0, 0, 0))

        # When
        cx_choices = [aa_1, aa_2]
        mock_lowest_utilization_cx_ids.return_value = (
            [aa_1.practitioner_id],
            aa1_utilization,
        )
        AssignableAdvocate.get_cx_with_lowest_weekly_utilization(
            cx_choices,
            start_date,
            end_date,
            member.id,
        )

        # Then - the correct utilizations are calculated and used
        Utilization = namedtuple("Utilization", "user_id utilization")
        weekly_utilizations = [
            Utilization(user_id=aa_1.practitioner_id, utilization=aa1_utilization),
            Utilization(user_id=aa_2.practitioner_id, utilization=aa2_utilization),
        ]
        mock_lowest_utilization_cx_ids.assert_called_with(weekly_utilizations)


class TestGetCXWithFewestAssignmentOverTimePeriod(AssignableAdvocateTestHelper):
    @pytest.fixture
    def start_date(self, end_date):
        return end_date - timedelta(days=13)

    @pytest.fixture
    def end_date(self):
        return date.today()

    @pytest.mark.parametrize("invalid_cx_value", [None, [], 123456789])
    def test_get_cx_with_fewest_assignments_over_time_period__invalid_cx_value(
        self,
        invalid_cx_value,
        start_date,
        end_date,
    ):
        # Given - invalid cx values (parametrized above)

        # When we request the lowest assignments cx
        selected_cx = (
            AssignableAdvocate.get_cx_with_fewest_assignments_over_time_period(
                invalid_cx_value,
                start_date,
                end_date,
            )
        )

        # Then - None is returned
        assert selected_cx is None

    def test__number_of_assignments_in_time_range_by_cx_sorted__some_cx_no_assignments(
        self, factories
    ):
        # Given a CA with 3 assignments and another CA with 0 assignments
        prac_1 = factories.PractitionerUserFactory()
        user_1 = factories.EnterpriseUserFactory()
        factories.MemberPractitionerAssociationFactory(
            type=CareTeamTypes.CARE_COORDINATOR,
            practitioner_id=prac_1.id,
            user_id=user_1.id,
        )
        user_2 = factories.EnterpriseUserFactory()
        factories.MemberPractitionerAssociationFactory(
            type=CareTeamTypes.CARE_COORDINATOR,
            practitioner_id=prac_1.id,
            user_id=user_2.id,
        )
        user_3 = factories.EnterpriseUserFactory()
        factories.MemberPractitionerAssociationFactory(
            type=CareTeamTypes.CARE_COORDINATOR,
            practitioner_id=prac_1.id,
            user_id=user_3.id,
        )
        prac_2 = factories.PractitionerUserFactory()

        # When we call the function
        end_date = date.today()
        start_date = end_date - timedelta(days=1)
        start_datetime = datetime.combine(start_date, time(0, 0, 0, 0))
        end_datetime = datetime.combine(end_date, time(23, 59, 59, 999))

        ca_ids = [prac_1.id, prac_2.id]

        sorted_number_of_assignments = (
            AssignableAdvocate._number_of_assignments_in_time_range_by_cx_sorted(
                ca_ids, start_datetime, end_datetime
            )
        )

        # Then the function counts the assignments correctly including for CA's with 0 assignments
        expected_results = [(prac_2.id, 0), (prac_1.id, 3)]
        assert sorted_number_of_assignments == expected_results


class TestLowestNumberOfAssignmentsCXIds(AssignableAdvocateTestHelper):
    def test__lowest_num_assignments_cx_ids__one_match(
        self,
    ):
        # Given 3 CA's with different num_assignments
        NumAssignments = namedtuple("NumAssignments", "user_id assignment_count")
        sorted_number_of_assignments = [
            NumAssignments(user_id=1, assignment_count=10),
            NumAssignments(user_id=2, assignment_count=18),
            NumAssignments(user_id=3, assignment_count=25),
        ]

        # When we look for the lowest number of assignments
        lowest_cx_ids = AssignableAdvocate._lowest_number_of_assignments_cx_ids(
            sorted_number_of_assignments
        )

        # Then we return the CA with the lowest number of assignments
        expected_results = ([1], 10)
        assert lowest_cx_ids == expected_results

    def test__lowest_num_assignments_cx_ids__two_matches(
        self,
    ):
        # Given 3 CA's, 2 with the same num_assignments
        NumAssignments = namedtuple("NumAssignments", "user_id assignment_count")
        sorted_number_of_assignments = [
            NumAssignments(user_id=1, assignment_count=10),
            NumAssignments(user_id=2, assignment_count=10),
            NumAssignments(user_id=3, assignment_count=25),
        ]

        # When we look for the lowest number of assignments
        lowest_cx_ids = AssignableAdvocate._lowest_number_of_assignments_cx_ids(
            sorted_number_of_assignments
        )

        # Then we return the two CA's with the lowest number of assignments
        expected_results = ([1, 2], 10)
        assert lowest_cx_ids == expected_results


class TestTotalScheduleEventHoursByCx(AssignableAdvocateTestHelper):
    @freeze_time("2023-03-14T09:00:00")
    def test__total_schedule_event_hours_by_cx(
        self,
    ):
        # Given
        now = datetime.utcnow()
        all_events = defaultdict(list)
        expected_output = defaultdict(float)
        one_day = relativedelta(days=1)

        # Prac 1
        aa_1 = self.create_advocate()
        event_1 = self.create_event(aa_1.practitioner, now, 8)
        event_2 = self.create_event(aa_1.practitioner, now + one_day, 4)
        event_3 = self.create_event(
            aa_1.practitioner, now + one_day + timedelta(hours=5), 4
        )
        all_events[event_1.id].append(event_1)
        all_events[event_2.id].append(event_2)
        all_events[event_3.id].append(event_3)
        # Cast string to mimic get_mass_existing_available_schedule_events (data comes raw from the db, not the orm)
        # Cast float because the datatimes are subtracted, converted to seconds, and converted to hours
        expected_output[str(aa_1.practitioner_id)] = float(8 + 4 + 4)

        # Prac 2
        aa_2 = self.create_advocate()
        event_4 = self.create_event(aa_2.practitioner, now, 8)
        all_events[event_4.id].append(self.create_event(aa_2.practitioner, now, 8))
        # See notes for Prac 1
        expected_output[str(aa_2.practitioner_id)] = float(8)

        # When
        hours_per_prac = AssignableAdvocate._total_schedule_event_hours_by_cx(
            all_events
        )

        # Then
        assert hours_per_prac == expected_output


class TestWeeklyUtilizationByCxSorted(AssignableAdvocateTestHelper):
    @freeze_time(datetime.utcnow().replace(minute=0, second=0, microsecond=0))
    def test__weekly_utilization_by_cx_sorted(
        self,
    ):
        # Given
        now = datetime.utcnow()
        appts_per_prac = defaultdict(list)
        hours_per_prac = defaultdict(float)
        expected_output = list

        # Prac 1, 3 appts, 16 scheduled hours (3/16 = 0.1875 = ~0.188)
        aa_1 = self.create_advocate()
        appts_per_prac[aa_1.practitioner_id] = [
            self.create_appt(aa_1.practitioner, now),
            self.create_appt(aa_1.practitioner, now + timedelta(hours=1)),
            self.create_appt(aa_1.practitioner, now + relativedelta(days=1)),
        ]
        hours_per_prac[aa_1.practitioner_id] = float(16)

        # Prac 2, 1 appt, 8 scheduled hours (1/8 = 0.125)
        aa_2 = self.create_advocate()
        appts_per_prac[aa_2.practitioner_id] = [
            self.create_appt(aa_2.practitioner, now),
        ]
        hours_per_prac[aa_2.practitioner_id] = float(8)

        # When
        Utilization = namedtuple("Utilization", "user_id utilization")
        expected_output = [
            Utilization(user_id=aa_2.practitioner_id, utilization=0.125),
            Utilization(user_id=aa_1.practitioner_id, utilization=0.188),
        ]
        sorted_utilizations = AssignableAdvocate._weekly_utilization_by_cx_sorted(
            appts_per_prac, hours_per_prac
        )

        # Then
        assert sorted_utilizations == expected_output


class TestLowestUtilizationCxIds(AssignableAdvocateTestHelper):
    def test__lowest_utilization_cx_ids__one_match(
        self,
    ):
        # Given
        Utilization = namedtuple("Utilization", "user_id utilization")
        sorted_utilizations = [
            Utilization(user_id=1, utilization=0.100),
            Utilization(user_id=2, utilization=0.188),
            Utilization(user_id=3, utilization=0.250),
        ]

        # When
        lowest_cx_ids = AssignableAdvocate._lowest_utilization_cx_ids(
            sorted_utilizations
        )

        # Then
        expected_results = ([1], 0.1)
        assert lowest_cx_ids == expected_results

    def test__lowest_utilization_cx_ids__two_matches(
        self,
    ):
        # Given
        Utilization = namedtuple("Utilization", "user_id utilization")
        sorted_utilizations = [
            Utilization(user_id=1, utilization=0.10),
            Utilization(user_id=2, utilization=0.10),
            Utilization(user_id=3, utilization=0.25),
        ]

        # When
        lowest_cx_ids = AssignableAdvocate._lowest_utilization_cx_ids(
            sorted_utilizations
        )

        # Then
        expected_results = ([1, 2], 0.1)
        assert lowest_cx_ids == expected_results


class TestCareAdvocateHas3DayAvailability(AssignableAdvocateTestHelper):
    @pytest.mark.parametrize(
        "num_days,expected_result", [(0, True), (1, True), (2, True), (4, False)]
    )
    @pytest.mark.skip(reason="Flaky")
    def test_care_advocate_has_3_day_availability(self, num_days, expected_result):
        # given 3 CAs, with next_availability
        number_of_days_from_now = datetime.utcnow().astimezone(
            timezone("America/New_York")
        ) + timedelta(days=num_days)
        practitioners = [
            self.create_advocate(
                practitioner_profile__next_availability=number_of_days_from_now
                + timedelta(days=i),
            )
            for i in range(0, 2)
        ]
        # when we call care_advocate_has_3_day_availability
        result = AssignableAdvocate.care_advocate_has_3_day_availability(
            [ca.practitioner_id for ca in practitioners]
        )
        # then it returns the expected result
        assert result == expected_result


class TestUserFlagsMatchEligibleRisk:
    @pytest.mark.parametrize(
        argnames="user_flag_names, result",
        argvalues=[
            ([], False),
            ([RiskFlagName.GESTATIONAL_DIABETES_AT_RISK], True),
            ([RiskFlagName.BMI_OVERWEIGHT], False),
            (
                [
                    RiskFlagName.GESTATIONAL_DIABETES_AT_RISK,
                    RiskFlagName.BMI_OVERWEIGHT,
                ],
                True,
            ),
        ],
    )
    def test_any_user_flags_match_eligible_risk_flags(
        self, user_flag_names, result, risk_flags
    ):
        user_flags = [risk_flags.get(flag_name) for flag_name in user_flag_names]
        assert (
            AssignableAdvocate.any_user_flags_match_eligible_risk_flags(user_flags)
            == result
        )
