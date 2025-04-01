import sqlalchemy.orm
from sqlalchemy.orm import joinedload

from appointments.tasks.appointment_notifications import notify_vip_bookings
from authn.models.user import User
from providers.domain.model import Provider
from tracks import service as tracks_svc
from utils.slack import notify_bookings_channel, notify_enterprise_bookings_channel


class MemberAppointmentNotificationService:
    def __init__(self, session: sqlalchemy.orm.Session):
        self.session = session

    # This method is refactored and copied from
    # appointments/tasks/appointment_notifications.py
    def send_slack_cancellation(
        self,
        practitioner_id: int,
        member_id: int,
        appointment_id: int,
        appointment_starts_in: str,
        cancelled_by_user_id: int,
    ) -> None:
        practitioner = (
            self.session.query(User)
            .join(Provider, Provider.user_id == User.id)
            .options(joinedload(User.practitioner_profile))
            .filter(User.id == practitioner_id)
            .first()
        )
        if not practitioner:
            raise ValueError("No practitioner found")

        practitioner_profile = practitioner.practitioner_profile
        if not practitioner_profile:
            raise ValueError("No practitioner found")

        phone_no = practitioner_profile.phone_number

        member = self.session.query(User).filter(User.id == member_id).one()
        if not member:
            raise ValueError("No member found")

        practitioner_info = "%s [%s]%s" % (
            practitioner.full_name,
            practitioner.email,
            f" ({phone_no})" if phone_no else "",
        )
        internal_string = (
            "Internal" if member.email.endswith("mavenclinic.com") else "External"
        )
        admin_link = f"https://admin.production.mvnctl.net:444/admin/appointment/edit/?id={appointment_id}"
        member_or_practitioner = (
            "member" if cancelled_by_user_id == member_id else "practitioner"
        )

        tmpl = (
            "CANCELLED - ID: <%s|%s>. Scheduled start was in %s "
            " w/ %s - Booking was %s. Cancelled by %s."
        )
        message = tmpl % (
            admin_link,
            appointment_id,
            appointment_starts_in,
            practitioner_info,
            internal_string,
            member_or_practitioner,
        )
        notify_bookings_channel(message)

        track_svc = tracks_svc.TrackSelectionService()

        if track_svc.is_enterprise(user_id=member_id):
            notify_enterprise_bookings_channel(message)
            vip_title = "VIP Appointment Cancellation"
            notify_vip_bookings(member, vip_title, message)
