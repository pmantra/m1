import dataclasses
from datetime import date
from typing import Any, Dict, List, Optional

import ddtrace
from flask import Response, make_response, request
from flask_restful import abort
from marshmallow import ValidationError
from werkzeug.exceptions import BadRequest

from common.services.api import PermissionedCareTeamResource
from health.data_models.member_risk_flag import MemberRiskFlag
from health.data_models.risk_flag import RiskFlag
from health.models.risk_enums import RiskFlagName
from health.schema.risk_flags import (
    MemberRiskFlagsPostRequestV3,
    MemberRiskFlagsPostResponseV3,
)
from health.services.member_risk_service import MemberRiskService, SetRiskResult
from utils.log import logger

log = logger(__name__)


@dataclasses.dataclass
class MemberRiskGetItem:
    # MemberRiskFlag fields
    value: Optional[int]
    start: Optional[str]  # iso formatted date 'YYYY-MM-DD' or null
    end: Optional[str]  # iso formatted date 'YYYY-MM-DD' or null

    # RiskFlag fields
    name: str
    severity: str  # RiskFlagSeverity
    is_mental_health: bool
    is_chronic_condition: bool  # deprecated used is_physical_health instead
    is_physical_health: bool
    is_utilization: bool
    is_situational: bool
    relevant_to_maternity: bool
    relevant_to_fertility: bool
    uses_value: bool
    value_unit: str

    # Care Plan Specific Fields
    ecp_qualifier_type: Optional[str] = None  # ECPQualifierType

    # Display Specific Fields
    is_ttc_and_treatment: bool = False
    display_name: str = ""
    display_context: str = ""


class MemberRiskResource(PermissionedCareTeamResource):
    def get(self, user_id: int) -> List[Dict[str, Any]]:  # List[MemberRiskGetItem]
        target_user = self.target_user(user_id)
        active_only = (
            request.args.get("active_only", default="true", type=str).lower() == "true"
        )
        track_relevant_only: bool = (
            request.args.get("track_relevant_only", default="true", type=str).lower()
            == "true"
        )

        service = MemberRiskService(target_user.id)
        member_risks = service.get_member_risks(active_only, track_relevant_only)
        items = [self._to_response_item(mr) for mr in member_risks]
        return [dataclasses.asdict(i) for i in items]

    @ddtrace.tracer.wrap()
    def post(self, user_id: int) -> Response:
        """
        Handle POST requests to create or update a risk flag for a specific user.

        This endpoint allows clients to create, end, or confirm a risk flag for a given user
        based on the provided `risk_flag_name` in the request payload. The response includes
        the status of the operation (created, ended, or confirmed) along with an appropriate
        HTTP status code.

        Args:
            user_id (int): The ID of the target user for whom the risk flag is being managed.

        Raises:
            ValidationError: If the request payload fails schema validation.
            Exception: For any unexpected server-side error, a 500 status code is returned.

        Returns:
            Response: A Flask response object containing the serialized result and HTTP status code.
            Return the serialized response with the appropriate HTTP status code:
                - 201: If the risk flag was created or ended.
                - 200: If the risk flag was confirmed.
        """

        target_user = self.target_user(user_id)
        try:
            # Validate the request input
            schema = MemberRiskFlagsPostRequestV3()
            request_json = request.json if request.is_json else None
            args = schema.load(request_json)

            # Process the risk flag
            risk_flag_name = args["risk_flag_name"]
            self._validate_risk_flag_name(risk_flag_name)
            modified_reason = args.get("modified_reason")
            service = MemberRiskService(
                user=target_user.id, modified_reason=modified_reason
            )
            result: SetRiskResult = service.set_risk(name=risk_flag_name)

            # Generate response data
            response_data = self._create_post_response(
                risk_flag_name=risk_flag_name, result=result
            )
            response_schema = MemberRiskFlagsPostResponseV3()
            serialized_response = response_schema.dump(response_data)

            status_code = 201 if result.created_risk or result.ended_risk else 200
            return make_response(serialized_response, status_code)
        except ValidationError:
            return abort(400, message="Invalid request, failed validation")
        except BadRequest as e:
            return abort(400, message=str(e))
        except Exception as e:
            return abort(500, message=str(e))

    def _validate_risk_flag_name(self, risk_flag_name: str) -> None:
        log.info(f"Validating risk_flag_name: {risk_flag_name}")
        log.info(f"Available risk flags: {RiskFlagName._value2member_map_.keys()}")
        if not risk_flag_name or risk_flag_name not in RiskFlagName._value2member_map_:
            raise BadRequest(description="Invalid risk flag name.")

    def _create_post_response(
        self, risk_flag_name: str, result: SetRiskResult
    ) -> Dict[str, Any]:
        """Generate the response dictionary based on the service result."""
        response = {
            "risk_flag_name": risk_flag_name,
            "created_risk": result.created_risk is not None,
            "ended_risk": result.ended_risk is not None,
            "confirmed_risk": result.confirmed_risk is not None,
        }
        return response

    def _to_response_item(self, member_risk: MemberRiskFlag) -> MemberRiskGetItem:
        risk: RiskFlag = member_risk.risk_flag
        item = MemberRiskGetItem(
            # Member Risk Fields
            value=member_risk.value,
            start=self._isoformat(member_risk.start),
            end=self._isoformat(member_risk.end),
            # Risk Fields
            name=risk.name,
            severity=risk.severity.value,  # type: ignore
            is_mental_health=risk.is_mental_health,
            is_chronic_condition=risk.is_chronic_condition,
            is_physical_health=risk.is_physical_health,
            is_utilization=risk.is_utilization,
            is_situational=risk.is_situational,
            relevant_to_maternity=risk.relevant_to_maternity,
            relevant_to_fertility=risk.relevant_to_fertility,
            uses_value=risk.uses_value,
            value_unit=risk.value_unit or "",
            is_ttc_and_treatment=risk.is_ttc_and_treatment,
        )
        if risk.ecp_qualifier_type:
            item.ecp_qualifier_type = risk.ecp_qualifier_type.value  # type:ignore
        item.display_name = risk.name
        if risk.uses_value:
            # currently there is no overlap between Risk name containing a dash and Risks using value
            # todo Design calls for risk-specific text - e.g. "7 months( 5 months remaining based on age/risk)"
            # todo: convert value_unit to singular when value is 1
            item.display_context = f"{item.value} {item.value_unit}"  # e.g. "7 months"
        elif " - " in risk.name:
            item.display_name = risk.name.split(" - ")[0]
            item.display_context = risk.name.split(" - ")[1]

        return item

    def _isoformat(self, date: Optional[date]) -> Optional[str]:
        if date is None:
            return None
        return date.isoformat()
