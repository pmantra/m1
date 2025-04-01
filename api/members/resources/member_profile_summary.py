import datetime

from flask_restful import abort
from sqlalchemy.orm.exc import NoResultFound

from appointments.repository.appointment import AppointmentRepository
from common.services.api import PermissionedCareTeamResource
from members.schemas.member_profile_summary import MemberProfileSummaryResultSchema
from models.profiles import MemberProfile
from tracks import TrackSelectionService
from utils.log import logger

log = logger(__name__)


class MemberProfileSummaryResource(PermissionedCareTeamResource):
    """
    Get member profile by id.

    An url param of `id` is the single term used look up the member by user_id.

    The result of this function is member profile data and upcoming appointment data.
    If there is no upcoming appointments, it returns as empty dict.
    If no value for `id` is provided, an error is returned.
    """

    def get(self, member_id: int) -> MemberProfileSummaryResultSchema:
        result = None
        try:
            result = MemberProfile.query.filter(
                MemberProfile.user_id == member_id
            ).one()
        except NoResultFound:
            pass

        if result is None:
            abort(404, message=f"No user found for id {member_id}")

        track_svc = TrackSelectionService()
        organization = track_svc.get_organization_for_user(user_id=member_id)

        if (
            result
            and organization
            and organization.US_restricted
            and (self.user.country_code is None or self.user.country_code != "US")
        ):
            abort(
                403, message="The current user isn't authorized to view this resource"
            )

        self._user_id_has_access_to_member_id_or_403(self.user.id, result.user_id)
        upcoming_appointment_args = {
            "member_id": member_id,
            "current_user_id": self.user.id,
            "scheduled_start": datetime.datetime.utcnow(),
            "exclude_statuses": ["CANCELLED"],
            "member_profile_search": True,  # to bypass the abort 404 on no results in query
        }

        schema = MemberProfileSummaryResultSchema()
        schema.context["user"] = self.user
        schema.context["organization"] = organization

        member_schedule_id = result.schedule.id if result.schedule else None
        if member_schedule_id:
            (
                pagination,
                upcoming_appointments,
            ) = AppointmentRepository().get_appointments_paginated(
                upcoming_appointment_args
            )
        else:
            upcoming_appointments = pagination = []

        if len(upcoming_appointments) == 0:
            log.info("No upcoming appointments for member_id: %s", member_id)
            data = {
                "member_profile_data": result,
            }
        else:
            data = {
                "member_profile_data": result,
                "upcoming_appointment_data": {
                    "data": upcoming_appointments,
                    "pagination": pagination,
                },
            }

        return schema.dump(data).data
