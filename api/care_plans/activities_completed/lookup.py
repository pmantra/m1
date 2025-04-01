from datetime import timedelta
from typing import List

from sqlalchemy.orm import joinedload

from appointments.models.appointment import Appointment
from appointments.models.schedule import Schedule
from care_plans.activities_completed.care_plan_activity_util import CarePlanActivityUtil
from care_plans.activities_completed.models import (
    CarePlanActivitiesCompletedArgs,
    CarePlanActivityCompletedItem,
    CarePlanAppointmentCompletedItem,
    CarePlanContentCompletedItem,
)
from learn.models.resource_interaction import ResourceInteraction
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class ActivitiesCompletedLookup:
    def get_activities_completed(
        self,
        args: CarePlanActivitiesCompletedArgs,
    ) -> List[CarePlanActivityCompletedItem]:
        log.info("ActivitiesCompletedLookup", context=args)
        items: List[CarePlanActivityCompletedItem] = []
        content = self._get_content_viewed(args)
        items.extend(content)
        if args.include_appointments:
            appointments = self._get_appointments_completed(args)
            items.extend(appointments)
        return items

    def _get_content_viewed(
        self,
        args: CarePlanActivitiesCompletedArgs,
    ) -> List[CarePlanContentCompletedItem]:
        next_day = args.end_date + timedelta(days=1)
        resource_interactions: List[ResourceInteraction] = (
            db.session.query(ResourceInteraction)
            .filter(ResourceInteraction.resource_viewed_at >= args.start_date)
            .filter(ResourceInteraction.resource_viewed_at < next_day)
            .filter(ResourceInteraction.user_id.in_(args.member_ids))
            .all()
        )
        # CPS is able to match activities on either slugs or resource-ids,
        # so skipping resource-id lookup (as that would require a Resource table lookup)
        result = [
            CarePlanActivityUtil.to_content_completed_item(ri)
            for ri in resource_interactions
        ]
        return result

    def _get_appointments_completed(
        self,
        args: CarePlanActivitiesCompletedArgs,
    ) -> List[CarePlanAppointmentCompletedItem]:
        next_day = args.end_date + timedelta(days=1)

        schedules = (
            db.session.query(Schedule)
            .filter(Schedule.user_id.in_(args.member_ids))
            .all()
        )
        if not schedules:
            return []
        schedule_ids = [o.id for o in schedules]
        appointments = (
            db.session.query(Appointment)
            .options(joinedload(Appointment.product))
            .filter(Appointment.cancelled_at == None)
            .filter(Appointment.member_schedule_id.in_(schedule_ids))
            .filter(Appointment.scheduled_end >= args.start_date)
            .filter(Appointment.scheduled_end < next_day)
            .all()
        )
        result = []
        for appt in appointments:
            if CarePlanActivityUtil.is_completed(appt):
                item = CarePlanActivityUtil.to_appointment_completed_item(appt)
                result.append(item)
        return result
