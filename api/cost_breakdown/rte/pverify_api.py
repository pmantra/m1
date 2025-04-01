from __future__ import annotations

import dataclasses
import decimal
import json
import re
import time
import traceback
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Optional

from requests import HTTPError, Response, Timeout

from common import stats
from common.base_http_client import AccessTokenMixin, BaseHttpClient
from cost_breakdown.constants import (
    COST_SHARING_CATEGORY_TO_PVERIFY_MAPPINGS,
    ELIGIBILITY_SUMMARY_ENDPOINT_NAME,
    MAVEN_PROVIDER_LASTNAME,
    MAVEN_PROVIDER_NPI,
    PVERIFY_CLIENT_API_ID,
    PVERIFY_CLIENT_API_SECRET,
    PVERIFY_HBPC_SUMMARY_TO_ELGIBILITY_INFO,
    PVERIFY_RESPONSE_KEY_SUBSET,
    PVERIFY_URL,
    TIER2_ELIGIBILITY_MAP,
    TOKEN_ENDPOINT_NAME,
    PverifyKeys,
    Tier2PverifyKeys,
)
from cost_breakdown.errors import (
    NoPatientNameFoundError,
    NoRTEPayerFound,
    PverifyEligibilityInfoParsingError,
    PverifyHttpCallError,
    PverifyPlanInactiveError,
    PverifyProcessFailedError,
)
from cost_breakdown.models.rte import EligibilityInfo, RTETransaction
from payer_accumulator.models.payer_list import Payer
from storage.connection import db
from utils.log import logger
from wallet.models.constants import CostSharingCategory
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)

CONTENT_TYPE = "application/json"
METRIC_PREFIX = "api.cost_breakdown.rte.pverify_api"


def get_pverify_key(
    cost_sharing_category: CostSharingCategory, pverify_key: str
) -> Optional[str]:
    try:
        category_mappings = COST_SHARING_CATEGORY_TO_PVERIFY_MAPPINGS[
            cost_sharing_category
        ]
        pverify_code = category_mappings[pverify_key].value
        return pverify_code
    except KeyError as e:
        log.error("Could not retrieve practice code mapping" f" Error: {e}")
        return None


class PverifyAPI(AccessTokenMixin, BaseHttpClient):
    """
    This class is responsible for calling the Pverify API.
    """

    def __init__(self) -> None:
        super().__init__(
            base_url=PVERIFY_URL,
            service_name="pVerify",
            content_type=CONTENT_TYPE,
            log=log,
            metric_prefix=METRIC_PREFIX,
            metric_pod_name=stats.PodNames.PAYMENTS_PLATFORM,
        )

    def _create_access_token(self) -> tuple[str | None, int | None]:
        """
        Called by AccessTokenMixin to request the new token
        """
        access_token: str | None = None
        access_token_expiration: int | None = None

        data = (
            "grant_type=client_credentials"
            f"&Client_Id={PVERIFY_CLIENT_API_ID}"
            f"&Client_Secret={PVERIFY_CLIENT_API_SECRET}"
        )

        response = self.make_request(
            url=TOKEN_ENDPOINT_NAME,
            data=data,
            extra_headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
            timeout=30,
            metric_suffix="create_access_token",
        )

        if response.ok:
            access_token = str(response.json()["access_token"])
            expires_in = int(response.json()["expires_in"])
            access_token_expiration = int(time.time()) + expires_in

        return access_token, access_token_expiration

    def make_api_request(
        self,
        url: str,
        data: Any = None,
        params: dict[str, Any] | None = None,
        method: Literal["GET", "PUT", "POST", "DELETE", "PATCH"] = "GET",
        timeout: Optional[int] = None,
        retry_on_error: bool = True,
    ) -> Response:
        """
        Wraps BaseHttpClient.make_request to provide additional logic and logging
        """
        self.get_access_token()

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Client-API-Id": PVERIFY_CLIENT_API_ID or "",
        }

        return self.make_request(
            url=url,
            data=json.dumps(data) or {},
            params=params,
            extra_headers=headers,
            method=method,
            timeout=timeout,
            retry_on_error=retry_on_error,
            metric_suffix="make_api_request",
        )

    def _should_retry_on_error(self, error: Exception) -> bool:
        # retry for auth or timeout errors
        if isinstance(error, HTTPError) and error.response.status_code == 401:
            self.create_access_token()
            return True
        if isinstance(error, Timeout):
            return True

        return False

    def _retry_make_request(self, **kwargs: Any) -> Response:
        # Overwrite auth header with the new token created in _should_retry_on_error
        retry_args = kwargs
        retry_args["extra_headers"]["Authorization"] = f"Bearer {self.access_token}"
        return super()._retry_make_request(**retry_args)

    def get_real_time_eligibility_data(
        self,
        plan: MemberHealthPlan,
        cost_sharing_category: CostSharingCategory,
        service_start_date: Optional[date],
        member_first_name: Optional[str] = None,
        member_last_name: Optional[str] = None,
        is_second_tier: bool = False,
        treatment_procedure_id: Optional[int] = None,
        reimbursement_request_id: Optional[int] = None,
    ) -> RTETransaction:
        """
        Send EligibilitySummary post request to Pverify to get member real time medical plan eligibility information.
        """
        # These values should be passed from treatment procedure/reimbursement request
        # default to past logic, sending today's date if they're null
        if service_start_date is None:
            service_start_date = date.today()

        body = self._get_eligibility_summary_request_body(
            plan=plan,
            cost_sharing_category=cost_sharing_category,
            service_start_date=service_start_date,
            member_first_name=member_first_name,  # type: ignore[arg-type] # Argument "member_first_name" to "get_eligibility_summary_request_body" has incompatible type "Optional[str]"; expected "str"
            member_last_name=member_last_name,  # type: ignore[arg-type] # Argument "member_last_name" to "get_eligibility_summary_request_body" has incompatible type "Optional[str]"; expected "str"
        )

        response = self.make_api_request(
            url=ELIGIBILITY_SUMMARY_ENDPOINT_NAME,
            data=body,
            method="POST",
            timeout=30,
            retry_on_error=True,
        )
        rte_transaction = self._handle_eligibility_summary_response(
            plan=plan,
            request=body,
            response=response,  # type: ignore[arg-type] # Argument "response" to "_handle_eligibility_summary_response" of "PverifyAPI" has incompatible type "Optional[Response]"; expected "Response"
            cost_sharing_category=cost_sharing_category,
            is_second_tier=is_second_tier,
            treatment_procedure_id=treatment_procedure_id,
            reimbursement_request_id=reimbursement_request_id,
        )
        self._increment_metric(
            successful=True, metric_suffix="get_real_time_eligibility_data"
        )
        return rte_transaction

    def _get_eligibility_summary_request_body(
        self,
        plan: MemberHealthPlan,
        cost_sharing_category: CostSharingCategory,
        member_first_name: str,
        member_last_name: str,
        service_start_date: date,
    ) -> dict:
        if not member_last_name or not member_first_name:
            # Log used in alerting
            log.error(
                "RTE pverify error: Missing patient name for pverify request for health plan.",
                member_health_plan_id=plan.id,
            )
            self._increment_metric(
                successful=False,
                metric_suffix="get_eligibility_summary_request_body",
                reason="bad_patient_name",
            )
            raise NoPatientNameFoundError(
                f"Missing patient name for pverify request for health plan {plan.id}"
            )
        payer = Payer.query.filter(
            Payer.id == plan.employer_health_plan.benefits_payer_id
        ).one_or_none()
        if not payer:
            raise NoRTEPayerFound(
                f"No rte payer found for benefit payer id {plan.employer_health_plan.benefits_payer_id}"
            )
        body = {
            "payerCode": payer.payer_code,
            "provider": {
                "lastName": MAVEN_PROVIDER_LASTNAME,
                "npi": MAVEN_PROVIDER_NPI,
            },
            "doS_StartDate": service_start_date.strftime("%m/%d/%Y"),
            # The end date sent here must be equal to the start date because pverify favors end dates over start dates,
            # while we want to calculate rte based on the start date, not end date.
            "doS_EndDate": service_start_date.strftime("%m/%d/%Y"),
            # We always set this flag to True, see more context: https://mavenclinic.atlassian.net/browse/PAY-6321
            "isSubscriberPatient": "True",
        }
        pverify_practice_code = get_pverify_key(
            cost_sharing_category=cost_sharing_category, pverify_key="PRACTICE_CODE"
        )
        if pverify_practice_code:
            body["PracticeTypeCode"] = pverify_practice_code

        subscriber_info: dict = {
            "memberID": plan.subscriber_insurance_id,
            "firstName": member_first_name,
            "lastName": member_last_name,
        }
        if plan.is_subscriber:
            subscriber_info["dob"] = plan.subscriber_date_of_birth.strftime("%m/%d/%Y")  # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "strftime"
        else:
            subscriber_info["dob"] = plan.patient_date_of_birth.strftime("%m/%d/%Y")  # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "strftime"
        body["subscriber"] = subscriber_info
        return body

    def _handle_eligibility_summary_response(
        self,
        plan: MemberHealthPlan,
        request: dict,
        response: Response,
        cost_sharing_category: CostSharingCategory,
        is_second_tier: bool = False,
        treatment_procedure_id: Optional[int] = None,
        reimbursement_request_id: Optional[int] = None,
    ) -> RTETransaction:
        if treatment_procedure_id is not None:
            trigger_source = f"treatment procedure id: {treatment_procedure_id}"
        elif reimbursement_request_id is not None:
            trigger_source = f"reimbursement request id: {reimbursement_request_id}"
        else:
            trigger_source = ""

        # handle failure cases
        if not response.ok:
            log.error(
                "RTE request fails.",
                reimbursement_wallet_id=str(plan.reimbursement_wallet_id),
                member_health_plan_id=plan.id,
                status_code=response.status_code,
            )
            try:
                # handle non-json error messages
                error = str(response.json())  # save json as a string
            except Exception:  # noqa Too broad exception but I don't want to silence error messages
                error = str(response.content)
            row = RTETransaction(
                member_health_plan_id=plan.id,
                response_code=response.status_code,
                request=request,
                error_message=error,
                trigger_source=trigger_source,
            )
            db.session.add(row)
            db.session.commit()
            self._increment_metric(
                successful=False,
                metric_suffix="handle_eligibility_summary_response",
                reason="pverify_call_failed",
            )
            raise PverifyHttpCallError(
                message=f"Failed to call pverify api for rte transaction {row.id}",
                http_status=response.status_code,
            )

        result = {
            k: v for k, v in response.json().items() if k in PVERIFY_RESPONSE_KEY_SUBSET
        }
        if (
            result["APIResponseCode"] != "0"
            or result[PverifyKeys.API_RESPONSE_MESSAGE.value] != "Processed"
        ):
            log.error(
                "RTE process failed.",
                reimbursement_wallet_id=str(plan.reimbursement_wallet_id),
                member_health_plan_id=plan.id,
            )
            row = RTETransaction(
                member_health_plan_id=plan.id,
                response_code=response.status_code,
                request=request,
                error_message=result[PverifyKeys.API_RESPONSE_MESSAGE.value],
                trigger_source=trigger_source,
            )
            db.session.add(row)
            db.session.commit()
            self._increment_metric(
                successful=False,
                metric_suffix="handle_eligibility_summary_response",
                reason="rte_process_failed",
            )
            raise PverifyProcessFailedError(
                message=f"Pverify returns unprocessed result back, check error message in rte transaction {row.id}",
                error=row.error_message
                if row.error_message
                else "Pverify has returned an unexpected result.",
                rte_transaction=row,
            )

        if result[PverifyKeys.PLAN_COVERAGE_SUMMARY.value].get("Status") != "Active":
            log.error(
                "RTE plan is inactive.",
                reimbursement_wallet_id=str(plan.reimbursement_wallet_id),
                member_health_plan_id=plan.id,
                plan_status=result[PverifyKeys.PLAN_COVERAGE_SUMMARY.value].get(
                    "Status"
                ),
            )
            row = RTETransaction(
                member_health_plan_id=plan.id,
                response_code=response.status_code,
                request=request,
                plan_active_status=False,
                trigger_source=trigger_source,
            )
            db.session.add(row)
            db.session.commit()
            self._increment_metric(
                successful=False,
                metric_suffix="handle_eligibility_summary_response",
                reason="inactive_plan",
            )
            raise PverifyPlanInactiveError(
                message=f"Pverify returned plan is inactive for rte transaction {row.id}",
                plan=plan,
            )

        # try to populate eligibility info in successful cases
        try:
            if is_second_tier:
                eligibility_info = self._tier2_populate_eligibility_info(
                    response=response
                )
            else:
                eligibility_info = self._populate_eligibility_info(
                    result=result, cost_sharing_category=cost_sharing_category
                )
            row = RTETransaction(
                member_health_plan_id=plan.id,
                response_code=response.status_code,
                request=request,
                response=dataclasses.asdict(eligibility_info),
                plan_active_status=True,
                trigger_source=trigger_source,
            )
            db.session.add(row)
            db.session.commit()
            self._increment_metric(
                successful=True, metric_suffix="handle_eligibility_summary_response"
            )
            return row
        except Exception as e:
            log.error(
                f"Error populating eligibility info from Pverify response: {e}",
                reimbursement_wallet_id=str(plan.reimbursement_wallet_id),
                member_health_plan_id=plan.id,
                is_second_tier=is_second_tier,
                reason=traceback.format_exc(),
            )
            raise PverifyEligibilityInfoParsingError(
                f"Error parsing eligibility info from Pverify response: {e}"
            )

    def _populate_eligibility_info(
        self,
        result: dict,
        cost_sharing_category: CostSharingCategory,
    ) -> EligibilityInfo:
        # handle success case
        hbpc_deductible_oop_summary = result[PverifyKeys.DEDUCTIBLE_OOP_SUMMARY.value]

        eligibility_info = EligibilityInfo()

        # get deductible and oop
        for (
            pverify_key,
            eligibility_key,
        ) in PVERIFY_HBPC_SUMMARY_TO_ELGIBILITY_INFO.items():
            if hbpc_deductible_oop_summary.get(pverify_key):
                value = hbpc_deductible_oop_summary[pverify_key].get("Value")
                if value:
                    setattr(
                        eligibility_info,
                        eligibility_key,
                        int(Decimal(value.strip("$")) * 100),
                    )
        # get coinsurance & copay
        if cost_sharing_category:
            summary_object_key = get_pverify_key(
                cost_sharing_category=cost_sharing_category,
                pverify_key="SUMMARY_OBJECT",
            )
            office_summary = result.get(summary_object_key, {})

            coinsurance, copay = office_summary.get("CoInsInNet"), office_summary.get(
                "CoPayInNet"
            )
            if coinsurance:
                eligibility_info.coinsurance = (
                    float(coinsurance.get("Value").strip().strip("%"))  # type: ignore[assignment] # Incompatible types in assignment (expression has type "float", variable has type "Optional[Decimal]")
                    / 100.0
                )
            if copay:
                eligibility_info.copay = int(float(copay.get("Value").strip("$")) * 100)

        # get hra remaining amount
        if result[PverifyKeys.ADDITIONAL_INFO.value] is not None:
            match = re.search(
                r"HRA.*?\b(\d+(\.\d+)?)\b",
                result[PverifyKeys.ADDITIONAL_INFO.value],
                re.IGNORECASE,
            )
            if match:
                hra_remaining = int(decimal.Decimal(match.group(1)) * 100)
                eligibility_info.hra_remaining = hra_remaining
        return eligibility_info

    def _tier2_populate_eligibility_info(
        self,
        response: Response,
    ) -> EligibilityInfo:
        eligibility_info = EligibilityInfo()
        service_details_obj = response.json()["ServiceDetails"]
        for details in service_details_obj:
            if details["ServiceName"] == "Chiropractic":
                eligibility_detail = details["EligibilityDetails"]
                for detail in eligibility_detail:
                    if (
                        detail["Message"]
                        and "tier 2" in detail["Message"][0].lower()
                        and detail["PlaceOfService"] == "Office"
                        and detail["EligibilityOrBenefit"]
                        in (
                            Tier2PverifyKeys.DEDUCTIBLE.value,
                            Tier2PverifyKeys.OUT_OF_POCKET.value,
                        )
                    ):
                        eligibility_key = TIER2_ELIGIBILITY_MAP[
                            detail["CoverageLevel"]
                        ][detail["EligibilityOrBenefit"]][detail["TimePeriodQualifier"]]
                        amount = detail["MonetaryAmount"]
                        if not getattr(eligibility_info, eligibility_key):
                            setattr(
                                eligibility_info,
                                eligibility_key,
                                int(Decimal(amount.strip().strip("$")) * 100),
                            )
                break
        return eligibility_info
