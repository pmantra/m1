from __future__ import annotations

import datetime
import json
import re
from typing import TYPE_CHECKING, Any, Literal, Mapping, Optional, Tuple

import inflection
import jwt
import requests
from flask_restful import abort
from requests import HTTPError, Response

from common import stats
from common.base_http_client import AccessTokenMixin, BaseHttpClient
from common.constants import Environment
from cost_breakdown.constants import ClaimType
from geography import CountryRepository
from models.profiles import Address
from storage.connection import db
from utils.log import logger
from utils.payments import convert_cents_to_dollars
from wallet.constants import (
    ALEGEUS_API_CLIENT_ID,
    ALEGEUS_API_PASSWORD,
    ALEGEUS_API_SECRET,
    ALEGEUS_API_USERNAME,
    ALEGEUS_CERT,
    ALEGEUS_PRIVATE_KEY,
    ALEGEUS_PROD_API_CLIENT_ID,
    ALEGEUS_PROD_TOKEN_URL,
    ALEGEUS_PROD_USER_ID,
    ALEGEUS_TOKEN_URL,
    ALEGEUS_TPAID,
    ALEGEUS_WCA_URL,
    ALEGEUS_WCP_URL,
    MAVEN_ADDRESS,
)
from wallet.decorators import (
    validate_account,
    validate_claim,
    validate_dependent,
    validate_plan,
    validate_reimbursement_request,
    validate_user_asset,
    validate_wallet,
)
from wallet.models.constants import (
    AlegeusCardStatus,
    AlegeusCoverageTier,
    ReimbursementMethod,
)

if TYPE_CHECKING:
    from models.enterprise import UserAsset
    from wallet.models.organization_employee_dependent import (
        OrganizationEmployeeDependent,
    )
    from wallet.models.reimbursement import (
        ReimbursementAccount,
        ReimbursementClaim,
        ReimbursementPlan,
        ReimbursementRequest,
    )
    from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)

METRIC_PREFIX = "api.wallet.alegeus_api"

# Headers
CONTENT_TYPE = "application/json"

# Alegeus file format codes used during file uploads.
ALEGEUS_FILE_FORMAT_CODES = {
    "image/jpeg": 64,
    "image/png": 4096,
    "application/pdf": 8,
    "text/csv": 2,
}


class AlegeusApi(AccessTokenMixin, BaseHttpClient):
    """
    This class is responsible for calling the Alegeus APIs (WCP and WCA).
    """

    def __init__(self) -> None:
        # No base URL because the APIs are split between two servers
        super().__init__(
            service_name="AlegeusAPI",
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

        if Environment.current() == Environment.PRODUCTION:
            data = (
                "grant_type=Cert"
                f"&client_id={ALEGEUS_PROD_API_CLIENT_ID}"
                "&scope=mbi_api bensoft_api"
                f"&tpa_id={ALEGEUS_TPAID}"
                f"&user_id={ALEGEUS_PROD_USER_ID}"
            )
            url = ALEGEUS_PROD_TOKEN_URL
            cert = (ALEGEUS_CERT, ALEGEUS_PRIVATE_KEY)
        else:
            data = {
                # type: ignore[assignment] # Incompatible types in assignment (expression has type "Dict[str, Optional[str]]", variable has type "str")
                "grant_type": "password",
                "client_id": ALEGEUS_API_CLIENT_ID,
                "client_secret": ALEGEUS_API_SECRET,
                "scope": "mbi_api bensoft_api",
                "username": ALEGEUS_API_USERNAME,
                "password": ALEGEUS_API_PASSWORD,
                "tpa_id": ALEGEUS_TPAID,
            }
            url = ALEGEUS_TOKEN_URL
            cert = None

        response = self.make_request(
            url=url,
            data=data,
            extra_headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
            timeout=15,
            metric_suffix="create_access_token",
            cert=cert,
        )

        if response.ok:
            access_token = response.json()["access_token"] or None
            access_token_expiration = (
                _get_token_expiration(access_token) if access_token else None
            )

        return access_token, access_token_expiration

    def make_api_request(
        self,
        url: str,
        data: Any = None,
        params: dict[str, Any] | None = None,
        api_version: str | None = None,
        extra_headers: Mapping[str, str] | None = None,
        method: Literal["GET", "PUT", "POST", "DELETE", "PATCH"] = "GET",
        timeout: int | None = None,
        retry_on_error: bool = True,
    ) -> Response:
        """
        Use BaseHttpClient.make_request to make a properly-formatted API request with auth, plus logging
        """
        self.get_access_token()

        if not self.access_token:
            self.log.error("Failed to retrieve access token. Skipping API request.")
            default_response = Response()
            default_response.status_code = 401
            default_response._content = "No Access Token Available"
            return default_response

        headers = {
            "Authorization": f"Bearer {self.access_token}",
        }

        if api_version:
            headers["api-version"] = api_version

        if extra_headers:
            headers.update(extra_headers)

        return self.make_request(
            url=url,
            data=json.dumps(data) or {},
            params=params or {},
            extra_headers=headers,
            method=method,
            timeout=timeout,
            retry_on_error=retry_on_error,
            metric_suffix="make_api_request",
        )

    def _should_retry_on_error(self, error: Exception) -> bool:
        # Retry on token errors only
        if isinstance(error, HTTPError):
            try:
                response_json = error.response.json()
                if (
                    isinstance(response_json, dict)
                    and response_json.get("Description") == "invalid token format"
                ):
                    self.create_access_token()
                    return True
            except requests.JSONDecodeError:
                pass

        return False

    def _retry_make_request(self, **kwargs: Any) -> Response:
        # Overwrite auth header with the new token created in _should_retry_on_error
        retry_args = kwargs
        retry_args["extra_headers"]["Authorization"] = f"Bearer {self.access_token}"
        return super()._retry_make_request(**retry_args)

    def get_user_info(self) -> Response:
        """
        Get details of the authenticated user. (Usually the API user.)
        """

        route = f"{ALEGEUS_WCP_URL}/userinfo"

        return self.make_api_request(
            route,
            api_version="18.0",
            method="GET",
        )

    def get_employer_list(self) -> Response:
        """
        List employers defined in WCA.
        """

        route = f"{ALEGEUS_WCA_URL}/Services/Employer/{ALEGEUS_TPAID}/List"

        return self.make_api_request(
            route,
            method="GET",
        )

    @validate_wallet
    def get_employee_details(self, wallet: ReimbursementWallet) -> Response:
        """
        Get member details (including demographic info) from Alegeus.

        This will include bank account information so be careful how we use this data.
        It no longer contains the full debit card pan.
        In almost all cases we will want to use `AlegeusApi.get_employee_demographic`
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/employee/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        return self.make_api_request(
            route,
            api_version="10.1",
            method="GET",
        )

    @validate_wallet
    def get_employee_demographic(self, wallet: ReimbursementWallet) -> Response:
        """
        Get member demographic information from Alegeus.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/employee/enrollment/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        return self.make_api_request(route, method="GET")

    @validate_wallet
    def get_all_dependents(self, wallet: ReimbursementWallet) -> Response:
        """
        Get a list of a member's dependents' demographic information.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/dependent/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"
        return self.make_api_request(route, api_version="0.0", method="GET")

    @validate_wallet
    @validate_dependent
    def get_dependent_demographic(
        self, wallet: ReimbursementWallet, dependent: OrganizationEmployeeDependent
    ) -> Response:
        """
        Get a member's dependent's demographic information.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id
        dependent_id = dependent.alegeus_dependent_id
        route = f"{ALEGEUS_WCP_URL}/participant/dependent/{ALEGEUS_TPAID}/{employer_id}/{employee_id}/{dependent_id}"

        return self.make_api_request(route, api_version="0.0", method="GET")

    @validate_wallet
    def get_account_summary(
        self, wallet: ReimbursementWallet, plan_year: str = "CurrentAndFuture"
    ) -> Response:
        """
        Get a list of the accounts a member is enrolled in.
        Members are enrolled in plans via the `AlegeusApi.post_add_employee_account` method.
        The output of this API call is used to create `ReimbursementAccount`s.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/accounts/summary/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        return self.make_api_request(
            route,
            api_version="10.1",
            params={"planyear": plan_year},
            method="GET",
        )

    @validate_wallet
    @validate_account
    def get_account_details(
        self, wallet: ReimbursementWallet, account: ReimbursementAccount
    ) -> Response:
        """
        Get the details for a specific plan a member is enrolled in.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/accounts/details/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        return self.make_api_request(
            route,
            api_version="10.1",
            params={
                "flexaccountkey": account.alegeus_flex_account_key,
                "accttypecode": account.alegeus_account_type.alegeus_account_type,
            },
            method="GET",
        )

    @validate_wallet
    def put_employee_services_and_banking(
        self,
        wallet: ReimbursementWallet,
        banking_info: Optional[dict] = None,
        eligibility_date: Optional[datetime.date] = None,
        member_address: Optional[Address] = None,
        employee_dob: Optional[datetime.date] = None,
        termination_date: Optional[datetime.date] = None,
    ) -> Response:
        """
        Update the demographic and banking info for a member.

        Hey You! If you're thinking about replacing this WCP call with an equivalent WCA call, know that the WCA call
        probably returns the full employee details object including the debit card PAN, and that is a BIG NOPE.
        """
        valid_banking_info_columns = (
            "BankAcctName",
            "BankAccount",
            "BankAccountTypeCode",
            "BankRoutingNumber",
        )

        if not banking_info:
            banking_info = {}
            # We cannot send a reimbursement method of direct deposit here because we need valid banking details.
            # If not sent it will be cleared.
            if wallet.reimbursement_method != ReimbursementMethod.DIRECT_DEPOSIT:
                banking_info[
                    "ReimbursementCode"
                ] = wallet.reimbursement_method.value  # type: ignore[attr-defined] # "str" has no attribute "value"
        else:
            for col in banking_info:
                assert (
                    col in valid_banking_info_columns
                ), f"{col} is not a valid banking info field. Valid fields: {', '.join(valid_banking_info_columns)}"
            banking_info[
                "ReimbursementCode"
            ] = wallet.reimbursement_method.value  # type: ignore[attr-defined] # "str" has no attribute "value"

        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id
        first_name, last_name, date_of_birth = wallet.get_first_name_last_name_and_dob()

        route = f"{ALEGEUS_WCA_URL}/Services/Employee/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        if not member_address:
            address = MAVEN_ADDRESS
            address_1 = address.get("address_1", "")
            city = address.get("city", "")
            country = address.get("country", "")
            state = address.get("state", "")
            zip_code = address.get("zip", "")
        else:
            address_1 = member_address.street_address
            city = member_address.city
            country = member_address.country
            state = member_address.state
            zip_code = member_address.zip_code

        if wallet.reimbursement_method is None:
            wallet.reimbursement_method = ReimbursementMethod.DIRECT_DEPOSIT
            db.session.add(wallet)
            db.session.commit()

        country_repo = CountryRepository(session=db.session)
        country_ = country_repo.get_by_name(name=country)

        if country_:
            country = country_.alpha_2
        else:
            abort(400, message="Invalid Country Code")

        body = {
            **banking_info,
            "Address1": address_1,
            "City": city,
            "Country": country,
            "EmployeeId": employee_id,
            "EmployerId": employer_id,
            "FirstName": format_name_field(first_name),
            "LastName": format_name_field(last_name),
            "State": state,
            "ZipCode": zip_code,
            "TpaId": ALEGEUS_TPAID,
            "CurrentEmployeeSocialSecurityNumber": "",
            "NewEmployeeSocialSecurityNumber": "",
            "EmployeeStatus": "Active",
            "NoOverwrite": True,
        }

        if eligibility_date:
            body["EligibilityDate"] = eligibility_date.isoformat()

        if employee_dob:
            body["BirthDate"] = employee_dob.isoformat()

        if termination_date:
            body["TerminationDate"] = termination_date.isoformat()

        return self.make_api_request(route, api_version="1.1", data=body, method="PUT")

    @validate_wallet
    def get_ach_accounts(self, wallet: ReimbursementWallet) -> Response:
        """
        Get the member's bank accounts (ACH) from Alegeus.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/repayment/achaccounts/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        return self.make_api_request(
            route,
            api_version="0.0",
            method="GET",
        )

    @validate_wallet
    def post_employee_services_and_banking(
        self,
        wallet: ReimbursementWallet,
        eligibility_date: Optional[datetime.date] = None,
    ) -> Response:
        """
        Create a member in the Alegeus system.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id
        first_name, last_name, date_of_birth = wallet.get_first_name_last_name_and_dob()

        route = f"{ALEGEUS_WCA_URL}/Services/Employee/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        address = MAVEN_ADDRESS

        body = {
            "Address1": address.get("address_1", ""),
            "City": address.get("city", ""),
            "Country": address.get("country", ""),
            "EmployeeId": employee_id,
            "EmployerId": employer_id,
            "FirstName": format_name_field(first_name),
            "LastName": format_name_field(last_name),
            "State": address.get("state", ""),
            "ZipCode": address.get("zip", ""),
            "TpaId": ALEGEUS_TPAID,
        }

        if eligibility_date:
            body["EligibilityDate"] = eligibility_date.isoformat()

        # We cannot send a reimbursement method of direct deposit here because we need valid banking details.
        # This will be added when adding banking details via the PUT method.
        reimbursement_method = wallet.reimbursement_method
        if reimbursement_method != ReimbursementMethod.DIRECT_DEPOSIT:
            body.update({"ReimbursementCode": wallet.reimbursement_method.value})  # type: ignore[attr-defined] # "str" has no attribute "value"

        return self.make_api_request(route, api_version="1.1", data=body, method="POST")

    @validate_wallet
    def post_dependent_services(
        self,
        wallet: ReimbursementWallet,
        alegeus_id_of_dependent: int,
        first_name: str,
        last_name: str,
    ) -> Response:
        """
        Create a dependent in the Alegeus system.
        """
        organization = wallet.reimbursement_organization_settings.organization

        # Alegeus ID of the individual who directly receives the Alegeus benefit.
        direct_beneficiary_alegeus_id: int = wallet.alegeus_id  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[str]", variable has type "int")
        employer_id = organization.alegeus_employer_id

        route = f"{ALEGEUS_WCA_URL}/Services/Employee/Dependent/{ALEGEUS_TPAID}/{employer_id}/{direct_beneficiary_alegeus_id}"

        address = MAVEN_ADDRESS
        body = {
            "Address1": address.get("address_1", ""),
            "City": address.get("city", ""),
            "Country": address.get("country", ""),
            "EmployeeId": direct_beneficiary_alegeus_id,
            "EmployerId": employer_id,
            "FirstName": format_name_field(first_name),
            "LastName": format_name_field(last_name),
            "State": address.get("state", ""),
            "ZipCode": address.get("zip", ""),
            "TpaId": ALEGEUS_TPAID,
            "DependentId": alegeus_id_of_dependent,
        }

        return self.make_api_request(route, api_version="1.0", data=body, method="POST")

    @validate_wallet
    def update_employee_termination_date(
        self,
        wallet: ReimbursementWallet,
        termination_date: Optional[datetime.date] = None,
        member_address: Optional[Address] = None,
    ) -> Response:
        """
        Set termination date on a employee service
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id
        first_name, last_name, date_of_birth = wallet.get_first_name_last_name_and_dob()

        route = f"{ALEGEUS_WCA_URL}/Services/Employee/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        # If no address is provided, use the default Maven address
        # Non-US addresses are not supported by Alegeus, so we use the Maven address in that case as well
        if not member_address or member_address.country != "US":
            address = MAVEN_ADDRESS
            address_1 = address.get("address_1", "")
            city = address.get("city", "")
            country = address.get("country", "")
            state = address.get("state", "")
            zip_code = address.get("zip", "")
        else:
            address_1 = member_address.street_address
            city = member_address.city
            country = member_address.country
            state = member_address.state
            zip_code = member_address.zip_code

        country_repo = CountryRepository(session=db.session)
        country_ = country_repo.get_by_name(name=country)

        if country_:
            country = country_.alpha_2
        else:
            abort(400, message="Invalid Country Code")

        body = {
            "Address1": address_1,
            "City": city,
            "Country": country,
            "EmployeeId": employee_id,
            "EmployerId": employer_id,
            "FirstName": format_name_field(first_name),
            "LastName": format_name_field(last_name),
            "State": state,
            "ZipCode": zip_code,
            "TpaId": ALEGEUS_TPAID,
            "EmployeeStatus": "Active",
            "NoOverwrite": True,
            "TerminationDate": termination_date.isoformat()
            if termination_date
            else None,
        }

        return self.make_api_request(route, api_version="1.1", data=body, method="PUT")

    @validate_wallet
    def put_dependent_services(
        self,
        wallet: ReimbursementWallet,
        alegeus_id_of_dependent: str,
        first_name: str,
        last_name: str,
    ) -> Response:
        """
        Update a dependent in the Alegeus system.
        """
        # Alegeus ID of the individual who directly receives the Alegeus benefit.
        direct_beneficiary_alegeus_id: int = wallet.alegeus_id  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[str]", variable has type "int")
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id

        route = f"{ALEGEUS_WCA_URL}/Services/Employee/Dependent/{ALEGEUS_TPAID}/{employer_id}/{direct_beneficiary_alegeus_id}"

        address = MAVEN_ADDRESS

        body = {
            "Address1": address.get("address_1", ""),
            "City": address.get("city", ""),
            "Country": address.get("country", ""),
            "EmployeeId": direct_beneficiary_alegeus_id,
            "EmployerId": employer_id,
            "FirstName": format_name_field(first_name),
            "LastName": format_name_field(last_name),
            "State": address.get("state", ""),
            "ZipCode": address.get("zip", ""),
            "TpaId": ALEGEUS_TPAID,
            "DependentId": alegeus_id_of_dependent,
        }

        return self.make_api_request(route, api_version="1.0", data=body, method="PUT")

    @validate_wallet
    @validate_plan
    def post_link_dependent_to_employee_account(
        self,
        wallet: ReimbursementWallet,
        plan: ReimbursementPlan,
        alegeus_id_of_dependent: str,
    ) -> Response:
        """
        Link a dependent that is already in the Alegeus System to an account.
        """
        direct_beneficiary_alegeus_id: int = wallet.alegeus_id  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[str]", variable has type "int")
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id

        route = f"{ALEGEUS_WCA_URL}/Services/Employee/Account/DependentAccount/{ALEGEUS_TPAID}/{employer_id}/{direct_beneficiary_alegeus_id}"

        body = {
            "accountTypeCode": plan.reimbursement_account_type.alegeus_account_type,
            "dependentId": alegeus_id_of_dependent,
            "planYearEndDate": plan.end_date.isoformat(),
            # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "isoformat"
            "planYearStartDate": plan.start_date.isoformat(),
            # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "isoformat"
            "planId": plan.alegeus_plan_id,
        }

        return self.make_api_request(route, data=body, method="POST")

    @validate_wallet
    @validate_plan
    def post_add_employee_account(
        self,
        wallet: ReimbursementWallet,
        plan: ReimbursementPlan,
        prefunded_amount: int,
        coverage_tier: AlegeusCoverageTier | None,
        start_date: datetime.date,
    ) -> Response:
        """
        Enroll a member in an account.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCA_URL}/Services/Employee/Account/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        body = {
            "accountTypeCode": plan.reimbursement_account_type.alegeus_account_type,
            "employeeId": employee_id,
            "employerId": employer_id,
            "planId": plan.alegeus_plan_id,
            "planYearEndDate": plan.end_date.isoformat(),
            # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "isoformat"
            "planYearStartDate": plan.start_date.isoformat(),
            "effectiveDate": start_date.isoformat(),
            "tpaId": ALEGEUS_TPAID,
            "originalPrefundedAmount": convert_cents_to_dollars(prefunded_amount),
        }

        if coverage_tier:
            body["coverageTierId"] = coverage_tier.value

        return self.make_api_request(route, api_version="0.0", data=body, method="POST")

    @validate_plan
    def terminate_employee_account(
        self,
        employer_id: str,
        employee_id: str,
        plan: ReimbursementPlan,
        termination_date: datetime.date,
    ) -> Response:
        """
        Set termination date on an existing employee account.
        """
        route = f"{ALEGEUS_WCA_URL}/Services/Employee/Account/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        body = {
            "accountTypeCode": plan.reimbursement_account_type.alegeus_account_type,
            "employeeId": employee_id,
            "employerId": employer_id,
            "planId": plan.alegeus_plan_id,
            "planYearEndDate": plan.end_date.isoformat(),
            # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "isoformat"
            "planYearStartDate": plan.start_date.isoformat(),
            # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "isoformat"
            "tpaId": ALEGEUS_TPAID,
            "terminationDate": termination_date.isoformat(),
            # We need to terminate plan for the same account type, i.e. one user can only have one hra type account type
            # at a time.
            "cardholderAccountStatus": "Terminated",
        }
        return self.make_api_request(route, api_version="0.0", data=body, method="PUT")

    @validate_plan
    def reactivate_employee_account(
        self, employer_id: str, employee_id: str, plan: ReimbursementPlan
    ) -> Response:
        """
        Set termination date on an existing employee account to None.
        """
        route = f"{ALEGEUS_WCA_URL}/Services/Employee/Account/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        body = {
            "accountTypeCode": plan.reimbursement_account_type.alegeus_account_type,
            "employeeId": employee_id,
            "employerId": employer_id,
            "planId": plan.alegeus_plan_id,
            "planYearEndDate": plan.end_date.isoformat(),
            # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "isoformat"
            "planYearStartDate": plan.start_date.isoformat(),
            # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "isoformat"
            "tpaId": ALEGEUS_TPAID,
            "terminationDate": None,
            "cardholderAccountStatus": "Active",
        }
        return self.make_api_request(route, api_version="0.0", data=body, method="PUT")

    @validate_wallet
    @validate_plan
    def post_add_prefunded_deposit(
        self,
        wallet: ReimbursementWallet,
        plan: ReimbursementPlan,
        deposit_amount: int,
    ) -> Optional[Response]:
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCA_URL}/Services/Transaction/{ALEGEUS_TPAID}/{employer_id}/{employee_id}/PrefundedDeposit"

        body = {
            "AccountTypeCode": plan.reimbursement_account_type.alegeus_account_type,
            "PrefundedAdjustmentAmount": convert_cents_to_dollars(deposit_amount),
            "employeeId": employee_id,
            "employerId": employer_id,
            "planId": plan.alegeus_plan_id,
            "accountTypeStartDate": plan.start_date.isoformat(),
            # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "isoformat"
            "accountTypeEndDate": plan.end_date.isoformat(),
            # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "isoformat"
            "tpaId": ALEGEUS_TPAID,
        }

        return self.make_api_request(
            route,
            api_version="8.0",
            data=body,
            method="POST",
            timeout=30,
        )

    @validate_wallet
    def get_employee_activity(
        self, wallet: ReimbursementWallet, timeout: int = 2
    ) -> Response:
        """
        Retrieve all claims and transactions for this wallet user.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/transactions/getemployeeactivity/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        return self.make_api_request(
            route,
            api_version="17.0",
            method="GET",
            timeout=timeout,  # 2 seconds default
        )

    @validate_wallet
    def get_transaction_details(
        self,
        wallet: ReimbursementWallet,
        transactionid: str,
        seqnum: int,
        setldate: str,
    ) -> Response:
        """
        Retrieve transaction details for this wallet user.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/transactions/detailsex/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        return self.make_api_request(
            route,
            api_version="0.0",
            params={
                "transactionid": transactionid,
                "seqnum": seqnum,
                "setldate": setldate,
            },
            method="GET",
        )

    @validate_plan
    def post_add_qle(
        self,
        wallet: ReimbursementWallet,
        plan: ReimbursementPlan,
        amount: float,
        effective_date: datetime.datetime,
    ) -> Response:
        """
        Create a Qualified Life Event in Alegeus. This will update the funds available for this member.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCA_URL}/Services/Employee/Account/FlexAccountLifeEvent/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        body = {
            "accountTypeCode": plan.reimbursement_account_type.alegeus_account_type,
            "planId": plan.alegeus_plan_id,
            "planYearEndDate": plan.end_date.isoformat(),
            # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "isoformat"
            "planYearStartDate": plan.start_date.isoformat(),
            # type: ignore[union-attr] # Item "None" of "Optional[date]" has no attribute "isoformat"
            "annualElection": amount,
            "lifeEventDate": effective_date.isoformat(),
            "lifeEventCde": "0000",
        }

        return self.make_api_request(route, api_version="0.0", data=body, method="POST")

    @staticmethod
    def build_request_route_and_body_of_post_direct_payment_claim(
        wallet: ReimbursementWallet,
        reimbursement_request: ReimbursementRequest,
        reimbursement_account: ReimbursementAccount,
        reimbursement_claim: ReimbursementClaim,
        claim_type: ClaimType,
        reimbursement_mode: str = "None",
        reimbursement_amount: int = None,
    ) -> Tuple[str, dict]:
        reimbursement_plan = reimbursement_account.plan
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCA_URL}/Services/Transaction/{ALEGEUS_TPAID}/{employer_id}"
        if reimbursement_request.amount < 0:
            route += "/ManualRefund"
        else:
            route += "/ManualClaim"

        account_type_code = (
            "DTR"
            if claim_type == ClaimType.EMPLOYEE_DEDUCTIBLE
            else reimbursement_plan.reimbursement_account_type.alegeus_account_type
        )
        body = {
            "AccountTypeCode": account_type_code,
            "EmployerId": organization.alegeus_employer_id,
            "CardholderId": employee_id,
            "DateOfServiceFrom": reimbursement_request.service_start_date.strftime(
                "%Y-%m-%d"
            ),
            "DateOfServiceTo": reimbursement_request.service_end_date.strftime(
                # type: ignore[union-attr] # Item "None" of "Optional[datetime]" has no attribute "strftime"
                "%Y-%m-%d"
            ),
            "ReimbursementMode": reimbursement_mode,
            "TrackingNumber": reimbursement_claim.alegeus_claim_id,
        }
        amount = (
            convert_cents_to_dollars(reimbursement_amount)
            if reimbursement_amount
            else convert_cents_to_dollars(
                reimbursement_request.usd_reimbursement_amount
            )
        )
        if reimbursement_request.amount < 0:
            body["RefundAmount"] = amount
        else:
            body["ApprovedClaimAmount"] = amount
        return route, body

    @validate_wallet
    @validate_plan
    def post_adjust_plan_amount(
        self,
        wallet: ReimbursementWallet,
        claim_id: str,
        plan: ReimbursementPlan,
        service_start_date: datetime.date,
        reimbursement_amount: int = None,
    ) -> Optional[Response]:
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id
        route = f"{ALEGEUS_WCA_URL}/Services/Transaction/{ALEGEUS_TPAID}/{employer_id}/ManualClaim"
        body = {
            "AccountTypeCode": plan.reimbursement_account_type.alegeus_account_type,
            "EmployerId": organization.alegeus_employer_id,
            "CardholderId": employee_id,
            "DateOfServiceFrom": service_start_date.strftime("%Y-%m-%d"),
            "DateOfServiceTo": service_start_date.strftime(
                # type: ignore[union-attr] # Item "None" of "Optional[datetime]" has no attribute "strftime"
                "%Y-%m-%d"
            ),
            "ReimbursementMode": "None",
            "TrackingNumber": claim_id,
            "ApprovedClaimAmount": convert_cents_to_dollars(reimbursement_amount),
        }

        return self.make_api_request(
            route,
            api_version="8.0",
            data=body,
            method="POST",
            timeout=30,
        )

    @validate_wallet
    @validate_reimbursement_request
    @validate_account
    @validate_claim
    def post_direct_payment_claim(
        self,
        wallet: ReimbursementWallet,
        reimbursement_request: ReimbursementRequest,
        reimbursement_account: ReimbursementAccount,
        reimbursement_claim: ReimbursementClaim,
        claim_type: ClaimType,
        reimbursement_mode: str = "None",
        reimbursement_amount: int = None,
    ) -> Optional[Response]:
        route, body = self.build_request_route_and_body_of_post_direct_payment_claim(
            wallet,
            reimbursement_request,
            reimbursement_account,
            reimbursement_claim,
            claim_type,
            reimbursement_mode,
            reimbursement_amount,
        )

        return self.make_api_request(
            route,
            api_version="8.0",
            data=body,
            method="POST",
            timeout=30,
        )

    @validate_wallet
    @validate_reimbursement_request
    @validate_account
    @validate_claim
    def post_claim(
        self,
        wallet: ReimbursementWallet,
        reimbursement_request: ReimbursementRequest,
        reimbursement_account: ReimbursementAccount,
        reimbursement_claim: ReimbursementClaim,
    ) -> Response:
        """
        Submit a new claim to Alegeus for this wallet user. Note: This will submit a claim without any attachments.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/claims/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        dollar_amount = convert_cents_to_dollars(
            reimbursement_request.usd_reimbursement_amount
        )

        log.info(
            "post_claim called",
            wallet_id=str(wallet.id),
            reimbursement_request_id=str(reimbursement_request.id),
            reimbursement_request_currency_code=str(
                reimbursement_request.benefit_currency_code or "USD"
            ),
            reimbursement_request_transaction_currency_code=str(
                reimbursement_request.transaction_currency_code or "USD"
            ),
            reimbursement_claim_id=str(reimbursement_claim.id),
            usd_dollar_amount=str(dollar_amount),
        )

        body = {
            "Claims": [
                {
                    "Claimant": {},
                    "ServiceStartDate": format_date_for_wcp(
                        reimbursement_request.service_start_date
                    ),
                    "TxnAmt": dollar_amount,
                    "TrackingNum": reimbursement_claim.alegeus_claim_id,
                }
            ]
        }

        if reimbursement_request.wallet_expense_subtype:
            body["Claims"][0][
                "ScCde"
            ] = reimbursement_request.wallet_expense_subtype.code

        return self.make_api_request(route, api_version="0.0", data=body, method="POST")

    @validate_wallet
    @validate_user_asset
    def upload_attachment_for_claim(
        self,
        wallet: ReimbursementWallet,
        user_asset: UserAsset,
        alegeus_claim_key: int,
        attachment_b64_str: str,
    ) -> Response:
        """
        Upload an attachment (Invoice, Receipt) for a Claim to Alegeus.
        """
        if not alegeus_claim_key:
            raise Exception(
                "Aborting Alegeus request. An alegeus_claim_key is required to upload attachments"
            )

        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/receipts/submitted/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        content_type = user_asset.content_type and user_asset.content_type.lower()
        alegeus_file_name = sanitize_file_name_for_alegeus(
            user_asset.file_name, content_type
        )

        body = {
            "FileFormat": ALEGEUS_FILE_FORMAT_CODES.get(content_type, 0),
            "ContentLength": user_asset.content_length,
            "ContentType": content_type,
            "FileName": alegeus_file_name,
            "Base64": attachment_b64_str,
        }

        return self.make_api_request(
            route,
            api_version="0.0",
            params={"claimkey": alegeus_claim_key},
            data=body,
            method="PUT",
        )

    @validate_wallet
    @validate_user_asset
    def upload_attachment_for_card_transaction(
        self,
        wallet: ReimbursementWallet,
        user_asset: UserAsset,
        transaction_id: int,
        settlement_date: str,
        sequence_number: int,
        attachment_b64_str: str,
    ) -> Response:
        """
        Upload an attachment (Invoice, Receipt) for a Debit Card Transaction to Alegeus.
        """
        if not all([transaction_id, settlement_date, sequence_number]):
            raise Exception(
                f"Aborting Alegeus Card doc upload request. Missing data for uploading user_asset: {user_asset.id}"
            )

        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/receipts/pos/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"
        params = {
            "transactionid": transaction_id,
            "setldate": settlement_date,
            "seqnum": sequence_number,
        }

        content_type = user_asset.content_type and user_asset.content_type.lower()
        alegeus_file_name = sanitize_file_name_for_alegeus(
            user_asset.file_name, content_type
        )

        body = {
            "FileFormat": ALEGEUS_FILE_FORMAT_CODES.get(content_type, 0),
            "ContentLength": user_asset.content_length,
            "ContentType": content_type,
            "FileName": alegeus_file_name,
            "Base64": attachment_b64_str,
        }

        return self.make_api_request(
            route,
            api_version="0.0",
            params=params,
            data=body,
            method="PUT",
        )

    @validate_wallet
    def post_issue_new_card(
        self,
        wallet: ReimbursementWallet,
    ) -> Response:
        """
        Issue a new card for the member.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/cards/new/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        params = {"status": AlegeusCardStatus.NEW}

        return self.make_api_request(
            route, api_version="0.0", params=params, method="POST"
        )

    @validate_wallet
    def get_debit_card_details(
        self,
        wallet: ReimbursementWallet,
        card_number: str,
    ) -> Response:
        """
        Get debit card details.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/cards/details/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        params = {"card": card_number}

        return self.make_api_request(
            route, api_version="0.0", params=params, method="GET"
        )

    @validate_wallet
    def put_debit_card_update_status(
        self,
        wallet: ReimbursementWallet,
        card_number: str,
        card_status: AlegeusCardStatus,
    ) -> Response:
        """
        Updates member debit card status.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/cards/status/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        params = {"status": card_status.value, "card": card_number}

        return self.make_api_request(
            route, api_version="0.0", params=params, method="PUT"
        )

    @validate_wallet
    def post_add_employee_phone_number(
        self,
        wallet: ReimbursementWallet,
        phone_number: str,
    ) -> Response:
        """
        Adds member phone number to Alegeus.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/communications/mobile/{ALEGEUS_TPAID}/{employer_id}/{employee_id}/{phone_number}"

        return self.make_api_request(
            route, api_version="0.0", params=None, method="POST"
        )

    @validate_wallet
    def delete_remove_employee_phone_number(
        self,
        wallet: ReimbursementWallet,
        phone_number: str,
    ) -> Response:
        """
        Deletes member phone number from Alegeus.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/communications/mobile/{ALEGEUS_TPAID}/{employer_id}/{employee_id}/{phone_number}"

        return self.make_api_request(
            route, api_version="0.0", params=None, method="DELETE"
        )

    @validate_wallet
    def get_member_phone_numbers(
        self,
        wallet: ReimbursementWallet,
    ) -> Response:
        """
        List member phone numbers from Alegeus.
        """
        organization = wallet.reimbursement_organization_settings.organization
        employer_id = organization.alegeus_employer_id
        employee_id = wallet.alegeus_id

        route = f"{ALEGEUS_WCP_URL}/participant/communications/mobile/{ALEGEUS_TPAID}/{employer_id}/{employee_id}"

        return self.make_api_request(
            route, api_version="0.0", params=None, method="GET"
        )


def format_date_for_wcp(dtm: datetime) -> str:  # type: ignore[valid-type] # Module "datetime" is not valid as a type
    """
    As of 11/17/21 Alegeus has confirmed that for API calls to their WCP service, Dates must be formatted according
    to the Microsoft JSON Date standard for millis timestamps
        Example: "/Date(1637178814)/"
    """
    timestamp = int(round(dtm.timestamp() * 1000))  # type: ignore[attr-defined] # datetime? has no attribute "timestamp"
    return f"/Date({timestamp})/"


def format_date_from_string_to_datetime(dtm: str) -> datetime:  # type: ignore[valid-type] # Module "datetime" is not valid as a type
    """
    Example: "/Date(1660712400000-0500)/" string.  This method converts into a datetime object.
    """
    timestamp = None
    if dtm:
        date_string = re.findall(r"(\d{13,})[+-]\d{4}", dtm)
        if date_string:
            timestamp = datetime.datetime.fromtimestamp(int(date_string[0]) / 1000)
    if timestamp:
        return timestamp
    else:
        raise AttributeError("Date string incorrectly formatted or missing.")


def format_name_field(name: str) -> str:
    """
    Return name field that conforms to Alegeus' requirements.

    This is done through a combination of replacing accented characters with their non-accented version
    (Á -> A, ü -> u, etc) and removing all remaining non-allowed characters. This is culturally insensitive and
    we hope Alegeus will make changes to their systems.

    > First name is either missing or contains invalid characters. Allowable characters are alphanumeric (a-z, A-Z,
    > 0-9), Special characters -  comma(,), period(.), dash(-), ampersand(&), single apostrophe('), and space( ).
    """
    if name == "":
        return name

    transliterated_name = inflection.transliterate(name)
    clean_name = re.sub(r"[^A-Za-z0-9,.&' \-]+", "", transliterated_name)

    if clean_name == "":
        return "---"

    return clean_name


def is_request_successful(response: Response) -> bool:
    """
    Determine if a request's response was successful.
    Uses the same logic as `requests.Response.raise_for_status()`
    """
    if not response.status_code:
        return False
    return not (400 <= response.status_code < 600)


def _get_error_response(response: requests.Response) -> Any:
    try:
        return response.json()
    except requests.JSONDecodeError:
        return response.content


def _get_token_expiration(access_token: str) -> Optional[str]:  # type: ignore[return] # Missing return statement
    """
    Get the expiration of the current access token
    """
    try:
        # We manually set these to bypass validation logic that was introduced in later versions of jwt - when first implemented, this verification wasn't done. Want to maintain that previous behavior
        decode_options = {
            "verify_exp": False,
            "verify_nbf": False,
            "verify_iat": False,
            "verify_aud": False,
            "verify_iss": False,
        }

        decoded = jwt.decode(
            jwt=access_token,
            key="secret",
            algorithms=["RS256"],
            options={**{"verify_signature": False}, **decode_options},
        )
        return decoded["exp"]
    except Exception as e:
        log.exception("Could not extract Alegeus API Token expiration", error=e)


def sanitize_file_name_for_alegeus(file_name: str, content_type: str) -> str:
    # TODO: Remove this if-elif block once iOS fix goes out
    alegeus_file_name = file_name

    if content_type == "image/jpeg" and not file_name.endswith((".jpg", ".jpeg")):
        alegeus_file_name += ".jpg"

    elif content_type == "image/png" and not file_name.endswith(".png"):
        alegeus_file_name += ".png"

    elif content_type == "application/pdf" and not file_name.endswith(".pdf"):
        alegeus_file_name += ".pdf"

    elif content_type == "text/csv" and not file_name.endswith(".csv"):
        alegeus_file_name += ".csv"

    # replace chars that alegeus does not accept
    sanitize_chars = {":": "-", " ": "_", "*": "", "<": "", ">": "", "?": "", "|": ""}
    for char in sanitize_chars.keys():
        alegeus_file_name = alegeus_file_name.replace(char, sanitize_chars[char])

    return alegeus_file_name
