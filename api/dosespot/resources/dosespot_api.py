from __future__ import annotations

import asyncio
import json
import urllib
from datetime import datetime
from time import sleep
from typing import Any, Dict, List, Tuple

import aiohttp
import dateutil
import ddtrace
import requests

from common import stats
from dosespot.constants import (
    DOSESPOT_API_URL_V2,
    DOSESPOT_SSO_URL,
    DOSESPOT_SUBSCRIPTION_KEY,
    MAX_RETRIES,
    RETRY_DELAY,
    DoseSpotActionTypes,
)
from dosespot.models.common import Pagination
from dosespot.services.dosespot_auth import DoseSpotAuth
from dosespot.services.dosespot_service import (
    create_dosespot_patient_data,
    get_existing_patient_id,
)
from utils.log import logger

log = logger(__name__)

API_REQUEST_METRIC_NAME = "api.dosespot.api_request"


class DoseSpotAPI:
    def __init__(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self,
        clinic_id=123977,
        clinic_key="DG9UMXALAS7MNXC9MNK6EF6F96MCEF2A",
        user_id=482,
        maven_user_id=None,
        should_audit=True,
    ):
        self.clinic_key = clinic_key
        self.clinic_id = clinic_id
        self.user_id = user_id
        self.maven_user_id = maven_user_id
        if not all([self.clinic_key, self.clinic_id, self.user_id]):
            log.info(
                "Missing DoseSpot Authorization Information",
                maven_user=self.maven_user_id,
            )
        self.auth = DoseSpotAuth(self.clinic_key, self.clinic_id, self.user_id)
        self.should_audit = should_audit

    @ddtrace.tracer.wrap()
    def api_request(
        self,
        url: str,
        data: dict | None = None,
        params: dict | None = None,
        method: str = "POST",
        endpoint: str | None = None,
    ) -> Tuple:
        token = self.auth.get_token()
        if token is None:
            log.warning(
                f"DoseSpot Token retrieval failure for user {self.maven_user_id}",
                request_url=url,
            )
            stats.increment(
                metric_name=API_REQUEST_METRIC_NAME,
                pod_name=stats.PodNames.MPRACTICE_CORE,
                tags=[
                    f"endpoint:{endpoint}",
                    "result:failure",
                    "failure_reason:auth_token",
                ],
            )
            return None, None
        url = DOSESPOT_API_URL_V2 + url
        headers = {
            "Authorization": "Bearer " + token,
            "Subscription-Key": DOSESPOT_SUBSCRIPTION_KEY,
        }
        retries = 0
        while retries <= MAX_RETRIES:
            res = requests.request(
                method, url, data=data, params=params, headers=headers
            )
            if res.status_code == 200 or res.status_code == 404:
                stats.increment(
                    metric_name=API_REQUEST_METRIC_NAME,
                    pod_name=stats.PodNames.MPRACTICE_CORE,
                    tags=[
                        f"endpoint:{endpoint}",
                        "result:success",
                        f"retry_count:{retries}",
                        f"status_code:{res.status_code}",
                    ],
                )
                # return successful responses & not found responses (ex: invalid pharmacy)
                return res.status_code, self.parse_response(res.text)
            elif retries == MAX_RETRIES:
                # if we have not retrieved a useful result in MAX number of retries, log & return the error
                log.warning(
                    "DoseSpot API Error", text=res.text, status_code=res.status_code
                )
                stats.increment(
                    metric_name=API_REQUEST_METRIC_NAME,
                    pod_name=stats.PodNames.MPRACTICE_CORE,
                    tags=[
                        f"endpoint:{endpoint}",
                        "result:failure",
                        "failure_reason:max_retries",
                        f"status_code:{res.status_code}",
                    ],
                )
                return res.status_code, self.parse_response(res.text)
            else:
                # if we should retry, delay before trying again
                retries += 1
                log.info("Retrying DoseSpot API request", url=url, retry_count=retries)
                if res.status_code == 401:
                    # renew the expired auth token
                    token = self.auth.create_token()
                    headers = {
                        "Authorization": "Bearer " + token,
                        "Subscription-Key": DOSESPOT_SUBSCRIPTION_KEY,
                    }
                sleep(retries * RETRY_DELAY)
        return None, None

    @ddtrace.tracer.wrap()
    async def api_request_async(
        self,
        session: aiohttp.ClientSession,
        url: str,
        data: dict | None = None,
        params: dict | None = None,
        method: str = "POST",
        endpoint: str | None = None,
    ) -> Tuple:
        token = self.auth.get_token()
        if token is None:
            log.warning(
                f"DoseSpot Token retrieval failure for user {self.maven_user_id}",
                request_url=url,
            )
            stats.increment(
                metric_name=API_REQUEST_METRIC_NAME,
                pod_name=stats.PodNames.MPRACTICE_CORE,
                tags=[
                    f"endpoint:{endpoint}",
                    "result:failure",
                    "failure_reason:auth_token",
                ],
            )
            return None, None
        url = DOSESPOT_API_URL_V2 + url
        headers = {
            "Authorization": "Bearer " + token,
            "Subscription-Key": DOSESPOT_SUBSCRIPTION_KEY,
        }
        retries = 0
        while retries <= MAX_RETRIES:
            async with session.request(
                method=method, url=url, params=params, headers=headers, data=data
            ) as response:
                status_code = response.status
                response_text = await response.text()
                if status_code == 200 or status_code == 404:
                    stats.increment(
                        metric_name=API_REQUEST_METRIC_NAME,
                        pod_name=stats.PodNames.MPRACTICE_CORE,
                        tags=[
                            f"endpoint:{endpoint}",
                            "result:success",
                            f"retry_count:{retries}",
                            f"status_code:{status_code}",
                        ],
                    )
                    # return successful responses & not found responses (ex: invalid pharmacy)
                    return status_code, self.parse_response(response_text)
                elif retries == MAX_RETRIES:
                    # if we have not retrieved a useful result in MAX number of retries, log & return the error
                    log.warning(
                        "DoseSpot API Error",
                        text=response.text,
                        status_code=status_code,
                    )
                    stats.increment(
                        metric_name=API_REQUEST_METRIC_NAME,
                        pod_name=stats.PodNames.MPRACTICE_CORE,
                        tags=[
                            f"endpoint:{endpoint}",
                            "result:failure",
                            "failure_reason:max_retries",
                            f"status_code:{status_code}",
                        ],
                    )
                    return status_code, self.parse_response(response_text)
                else:
                    # if we should retry, delay before trying again
                    retries += 1
                    log.info(
                        "Retrying DoseSpot API request", url=url, retry_count=retries
                    )
                    if status_code == 401:
                        # renew the expired auth token
                        token = self.auth.create_token()
                        headers = {
                            "Authorization": "Bearer " + token,
                            "Subscription-Key": DOSESPOT_SUBSCRIPTION_KEY,
                        }
                    sleep(retries * RETRY_DELAY)
        return None, None

    def parse_response(self, response_text: str):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            return json.loads(response_text)
        except Exception as e:
            log.error(
                "An error occurred loading the response", text=response_text, error=e
            )

    def audit(self, action_type, status_code=None, extra=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if not self.should_audit:
            return

        audit_data = {}
        if extra:
            audit_data.update(extra)
        if status_code:
            audit_data["status_code"] = status_code

        audit_log_info = {
            "user_id": self.maven_user_id,
            "action_type": action_type,
            "action_target_type": "dosespot",
            "action_audit_data": audit_data,
        }
        log.info("audit_log_events", audit_log_info=audit_log_info)

    @ddtrace.tracer.wrap()
    def _return_SSO_url(self, patient_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        params = {
            "SingleSignOnClinicId": self.clinic_id,
            "SingleSignOnUserId": self.user_id,
            "SingleSignOnPhraseLength": 32,
            "SingleSignOnCode": self.auth.create_encrypted_clinic_key(),
            "SingleSignOnUserIdVerify": self.auth.create_encrypted_user_id(
                self.user_id
            ),
        }
        if patient_id:
            params["PatientId"] = patient_id

        encoded = urllib.parse.urlencode(params)
        url = f"{DOSESPOT_SSO_URL}?{encoded}"
        return url

    @ddtrace.tracer.wrap()
    def _generate_refill_error_url(self, patient_id, patient_info):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        params = {
            "SingleSignOnClinicId": self.clinic_id,
            "SingleSignOnUserId": self.user_id,
            "SingleSignOnPhraseLength": 32,
            "SingleSignOnCode": self.auth.create_encrypted_clinic_key(),
            "SingleSignOnUserIdVerify": self.auth.create_encrypted_user_id(
                self.user_id
            ),
        }
        params.update(patient_info)

        if patient_id and "PatientId" not in params:
            params["PatientId"] = patient_id

        encoded = urllib.parse.urlencode(params)
        url = f"{DOSESPOT_SSO_URL}?{encoded}"

        return url

    @ddtrace.tracer.wrap()
    def practitioner_refill_errors_request_url(self) -> str:
        return self._generate_refill_error_url(None, {"RefillsErrors": 1})

    @ddtrace.tracer.wrap()
    def patient_details_request(self, appointment, create_patient=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self.audit(
            DoseSpotActionTypes.get_patient_details_url,
            extra={
                "member_id": appointment.member.id,
                "appointment_id": appointment.id,
            },
        )

        existing_patient_id = get_existing_patient_id(appointment)
        if existing_patient_id:
            return (
                existing_patient_id,
                self._return_SSO_url(existing_patient_id),
            )

        if not create_patient:
            # None is a sentinel here -- causes returning a url without updating the user profile
            return None, self._return_SSO_url(None)

        status_code, data = self.api_request(
            "api/patients",
            data=create_dosespot_patient_data(appointment),
            method="POST",
            endpoint="create_patient",
        )

        if status_code == 200 and data.get("Id"):
            new_patient_id = data.get("Id")

            if new_patient_id:
                stats.increment(
                    metric_name="api.dosespot.patient_details_request",
                    pod_name=stats.PodNames.MPRACTICE_CORE,
                    tags=["success:true"],
                )

                if len(str(appointment.member.id)) > 35:
                    log.warning(
                        "Maven member id sent to associate DoseSpot patient is cut off due to field length limitations",
                        maven_member_id=appointment.member.id,
                    )
                    stats.increment(
                        metric_name="api.dosespot.patient_details_request.member_id_cutoff",
                        pod_name=stats.PodNames.MPRACTICE_CORE,
                    )

                patient_prescription_data = (
                    appointment.member.member_profile.get_prescription_info()
                )
                if patient_prescription_data.get("pharmacy_id"):
                    pharmacy_id = patient_prescription_data["pharmacy_id"]
                    self.add_patient_pharmacy(
                        appointment.member.id, new_patient_id, pharmacy_id
                    )

                return (
                    str(new_patient_id),
                    self._return_SSO_url(new_patient_id),
                )
            else:
                log.warning(
                    "DoseSpot Patient Details V2 did not find a match",
                    appointment_id=appointment.id,
                    member_id=appointment.member.id,
                    status_code=status_code,
                    message=data.get("Message"),
                    model_state=data.get("ModelState"),
                    pod_name=stats.PodNames.MPRACTICE_CORE,
                )
                stats.increment(
                    metric_name="api.dosespot.patient_details_request.non_match",
                    pod_name=stats.PodNames.MPRACTICE_CORE,
                )
                return None, None
        else:
            log.warning(
                "Problem with DoseSpot Patient Details V2",
                appointment_id=appointment.id,
                member_id=appointment.member.id,
                status_code=status_code,
            )
            stats.increment(
                metric_name="api.dosespot.patient_details_request.bad_request",
                pod_name=stats.PodNames.MPRACTICE_CORE,
                tags=[f"status_code:{status_code}"],
            )
            return None, None

    @ddtrace.tracer.wrap()
    def add_patient_pharmacy(  # type: ignore[no-untyped-def] # Function is missing a type annotation
        self, member_id, patient_id, pharmacy_id, set_as_primary=True
    ):
        self.audit(
            DoseSpotActionTypes.add_patient_pharmacy,
            extra={
                "member_id": member_id,
                "patient_id": patient_id,
                "pharmacy_id": pharmacy_id,
            },
        )
        pharmacy_status_code, pharmacy_data = self.api_request(
            f"api/patients/{patient_id}/pharmacies",
            data={"PharmacyId": pharmacy_id, "SetAsPrimary": set_as_primary},
            method="POST",
            endpoint="add_patient_pharmacy",
        )

        pharmacy_data = pharmacy_data.get("Result", {})

        if pharmacy_status_code != 200 or pharmacy_data.get("ResultCode") == "ERROR":
            log.warning(
                "DoseSpot could not add pharmacy",
                patient_id=patient_id,
                member_id=member_id,
                status_code=pharmacy_status_code,
                pharmacy_id=pharmacy_id,
                message=pharmacy_data.get("ResultDescription"),
            )

            # Mute no action item in monitor
            # Special case: User not authorized
            if (
                pharmacy_data.get("ResultDescription")
                == "User is not authorized to access this patient."
            ):
                return None

            stats.increment(
                metric_name="api.dosespot.add_patient_pharmacy.pharmacy_error",
                pod_name=stats.PodNames.MPRACTICE_CORE,
            )
            return None
        return str(pharmacy_id)

    @ddtrace.tracer.wrap()
    def get_patient_pharmacy(
        self,
        member_id: int | str,
        patient_id: int | str,
    ) -> dict | None:
        status_code, data = self.api_request(
            f"api/patients/{patient_id}/pharmacies",
            method="GET",
            endpoint="get_patient_pharmacy",
        )

        if status_code != 200 or not data:
            log.error(
                "Could not get patient pharmacy from DoseSpot",
                patient_id=patient_id,
                member_id=member_id,
                status_code=status_code,
                message=data.get("ResultDescription"),
            )
            return None

        return data["Items"][0] if len(data["Items"]) > 0 else None

    @ddtrace.tracer.wrap()
    def refills_and_transmission_counts(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        status_code, data = self.api_request(
            "api/notifications/counts", method="GET", endpoint="get_notifications_count"
        )
        self.audit(DoseSpotActionTypes.request_provider_errors, status_code, data)
        if (
            status_code == 200
            and data.get("RefillRequestsCount") is not None
            and data.get("TransactionErrorsCount") is not None
        ):
            return {
                "refill_count": data["RefillRequestsCount"],
                "transaction_count": data["TransactionErrorsCount"],
            }
        else:
            log.error(
                "Problem retrieving DoseSpot refills and error counts",
                status_code=status_code,
                result=data and data.get("Result"),
            )
            return {}

    @ddtrace.tracer.wrap()
    async def pharmacy_search(
        self, zipcode: str, pharmacy_name: str | None = None
    ) -> List:
        params = {"zip": zipcode}
        if pharmacy_name:
            params["name"] = pharmacy_name

        async with aiohttp.ClientSession() as session:
            pharmacies: List
            total_pages: int
            pharmacies, total_pages = await self.pharmacy_search_by_page_number(
                session=session, params=params, page_number=1
            )
            search_results = pharmacies
            # Limit search result to 100 items to reduce latency
            # This aligns with the v1 response, where there's no pagination and the result contains at most 100 items.
            page_limit = min(total_pages + 1, 6)
            if total_pages > 1:
                tasks = [
                    self.pharmacy_search_by_page_number(
                        session=session, params=params, page_number=page_number
                    )
                    for page_number in range(2, page_limit)
                ]
                results = await asyncio.gather(*tasks)
                for (pharmacies, _) in results:
                    search_results.extend(pharmacies)
            return search_results

    @ddtrace.tracer.wrap()
    def paginated_pharmacy_search(
        self,
        page_number: int,
        zipcode: str | None = None,
        pharmacy_name: str | None = None,
    ) -> Tuple[List, Pagination]:
        params: Dict[str, Any] = {"pageNumber": page_number}
        if zipcode:
            params["zip"] = zipcode
        if pharmacy_name:
            params["name"] = pharmacy_name

        status_code, data = self.api_request(
            url="api/pharmacies/search",
            params=params,
            method="GET",
            endpoint="pharmacy_search",
        )

        current_page = 0
        total_pages = 0
        page_size = 0
        has_previous = False
        has_next = False
        if data and data.get("PageResult"):
            page_result = data.get("PageResult")
            current_page = page_result.get("CurrentPage", 0)
            total_pages = page_result.get("TotalPages", 0)
            page_size = page_result.get("PageSize", 0)
            has_previous = page_result.get("HasPrevious", False)
            has_next = page_result.get("HasNext", False)
        pagination = Pagination(
            current_page=current_page,
            total_pages=total_pages,
            page_size=page_size,
            has_previous=has_previous,
            has_next=has_next,
        )

        if status_code != 200 or not data or not data.get("Items"):
            stats.increment(
                metric_name="api.dosespot.pharmacy_search.error",
                pod_name=stats.PodNames.MPRACTICE_CORE,
            )
            log.error(
                "Problem with DoseSpot pharmacy search",
                status_code=status_code,
                result=data and data.get("Result"),
            )
            return [], pagination

        pharmacies = data["Items"]
        return pharmacies, pagination

    @ddtrace.tracer.wrap()
    async def pharmacy_search_by_page_number(
        self, session: aiohttp.ClientSession, params: Dict, page_number: int
    ) -> Tuple[List, int]:
        params["pageNumber"] = page_number
        status_code, data = await self.api_request_async(
            session=session,
            url="api/pharmacies/search",
            params=params,
            method="GET",
            endpoint="pharmacy_search",
        )

        if status_code != 200 or not data.get("Items"):
            stats.increment(
                metric_name="api.dosespot.pharmacy_search.error",
                pod_name=stats.PodNames.MPRACTICE_CORE,
            )
            log.error(
                "Problem with DoseSpot pharmacy search",
                status_code=status_code,
                result=data and data.get("Result"),
            )
            return [], False

        pharmacies = []
        for pharmacy in data["Items"]:
            pharmacies.append(pharmacy)

        total_pages = 0
        if data.get("PageResult") and data.get("PageResult").get("TotalPages"):
            total_pages = data.get("PageResult").get("TotalPages")

        return pharmacies, total_pages

    @ddtrace.tracer.wrap()
    def validate_pharmacy(self, pharmacy_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        status_code, data = self.api_request(
            f"api/pharmacies/{pharmacy_id}", method="GET", endpoint="validate_pharmacy"
        )
        self.audit(DoseSpotActionTypes.validate_pharmacy, status_code, data)
        if status_code == 200 and data.get("Item"):
            return data["Item"]
        else:
            stats.increment(
                metric_name="api.dosespot.validate_pharmacy.error",
                pod_name=stats.PodNames.MPRACTICE_CORE,
            )
            log.error(
                "Problem validating DoseSpot pharmacy",
                pharmacy_id=pharmacy_id,
                status_code=status_code,
                result=data and data.get("Result"),
            )
            return {}

    @ddtrace.tracer.wrap()
    def medication_list(
        self,
        patient_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> List:
        params: Dict[str, Any] = {"pageNumber": 1}
        if start_date:
            params["startDate"] = datetime.strftime(start_date, "%Y-%m-%dT%H:%M:%S")
        if end_date:
            params["endDate"] = datetime.strftime(end_date, "%Y-%m-%dT%H:%M:%S")

        medications, has_next_page = self.medication_list_with_pagination(
            patient_id=patient_id, params=params
        )
        results = medications
        while has_next_page:
            params["pageNumber"] = params["pageNumber"] + 1
            medications, has_next_page = self.medication_list_with_pagination(
                patient_id=patient_id, params=params
            )
            results.extend(medications)
        return results

    @ddtrace.tracer.wrap()
    def medication_list_with_pagination(
        self, patient_id: str, params: Dict
    ) -> Tuple[List, bool]:
        status_code, data = self.api_request(
            f"api/patients/{patient_id}/prescriptions",
            params=params,
            method="GET",
            endpoint="get_patient_prescriptions",
        )
        self.audit(DoseSpotActionTypes.get_medication_list, status_code, data)

        if status_code != 200 or not data.get("Items"):
            log.error(
                "Problem fetching prescriptions",
                patient_id=patient_id,
                status_code=status_code,
                result=data and data.get("Result"),
            )
            return [], False

        results = []
        for prescription in data["Items"]:
            # 1: Active, 5: Completed. See DoseSpot API 4.2.10 Patient Medication Status Type
            if prescription["MedicationStatus"] in [1, 5]:
                # DateWritten property was renamed during the DoseSpot api upgrade, so here's a compatibility fix
                prescription["DateWritten"] = dateutil.parser.parse(
                    prescription["WrittenDate"], ignoretz=True
                )
                # Another rename compatibility fix
                prescription["MedicationId"] = prescription["PatientMedicationId"]
                # PrescriptionStatus was also changed during the DoseSpot api upgrade
                prescription_status = {
                    1: "Entered",
                    2: "Printed",
                    3: "Sending",
                    4: "eRxSent",
                    5: "FaxSent",
                    6: "Error",
                    7: "Deleted",
                    8: "Requested",
                    9: "Edited",
                    10: "EpcsError",
                    11: "EpcsSigned",
                    12: "ReadyToSign",
                    13: "PharmacyVerified",
                }
                if prescription["Status"] in prescription_status:
                    prescription["PrescriptionStatus"] = prescription_status[
                        prescription["Status"]
                    ]
                else:
                    log.error(
                        "Dosespot returned unexpected prescription status",
                        status=prescription["Status"],
                    )
                    prescription["PrescriptionStatus"] = "Error"
                results.append(prescription)

        has_next_page = False
        if data.get("PageResult") and data.get("PageResult").get("HasNext"):
            has_next_page = data.get("PageResult").get("HasNext")

        return results, has_next_page
