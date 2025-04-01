from appointments.models.appointment import Appointment
from care_plans.activities_completed.models import (
    CarePlanAppointmentCompletedItem,
    CarePlanContentCompletedItem,
)
from care_plans.cps_models import ActivityType
from learn.models.resource_interaction import ResourceInteraction, ResourceType


class CarePlanActivityUtil:
    @staticmethod
    def is_completed(appt: Appointment) -> bool:
        # To be considered as completed for CarePlan purposes,
        # Appointment should have a time (either start or end)
        # from both the member and the practitioner
        member_time = appt.member_started_at or appt.member_ended_at
        practitioner_time = appt.practitioner_started_at or appt.practitioner_ended_at
        completed = member_time and practitioner_time
        return completed  # type: ignore[return-value] # Incompatible return value type (got "Optional[datetime]", expected "bool")

    @staticmethod
    def to_appointment_completed_item(
        appt: Appointment,
    ) -> CarePlanAppointmentCompletedItem:
        member_id = appt.member.id
        type = ActivityType.MEET
        vertical_id = appt.product.vertical_id
        appointment_purpose = appt.purpose
        return CarePlanAppointmentCompletedItem(
            member_id, type, vertical_id, appointment_purpose  # type: ignore[arg-type] # Argument 3 to "CarePlanAppointmentCompletedItem" has incompatible type "Optional[int]"; expected "int" #type: ignore[arg-type] # Argument 4 to "CarePlanAppointmentCompletedItem" has incompatible type "Optional[str]"; expected "str"
        )

    @staticmethod
    def to_content_completed_item(
        ri: ResourceInteraction,
    ) -> CarePlanContentCompletedItem:
        member_id = ri.user_id
        slug = ri.slug
        if ri.resource_type == ResourceType.ON_DEMAND_CLASS:
            type = ActivityType.WATCH
        else:
            type = ActivityType.READ
        return CarePlanContentCompletedItem(member_id, type, slug)
