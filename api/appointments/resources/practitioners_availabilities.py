import datetime
from typing import Any, Dict, List

from ddtrace import tracer
from flask import request
from flask_restful import abort
from marshmallow import ValidationError

from appointments.schemas.practitioners_availabilities import (
    PractitionerDatesAvailablePostSchema,
    PractitionerDatesAvailableSchema,
)
from appointments.schemas.practitioners_availabilities_v3 import (
    PractitionersAvailabilitiesPostSchemaV3,
    PractitionersAvailabilitiesSchemaV3,
)
from appointments.utils.booking import MassAvailabilityCalculator
from authn.models.user import User
from common.services.api import AuthenticatedResource
from models.profiles import PractitionerProfile
from providers.service.provider import ProviderService
from utils.log import logger

log = logger(__name__)

MAX_DATE_RANGE = 30
DATES_AVAILABLE_PERF_FLAG = "dates_available_perf"


def _get_common_availability_args(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    request_args: Dict[str, Any], user: User, date_delta: int = 7
):
    """
    Extract common arguments for practitioner availability requests
    """
    time_now = datetime.datetime.utcnow()

    start_time = request_args.get("start_time")
    if start_time:
        start_time = start_time.replace(tzinfo=None)

    if not start_time or start_time < time_now:
        start_time = time_now

    end_time = request_args.get("end_time") or start_time + datetime.timedelta(
        days=date_delta
    )
    end_time = end_time.replace(tzinfo=None)

    vertical_name = request_args.get("provider_type")
    practitioner_ids = request_args.get("practitioner_ids")

    can_prescribe = bool(request_args.get("can_prescribe"))

    # provider steerage sorts by contract priority and then first available within the timeframe
    # this is a temporary arg so web can sort by provider steerage before it's released on mobile
    provider_steerage_sort = request_args.get("provider_steerage_sort")

    practitioner_profiles = ProviderService().list_available_practitioners_query(
        user, practitioner_ids, can_prescribe, provider_steerage_sort
    )

    return (
        start_time,
        end_time,
        vertical_name,
        practitioner_profiles,
        provider_steerage_sort,
    )


def _get_practitioner_contract_priorities(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    practitioner_profiles: List[PractitionerProfile],
):
    practitioner_ids = [pp.user_id for pp in practitioner_profiles]
    practitioner_contract_priorities = ProviderService().get_contract_priorities(
        practitioner_ids
    )
    practitioner_contracts_dict = {}
    for p in practitioner_contract_priorities:
        practitioner_contracts_dict[p.practitioner_id] = p.contract_priority
    return practitioner_contracts_dict


class PractitionersAvailabilitiesResource(AuthenticatedResource):
    @tracer.wrap()
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Retrieve the availabilities for practitioners from the request body.
        """
        self.timer("start_time")

        request_json = request.json if request.is_json else None
        try:
            args = PractitionersAvailabilitiesPostSchemaV3().load(request_json)
        except ValidationError as e:
            abort(400, message=e.messages)

        self.timer("read_args_time")
        (
            start_time,
            end_time,
            vertical_name,
            practitioner_profiles,
            provider_steerage_sort,
        ) = _get_common_availability_args(
            request_args=args, user=self.user, date_delta=7
        )
        self.timer("load_args_time")

        contract_priority_by_practitioner_id = None
        if provider_steerage_sort:
            contract_priority_by_practitioner_id = (
                _get_practitioner_contract_priorities(practitioner_profiles)
            )

        offset = args["offset"]
        limit = args["limit"]

        window_length_hrs = round((end_time - start_time).total_seconds() / (60 * 60))
        log.info(
            "POST PractitionersAvailabilitiesResource: Fetching availability for practitioners",
            n_practitioners=len(practitioner_profiles),
            start_time=str(start_time),
            end_time=str(end_time),
            window_length_hrs=window_length_hrs,
            vertical_name=vertical_name,
            offset=offset,
            limit=limit,
        )

        pagination = {
            "offset": offset,
            "limit": limit,
        }

        data = {"data": [], "pagination": pagination}

        availabilities = MassAvailabilityCalculator().get_practitioner_availabilities(
            practitioner_profiles=practitioner_profiles,
            start_time=start_time,
            end_time=end_time,
            member=self.user,
            limit=limit,
            offset=offset,
            vertical_name=vertical_name,
            contract_priority_by_practitioner_id=contract_priority_by_practitioner_id,
        )
        self.timer("get_availabilities_time")

        # sort first on contract_priority (prioritizing fixed cost providers), then sort based on availability returned
        # for the time period (pushing practitioners with no availability to the end of the list)
        if provider_steerage_sort:
            availabilities.sort(
                key=lambda t: (
                    t.contract_priority,
                    t.availabilities[0].scheduled_start
                    if t.availabilities
                    else datetime.datetime.max,
                )
            )

        data["data"] = [
            {
                "practitioner_id": a.practitioner_id,
                "duration": a.duration,
                "product_id": a.product_id,
                "product_price": a.product_price,
                "total_available_credits": a.availabilities[0].total_available_credits
                if len(a.availabilities)
                else 0,
                "availabilities": [
                    {
                        "start_time": avail.scheduled_start,
                        "end_time": avail.scheduled_end,
                    }
                    for avail in a.availabilities
                ],
            }
            for a in availabilities
        ]
        self.timer("init_data_time")
        schema = PractitionersAvailabilitiesSchemaV3()
        resp = schema.dump(data)  # type: ignore[attr-defined] # "object" has no attribute "dump"
        self.timer("schema_time")
        return resp


class PractitionerDatesAvailableResource(AuthenticatedResource):
    @tracer.wrap()
    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Identifies the dates with any open appointments for provided practitioners in a given time frame
        """
        request_json = request.json if request.is_json else None
        args = PractitionerDatesAvailablePostSchema().load(request_json).data

        (
            start_time,
            end_time,
            vertical_name,
            practitioner_profiles,
            provider_steerage_sort,
        ) = _get_common_availability_args(
            request_args=args, user=self.user, date_delta=29
        )

        log.info(
            "POST PractitionerDatesAvailableResource: Fetching availability",
            n_practitioners=len(practitioner_profiles),
            start_time=start_time,
            end_time=end_time,
            vertical_name=vertical_name,
        )

        member_timezone = args.get("member_timezone")
        if member_timezone is None:
            abort(400, error="Invalid timezone request")

        date_range = (end_time - start_time).days
        if date_range > MAX_DATE_RANGE:
            abort(400, error="Requested date range exceeds limit")

        availabilities = MassAvailabilityCalculator().get_practitioner_available_dates(
            practitioner_profiles=practitioner_profiles,
            start_time=start_time,
            end_time=end_time,
            member=self.user,
            vertical_name=vertical_name,
            member_timezone=member_timezone,
        )

        response_data = {"data": availabilities}

        # below is only for logging purpose
        practitioner_ids = args.get("practitioner_ids")
        can_prescribe = bool(args.get("can_prescribe"))
        log.info(
            "Practitioner dates availability result",
            n_practitioners=len(practitioner_profiles),
            start_time=start_time,
            end_time=end_time,
            vertical_name=vertical_name,
            user_id=self.user.id,
            practitioner_ids=practitioner_ids,
            availabilities=availabilities,
        )

        from appointments.tasks.availability import (
            log_practitioner_future_days_availability,
        )

        log_practitioner_future_days_availability.delay(
            user_id=self.user.id,
            practitioner_ids=practitioner_ids,
            can_prescribe=can_prescribe,
            start_time=start_time,
            end_time=end_time,
            vertical_name=vertical_name,
            provider_steerage_sort=provider_steerage_sort,
        )
        # logging end

        return PractitionerDatesAvailableSchema().dump(response_data).data
