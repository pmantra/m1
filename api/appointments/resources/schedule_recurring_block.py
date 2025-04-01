from appointments.resources.constants import PractitionerScheduleResource
from appointments.services.recurring_schedule import (
    RecurringScheduleAvailabilityService,
)
from appointments.tasks.availability import delete_recurring_availability
from utils.log import logger

log = logger(__name__)


class ScheduleRecurringBlockResource(PractitionerScheduleResource):
    def delete(self, practitioner_id, schedule_recurring_block_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self._check_practitioner(practitioner_id)

        recurring_schedule_availability_service = RecurringScheduleAvailabilityService()
        recurring_schedule_availability_service.detect_booked_appointments_in_block(
            schedule_recurring_block_id=schedule_recurring_block_id,
            user_id=practitioner_id,
        )

        delete_recurring_availability.delay(
            user_id=practitioner_id,
            schedule_recurring_block_id=schedule_recurring_block_id,
        )

        return {}, 202
