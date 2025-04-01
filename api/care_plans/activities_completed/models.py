from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from care_plans.cps_models import ActivityType


@dataclass
class CarePlanActivitiesCompletedArgs:
    member_ids: List[int]
    start_date: date
    end_date: date
    include_appointments: Optional[bool] = False


@dataclass
class CarePlanActivityCompletedItem:
    member_id: int
    type: ActivityType


@dataclass
class CarePlanContentCompletedItem(CarePlanActivityCompletedItem):
    slug: str


@dataclass
class CarePlanAppointmentCompletedItem(CarePlanActivityCompletedItem):
    vertical_id: int
    appointment_purpose: str
