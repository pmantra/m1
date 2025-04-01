from unittest import mock

from appointments.services.v2.notification import MemberAppointmentNotificationService
from pytests import factories
from storage.connection import db


class TestMemberAppointmentNotificationService:
    def test_send_slack_cancellation(self, enterprise_user, datetime_now):
        vertical = factories.VerticalFactory.create(products=None)
        product = factories.ProductFactory(
            vertical=vertical,
            minutes=30,
            price=2.0,
        )
        member_schedule = factories.ScheduleFactory.create(
            user=enterprise_user, user_id=enterprise_user.id
        )
        appointment = factories.AppointmentFactory.create(
            scheduled_start=datetime_now,
            member_schedule_id=member_schedule.id,
            member_schedule=member_schedule,
            product_id=product.id,
            product=product,
            cancelled_by_user_id=enterprise_user.id,
        )
        practitioner = product.practitioner
        practitioner_profile = practitioner.practitioner_profile
        phone_no = practitioner_profile.phone_number

        with mock.patch(
            "appointments.services.v2.notification.notify_bookings_channel"
        ) as mock_notify_bookings_channel:
            MemberAppointmentNotificationService(db.session).send_slack_cancellation(
                practitioner_id=product.user_id,
                member_id=enterprise_user.id,
                appointment_id=appointment.id,
                appointment_starts_in="12mins",
                cancelled_by_user_id=enterprise_user.id,
            )

        tmpl = (
            "CANCELLED - ID: <%s|%s>. Scheduled start was in %s "
            " w/ %s - Booking was %s. Cancelled by %s."
        )
        admin_link = f"https://admin.production.mvnctl.net:444/admin/appointment/edit/?id={appointment.id}"
        practitioner_info = "%s [%s]%s" % (
            practitioner.full_name,
            practitioner.email,
            f" ({phone_no})" if phone_no else "",
        )
        expected_message = tmpl % (
            admin_link,
            appointment.id,
            "12mins",
            practitioner_info,
            "External",
            "member",
        )
        mock_notify_bookings_channel.assert_called_once_with(expected_message)
