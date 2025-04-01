import factory
import pytest

from admin.views.models.schedules import (
    AppointmentViewMemberEmailFilter,
    AppointmentViewMemberFirstNameFilter,
    AppointmentViewMemberLastNameFilter,
)
from appointments.models.appointment import Appointment
from storage.connection import db


@pytest.fixture
def appointment_first_name_filter():
    def query_appointment_filter(query_value):
        return (
            AppointmentViewMemberFirstNameFilter(None, None)
            .apply(db.session.query(Appointment), query_value)
            .all()
        )

    return query_appointment_filter


@pytest.fixture
def appointment_last_name_filter():
    def query_appointment_filter(query_value):
        return (
            AppointmentViewMemberLastNameFilter(None, None)
            .apply(db.session.query(Appointment), query_value)
            .all()
        )

    return query_appointment_filter


@pytest.fixture
def appointment_email_filter():
    def query_appointment_filter(query_value):
        return (
            AppointmentViewMemberEmailFilter(None, None)
            .apply(db.session.query(Appointment), query_value)
            .all()
        )

    return query_appointment_filter


class TestAdminAppointmentMemberFilters:
    @pytest.mark.parametrize(
        "filter_name",
        [
            "appointment_first_name_filter",
            "appointment_last_name_filter",
            "appointment_email_filter",
        ],
    )
    def test_empty(self, filter_name, request):
        filter_function = request.getfixturevalue(filter_name)
        res = filter_function("")
        assert len(res) == 0

    @pytest.mark.parametrize(
        "filter_name,user_field,user_value",
        [
            ("appointment_first_name_filter", "first_name", "abc"),
            ("appointment_last_name_filter", "last_name", "xyz"),
            ("appointment_email_filter", "email", "abc.xyz@mavenclinic.com"),
        ],
    )
    def test_appointment(self, request, factories, filter_name, user_field, user_value):
        # given an appointment exists for the given user
        member = factories.EnterpriseUserFactory.create(**{user_field: user_value})
        member_schedule = factories.ScheduleFactory.create(user=member)
        appointment = factories.AppointmentFactory.create(
            member_schedule=member_schedule
        )
        filter_function = request.getfixturevalue(filter_name)

        # when
        result = filter_function(user_value)
        no_result = filter_function("nomatch")

        # then
        assert result == [appointment]
        assert no_result == []

    @pytest.mark.parametrize(
        "filter_name,query_value",
        [
            ("appointment_first_name_filter", "ab"),
            ("appointment_last_name_filter", "yz"),
            ("appointment_email_filter", "c.x"),
            ("appointment_first_name_filter", "cd"),
            ("appointment_last_name_filter", "wx"),
            ("appointment_email_filter", "d.w"),
        ],
    )
    def test_double_appointment(self, request, factories, filter_name, query_value):
        members = factories.EnterpriseUserFactory.create_batch(
            size=2,
            first_name=factory.Iterator(["abc", "bcd"]),
            last_name=factory.Iterator(["xyz", "wxy"]),
            email=factory.Iterator(
                ["abc.xyz@mavenclinic.com", "bcd.wxy@mavenclinic.com"]
            ),
        )
        member_schedules = factories.ScheduleFactory.create_batch(
            size=2, user=factory.Iterator(members)
        )
        factories.AppointmentFactory.create_batch(
            size=2, member_schedule=factory.Iterator(member_schedules)
        )
        filter_function = request.getfixturevalue(filter_name)

        result = filter_function(query_value)
        assert len(result) == 1
