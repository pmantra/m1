from dataclasses import asdict
from typing import Optional

from ddtrace import tracer

from appointments.models.appointment import Appointment
from authn.models.user import User
from care_plans.cps_models import ActivityAutoCompleteArgs, ActivityType
from care_plans.cps_request import CarePlanServiceRequest
from care_plans.cps_threadpool import run_async_in_threadpool
from common import stats
from models.marketing import Resource, ResourceContentTypes
from utils.log import logger

log = logger(__name__)


class CarePlansService:
    @staticmethod
    @tracer.wrap()
    def send_content_completed(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        resource: Resource, user: Optional[User], caller: str = "mono"
    ):
        if not user:
            return
        if not user.member_profile:
            return
        if not user.member_profile.has_care_plan:
            return

        if resource.content_type == ResourceContentTypes.on_demand_class.name:
            type = ActivityType.WATCH
        else:
            type = ActivityType.READ
        args = ActivityAutoCompleteArgs(
            type=type, caller=caller, resource_id=resource.id, slug=resource.slug
        )
        CarePlansService.send_activity_occurred(
            user.id,
            args,
        )

    @staticmethod
    @tracer.wrap()
    def send_appointment_completed(appointment: Appointment, caller: str = "mono"):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Calls CPS' activity-occurred endpoint with a 'meet' event when:
            - appointment is completed
            - member has care plan
        """
        user = appointment.member
        if not user.member_profile.has_care_plan:
            return
        args = ActivityAutoCompleteArgs(
            type=ActivityType.MEET,
            caller=caller,
            vertical_id=appointment.product.vertical_id,
            appointment_purpose=appointment.purpose,
        )
        CarePlansService.send_activity_occurred(
            user.id,
            args,
        )

    @staticmethod
    def send_activity_occurred(member_id: int, args: ActivityAutoCompleteArgs):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        run_async_in_threadpool(
            CarePlansService._send_activity_occurred, member_id, args
        )

    @staticmethod
    def _send_activity_occurred(member_id: int, args: ActivityAutoCompleteArgs):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        success = False
        try:
            data = asdict(args)
            CarePlanServiceRequest.post(
                member_id,
                "v1/care-plans/activity-occurred",
                data,
            )

            success = True
            log.info(
                "CPS AutoComplete request succeeded",
                context={
                    "user_id": member_id,
                    "args": args,
                    "data": data,
                },
            )
        except Exception as e:
            # error log should be same format as HDC's cps_client
            # there are monitors on the exact string message
            log.error(
                "CarePlan auto-complete request failed",
                error={"type": type(e).__name__, "message": str(e)},
                context={
                    "user_id": member_id,
                    "args": args,
                    "data": data,
                },
            )
            raise e
        finally:
            stats.increment(
                metric_name="care_plan.auto_complete_activity.sent",
                pod_name=stats.PodNames.CARE_MANAGEMENT,
                tags=[
                    f"success:{success}",
                    f"caller:{args.caller}",
                    f"type:{args.type}",
                ],
            )

    @staticmethod
    @tracer.wrap()
    def send_gdpr_member_delete(member_id: int, timeout_in_sec: Optional[int] = None):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            data = {"member_id": member_id}
            CarePlanServiceRequest.post(
                None,
                "v1/-/gdpr/member-delete",
                data,
                timeout_in_sec,
            )
        except Exception as e:
            # error log should be same format as HDC's cps_client
            # there are monitors on the exact string message
            log.error(
                "CarePlan GDPR-Member-Delete request failed",
                error={"type": type(e).__name__, "message": str(e)},
                context={
                    "user_id": member_id,
                },
            )
