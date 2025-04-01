import dataclasses
import datetime
import traceback
from typing import Any, Dict, List

from dateutil.parser import parse
from flask import request
from httpproblem import Problem

from care_plans.activities_completed.lookup import ActivitiesCompletedLookup
from care_plans.activities_completed.models import CarePlanActivitiesCompletedArgs
from common.services.api import InternalServiceResource
from utils.log import logger

log = logger(__name__)


# Internal API used by CarePlanService to fetch content consumed by users
class CarePlanActivitiesCompletedResource(InternalServiceResource):
    def post(self) -> List[Dict[str, Any]]:  # List[CarePlanActivityCompletedItem]
        self._check_permissions()
        args = self.parse_input()
        items = ActivitiesCompletedLookup().get_activities_completed(args)
        # dataclasses don't serialize to json automatically
        return [dataclasses.asdict(i) for i in items]

    def parse_input(self) -> CarePlanActivitiesCompletedArgs:
        request_json = request.json if request.is_json else None
        try:
            args = CarePlanActivitiesCompletedArgs(**request_json)
            if not isinstance(args.start_date, datetime.date):
                args.start_date = parse(str(args.start_date)).date()
            if not isinstance(args.end_date, datetime.date):
                args.end_date = parse(str(args.end_date)).date()
        except Exception:
            log.error(
                "Unable to parse input",
                request_json=request_json,
                error=traceback.format_exc(),
            )
            raise Problem(400, "Unable to parse Input")
        if not args.member_ids:
            log.error("Input is empty")
            raise Problem(400, "Empty Ids")
        count = len(args.member_ids)
        if count > 1000:
            log.error(
                "Input contains too many member-ids.  Max 1000",
                member_count=count,
            )
            raise Problem(400, "Too Many Ids")
        if args.start_date > args.end_date:
            log.error(
                "Date-From greater than Date-To",
                context=args,
            )
            raise Problem(400, "Invalid Dates")
        return args
