from __future__ import annotations

import datetime
import functools
import json
import os
import random
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import ddtrace
import grpc
import inflection
from google.protobuf.wrappers_pb2 import (
    Int64Value,  # type: ignore[import-untyped] # Library stubs not installed for "google.protobuf.wrappers_pb2"
)

from common import stats
from eligibility.e9y import model, translate
from maven_schemas import eligibility_pb2 as e9ypb
from maven_schemas import eligibility_pb2_grpc as e9ygrpc
from maven_schemas.eligibility import eligibility_test_utility_pb2 as teste9ypb
from maven_schemas.eligibility import eligibility_test_utility_pb2_grpc as teste9ygrpc
from maven_schemas.eligibility import pre_eligibility_pb2 as pre9ypb
from maven_schemas.eligibility import pre_eligibility_pb2_grpc as pre9ygrpc
from utils import log as logging

logger = logging.logger(__name__)

__all__ = (
    "standard",
    "alternate",
    "client_specific",
    "member_id_search",
    "org_identity_search",
    "wallet_enablement_by_org_identity_search",
    "create_verification",
)

# E9y GRPC timeout setting for each API
# Mapping from API method name -> timeout in seconds
ELIGIBILITY_TIMEOUT_SETTING: Dict[str, float] = {
    "member_search": 2.0,
    "create_verification": 5.0,
    "get_verification": 5.0,
    "client_specific": 7.0,
    "get_eligible_features_for_user": 5.0,
    "alternate": 7.0,
}
# In case of no timeout found in above setting
# ELIGIBILITY_TIMEOUT_DEFAULT will be used
ELIGIBILITY_TIMEOUT_DEFAULT = 3.0


def _get_effective_timeout(
    override_timeout: Optional[float], grpc_method: str
) -> Optional[float]:
    """
    Get effective timeout,
    if there is an override_timeout, use it,
    otherwise lookup by GRPC method name in the setting map.
    if not found in the setting map, use  ELIGIBILITY_TIMEOUT_DEFAULT
    @param override_timeout: <float, optional> passed in timeout, this will override the setting values
    @param grpc_method: <str> name of the GRPC method
    @return: effective timeout, None means infinity
    """
    if override_timeout is not None:
        return override_timeout
    return ELIGIBILITY_TIMEOUT_SETTING.get(grpc_method, ELIGIBILITY_TIMEOUT_DEFAULT)


def _record_grpc_error(e: grpc.RpcError, method_name: str):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    """
    Send DD metrics when GRPC timeout
    @param e: GRPqC Error
    @param method_name: <str> GRPC method name
    @return: None
    """
    logger.error(
        "Error with eligibility GRPC call",
        api_name=method_name,
        grpc_error=e,
    )
    if e.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
        stats.increment(
            metric_name="api.eligibility.grpc.timeout",
            pod_name=stats.PodNames.ELIGIBILITY,
            tags=[
                f"method_name:{method_name}",
            ],
        )


def basic(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    first_name: str,
    last_name: str,
    date_of_birth: datetime.date,
    *,
    user_id: Optional[int] = None,
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[List[model.EligibilityMember]]:
    if not grpc_connection:
        logger.info("passed null connection to grpc endpoint", method="standard")
        grpc_connection = channel()
    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)
    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response: e9ypb.Member = stub.CheckBasicEligibility(  # type: ignore[name-defined, valid-type] # Name "e9ypb.Member" is not defined
            request=e9ypb.BasicEligibilityRequest(  # type: ignore[attr-defined] # Module has no attribute "BasicEligibilityRequest"
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth.isoformat(),
                user_id=user_id,
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, basic.__qualname__),
        )
        members = translate.member_list_pb_to_member_list(response)
    except grpc.RpcError as e:
        _record_grpc_error(e, basic.__qualname__)
        return None
    return members


def healthplan(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    first_name: str,
    last_name: str,
    date_of_birth: datetime.date,
    *,
    user_id: Optional[int] = None,
    subscriber_id: Optional[str] = None,
    dependent_date_of_birth: Optional[datetime.date] = None,
    employee_first_name: Optional[str] = None,
    employee_last_name: Optional[str] = None,
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> model.EligibilityMember | None:
    if not grpc_connection:
        logger.info("passed null connection to grpc endpoint", method="standard")
        grpc_connection = channel()
    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)
    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        dependent_date_of_birth_str = (
            dependent_date_of_birth.isoformat()
            if dependent_date_of_birth is not None
            else ""
        )
        response: e9ypb.Member = stub.CheckHealthPlanEligibility(  # type: ignore[name-defined, valid-type] # Name "e9ypb.Member" is not defined
            request=e9ypb.HealthPlanEligibilityRequest(  # type: ignore[attr-defined] # Module has no attribute "HealthPlanEligibilityRequest"
                subscriber_id=subscriber_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth.isoformat(),
                dependent_date_of_birth=dependent_date_of_birth_str,
                employee_first_name=employee_first_name,
                employee_last_name=employee_last_name,
                user_id=user_id,
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, healthplan.__qualname__),
        )
        member = translate.member_pb_to_member(response)
    except grpc.RpcError as e:
        _record_grpc_error(e, healthplan.__qualname__)
        return None
    return member


def employer(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    date_of_birth: datetime.date,
    *,
    company_email: Optional[str] = None,
    employee_first_name: Optional[str] = None,
    employee_last_name: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    work_state: Optional[str] = None,
    user_id: Optional[int] = None,
    dependent_date_of_birth: Optional[datetime.date] = None,
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> model.EligibilityMember | None:
    if not grpc_connection:
        logger.info("passed null connection to grpc endpoint", method="standard")
        grpc_connection = channel()
    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)
    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        dependent_date_of_birth = (
            dependent_date_of_birth and dependent_date_of_birth.isoformat()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Union[date, None, str]", variable has type "Optional[date]")
        )
        response: e9ypb.Member = stub.CheckEmployerEligibility(  # type: ignore[name-defined, valid-type] # Name "e9ypb.Member" is not defined
            request=e9ypb.EmployerEligibilityRequest(  # type: ignore[attr-defined] # Module has no attribute "EmployerEligibilityRequest"
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth.isoformat(),
                dependent_date_of_birth=dependent_date_of_birth,
                company_email=company_email,
                work_state=work_state,
                employee_first_name=employee_first_name,
                employee_last_name=employee_last_name,
                user_id=user_id,
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, employer.__qualname__),
        )
        member = translate.member_pb_to_member(response)
    except grpc.RpcError as e:
        _record_grpc_error(e, employer.__qualname__)
        return None
    return member


def standard(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    date_of_birth: datetime.date,
    company_email: str,
    *,
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.EligibilityMember]:
    """Search for a Member via 'Standard' eligibility information.

    'Standard' eligibility checks for a matching member given a date of birth and an
    email. 'Standard' eligibility is also referred to 'Primary' verification.

    Parameters:
        date_of_birth <datetime.date>: The date of birth to match against.
        company_email <str>: The email to match against.
        timeout <float, optional>: GRPC call timeout in seconds
    Returns:
        An Eligibility member record, if one is found.
    """
    if not grpc_connection:
        logger.info("passed null connection to grpc endpoint", method="standard")
        grpc_connection = channel()
    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)

    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response: e9ypb.Member = stub.CheckStandardEligibility(  # type: ignore[name-defined, valid-type] # Name "e9ypb.Member" is not defined
            request=e9ypb.StandardEligibilityRequest(  # type: ignore[attr-defined] # Module has no attribute "StandardEligibilityRequest"
                date_of_birth=date_of_birth.isoformat(), company_email=company_email
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, standard.__qualname__),
        )
        member = translate.member_pb_to_member(response)
    except grpc.RpcError as e:
        _record_grpc_error(e, standard.__qualname__)
        return None
    return member


def alternate(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    date_of_birth: datetime.date,
    work_state: Optional[str],
    first_name: str,
    last_name: str,
    *,
    unique_corp_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "unique_corp_id" (default has type "None", argument has type "str")
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.EligibilityMember]:
    """Search for a Member via 'Alternative' eligibility information.

    Parameters:
        date_of_birth <datetime.date>: The date of birth to match against.
        work_state <str>: The state/region of employment. (optional, case-insensitive)
            ISO 3166-2 (2 digit state code) for US, no character limit for International (can be null)
        first_name <str>: The first name to match against. (case-insensitive)
        last_name <str>: The last name to match against. (case-insensitive)
        unique_corp_id <str, optional>: The uniquely-identifying ID provided by the client.
        timeout <float, optional>: GRPC call timeout in seconds
    Returns:
        A Eligibility member record, if one is found.
    """

    if not grpc_connection:
        logger.info("passed null connection to grpc endpoint", method="alternate")
        grpc_connection = channel()
    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)

    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response: e9ypb.Member = stub.CheckAlternateEligibility(  # type: ignore[name-defined, valid-type] # Name "e9ypb.Member" is not defined
            request=e9ypb.AlternateEligibilityRequest(  # type: ignore[attr-defined] # Module has no attribute "AlternateEligibilityRequest"
                date_of_birth=date_of_birth.isoformat(),
                work_state=work_state,
                first_name=first_name,
                last_name=last_name,
                unique_corp_id=unique_corp_id,
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, alternate.__qualname__),
        )
        member = translate.member_pb_to_member(response)
    except grpc.RpcError as e:
        _record_grpc_error(e, alternate.__qualname__)
        return None
    return member


def overeligibility(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    date_of_birth: datetime.date,
    first_name: str,
    last_name: str,
    user_id: int,
    *,
    company_email: str = None,  # type: ignore[assignment] # Incompatible default for argument "company_email" (default has type "None", argument has type "str")
    work_state: str = None,  # type: ignore[assignment] # Incompatible default for argument "work_state" (default has type "None", argument has type "str")
    unique_corp_id: str = None,  # type: ignore[assignment] # Incompatible default for argument "unique_corp_id" (default has type "None", argument has type "str")
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> List[model.EligibilityMember]:
    """Search for a Member via 'Overeligibility' eligibility information.

    Parameters:
        date_of_birth <datetime.date>: The date of birth to match against.
        first_name <str>: The first name to match against. (case-insensitive)
        last_name <str>: The last name to match against. (case-insensitive)
        user_id <int>: The Maven identifier for the user we are trying to verify eligibility against
        company_email <str, optional>: The email provided by the client.
        work_state <str>: The state/region of employment. (optional, case-insensitive)
            ISO 3166-2 (2 digit state code) for US, no character limit for International (can be null)
        unique_corp_id <str, optional>: The uniquely-identifying ID provided by the client.
        timeout <float, optional>: GRPC call timeout in seconds
    Returns:
        Eligibility member record(s), if a match(es) is found.
    """

    if not grpc_connection:
        logger.info("passed null connection to grpc endpoint", method="alternate")
        grpc_connection = channel()
    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)

    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response: e9ypb.Member = stub.CheckEligibilityOverEligibility(  # type: ignore[name-defined, valid-type] # Name "e9ypb.Member" is not defined
            request=e9ypb.EligibilityOverEligibilityRequest(  # type: ignore[attr-defined] # Module has no attribute "EligibilityOverEligibilityRequest"
                date_of_birth=date_of_birth.isoformat(),
                work_state=work_state,
                first_name=first_name,
                last_name=last_name,
                unique_corp_id=unique_corp_id,
                company_email=company_email,
                user_id=str(user_id),
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, alternate.__qualname__),
        )
        members = translate.member_list_pb_to_member_list(response)
    except grpc.RpcError as e:
        _record_grpc_error(e, alternate.__qualname__)
        return None  # type: ignore[return-value] # Incompatible return value type (got "None", expected "List[EligibilityMember]")
    return members


def client_specific(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    date_of_birth: datetime.date,
    unique_corp_id,
    organization_id: int,
    is_employee: bool,
    *,
    dependent_date_of_birth: Optional[datetime.date] = None,
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.EligibilityMember]:
    """Search for a Member via 'Client-Specific' eligibility information.

    Parameters:
        date_of_birth <datetime.date>: The employee date of birth to match against.
        unique_corp_id <str>: The unique corp id to match against.
        organization_id <int>: The organization to match against.
        is_employee <bool>: Whether the member is an employee of a client or benificiary thereof.
        dependent_date_of_birth <datetime.date, optional>: The benificiary date of birth to match against.
        timeout <float, optional>: GRPC call timeout in seconds
    Returns:
        An Eligibility member record, if one is found.
    """

    dependent_date_of_birth = (
        dependent_date_of_birth and dependent_date_of_birth.isoformat()  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Union[date, None, str]", variable has type "Optional[date]")
    )

    if not grpc_connection:
        logger.info("passed null connection to grpc endpoint", method="client_specific")
        grpc_connection = channel()

    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)
    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response: e9ypb.Member = stub.CheckClientSpecificEligibility(  # type: ignore[name-defined, valid-type] # Name "e9ypb.Member" is not defined
            request=e9ypb.ClientSpecificEligibilityRequest(  # type: ignore[attr-defined] # Module has no attribute "ClientSpecificEligibilityRequest"
                date_of_birth=date_of_birth.isoformat(),
                dependent_date_of_birth=dependent_date_of_birth,
                unique_corp_id=unique_corp_id,
                organization_id=organization_id,
                is_employee=is_employee,
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, client_specific.__qualname__),
        )
        member = translate.member_pb_to_member(response)
    except grpc.RpcError as e:
        _record_grpc_error(e, client_specific.__qualname__)
        return None
    return member


def no_dob_verification(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    email: str,
    first_name: str,
    last_name: str,
    *,
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.EligibilityMember]:
    """Search for a Member via 'No DOB' eligibility information.

    Parameters:
        email <str>: The email address to match against.
        first_name <str>: The first name to match against. (case-insensitive)
        last_name <str>: The last name to match against. (case-insensitive)
        timeout <float, optional>: GRPC call timeout in seconds
    Returns:
        A Eligibility member record, if one is found.
    """

    if not grpc_connection:
        logger.info("passed null connection to grpc endpoint", method="no-dob")
        grpc_connection = channel()
    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)

    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response: e9ypb.Member = stub.CheckNoDOBEligibility(  # type: ignore[name-defined, valid-type] # Name "e9ypb.Member" is not defined
            request=e9ypb.NoDOBEligibilityRequest(  # type: ignore[attr-defined] # Module has no attribute "NoDOBEligibilityRequest"
                email=email,
                first_name=first_name,
                last_name=last_name,
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, no_dob_verification.__qualname__),
        )
        member = translate.member_pb_to_member(response)
    except grpc.RpcError as e:
        _record_grpc_error(e, no_dob_verification.__qualname__)
        return None
    return member


def member_id_search(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    member_id: int,
    *,
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.EligibilityMember]:
    """Search for an eligibility member using their eligibility user ID

    Parameters:
        member_id <int>: The Eligibility ID used to refer to an individual (maps to eligibility.member.id)
        timeout <float, optional>: GRPC call timeout in seconds

    Returns:
        A Eligibility record, if one is found.
    """
    if not grpc_connection:
        logger.info(
            "passed null connection to grpc endpoint", method="member_id_search"
        )
        grpc_connection = channel()

    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)
    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response: e9ypb.Member = stub.GetMemberById(  # type: ignore[name-defined, valid-type] # Name "e9ypb.Member" is not defined
            request=e9ypb.MemberIdRequest(id=member_id),  # type: ignore[attr-defined] # Module has no attribute "MemberIdRequest"
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, member_id_search.__qualname__),
        )
        member = translate.member_pb_to_member(response)
    except grpc.RpcError as e:
        _record_grpc_error(e, member_id_search.__qualname__)
        return None
    return member


def org_identity_search(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    unique_corp_id: str,
    dependent_id: str,
    organization_id: int,
    *,
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.EligibilityMember]:
    """Search for a member via an 'Org-Identity'

    An 'Org-Identity' is a unique, composite key based on the Organization's ID and
    the eligibility member record's `unique_corp_id` & `dependent_id`.

    Parameters:
        unique_corp_id <str>: The unique corp id to match against.
        dependent_id <str>: The dependent id to match against.
        organization_id <str>: The organization to match against.
        timeout <float, optional>: GRPC call timeout in seconds

    Returns:
        An eligibility member record, if one is found.
    """

    if not grpc_connection:
        logger.info(
            "passed null connection to grpc endpoint", method="org_identity_search"
        )
        grpc_connection = channel()

    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)
    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response: e9ypb.Member = stub.GetMemberByOrgIdentity(  # type: ignore[name-defined, valid-type] # Name "e9ypb.Member" is not defined
            request=e9ypb.OrgIdentityRequest(  # type: ignore[attr-defined] # Module has no attribute "OrgIdentityRequest"
                organization_id=organization_id,
                unique_corp_id=unique_corp_id,
                dependent_id=dependent_id,
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, org_identity_search.__qualname__),
        )
        member = translate.member_pb_to_member(response)
    except grpc.RpcError as e:
        _record_grpc_error(e, org_identity_search.__qualname__)
        return None
    return member


def member_search(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user_id: int,
    first_name: str,
    last_name: str,
    date_of_birth: datetime.date,
    *,
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.PreEligibilityResponse]:
    """Search for e9y member based on member_id, first_name, last_name and date_of birth

    search response includes whether there is a potential or existing member and the associated organizations

    Parameter:
      user_id : user id associated with the individual
      first_name: first name of the individual
      last_name: last name of the individual
      date_of_birth: date of birth of the individual
      timeout <float, optional>: GRPC call timeout in seconds

    Returns:
      response indicating whether a member was found and their organization details
    """

    if not grpc_connection:
        logger.info("passed null connection to grpc endpoint", method="member_search")
        grpc_connection = channel()

    stub = pre9ygrpc.PreEligibilityServiceStub(grpc_connection)
    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response: pre9ypb.PreEligibilityResponse = stub.CheckPreEligibility(  # type: ignore[valid-type] # Variable "maven_schemas.eligibility.pre_eligibility_pb2.PreEligibilityResponse" is not valid as a type
            request=pre9ypb.PreEligibilityRequest(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth.isoformat(),
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, member_search.__qualname__),
        )
        translated_response = translate.pre_eligibility_pb_to_pre_eligibility(response)
    except grpc.RpcError as e:
        _record_grpc_error(e, member_search.__qualname__)
        return None
    return translated_response


def wallet_enablement_by_id_search(
    member_id: int,
    *,
    timeout: Optional[float] = None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.WalletEnablement]:
    """Search for a wallet enablement configuration for the provided eligibility Member ID.

    A "wallet enablement" is a set of configuration values provided to us at the
    member-level by an organization which allows or dis-allows a user to access our
    Maven Wallet product.

    Note- record returned is not guaranteed to be active- you must look at the record itself to determine
    if it represents an eligible user's data. We may return historical data.

    Parameter:
      member_id <int>: The Eligibility ID used to refer to an individual (maps to eligibility.member.id)
      timeout <float, optional>: GRPC call timeout in seconds

    Returns:
      A WalletEnablement, if one is found.
    """

    with channel() as conn:
        stub = e9ygrpc.EligibilityServiceStub(conn)
        try:
            metadata = metadata if metadata is not None else get_trace_metadata()
            response: e9ypb.WalletEnablement = stub.GetWalletEnablementById(  # type: ignore[name-defined, valid-type] # Name "e9ypb.WalletEnablement" is not defined
                request=e9ypb.MemberIdRequest(id=member_id),  # type: ignore[attr-defined] # Module has no attribute "MemberIdRequest"
                metadata=metadata,
                timeout=_get_effective_timeout(
                    timeout, wallet_enablement_by_id_search.__qualname__
                ),
            )
            enablement = translate.wallet_pb_to_wallet(response)
        except grpc.RpcError as e:
            _record_grpc_error(e, wallet_enablement_by_id_search.__qualname__)
            return None
        return enablement


def wallet_enablement_by_user_id_search(
    user_id: int,
    *,
    timeout: Optional[float] = None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.WalletEnablement]:
    """Search for a wallet enablement configuration for the provided Maven user ID.

    A "wallet enablement" is a set of configuration values provided to us at the
    member-level by an organization which allows or dis-allows a user to access our
    Maven Wallet product.

    Note- record returned is not guaranteed to be active- you must look at the record itself to determine
    if it represents an eligible user's data. We may return historical data.

    Parameter:
      member_id <int>: The Eligibility ID used to refer to an individual (maps to eligibility.member.id)
      timeout <float, optional>: GRPC call timeout in seconds

    Returns:
      A WalletEnablement, if one is found.
    """

    with channel() as conn:
        stub = e9ygrpc.EligibilityServiceStub(conn)
        try:
            metadata = metadata if metadata is not None else get_trace_metadata()
            response: e9ypb.WalletEnablement = stub.GetWalletEnablementByUserId(  # type: ignore[name-defined, valid-type] # Name "e9ypb.WalletEnablement" is not defined
                request=e9ypb.UserIdRequest(id=user_id),  # type: ignore[attr-defined] # Module has no attribute "UserIdRequest"
                metadata=metadata,
                timeout=_get_effective_timeout(
                    timeout, wallet_enablement_by_user_id_search.__qualname__
                ),
            )
            enablement = translate.wallet_pb_to_wallet(response)
        except grpc.RpcError as e:
            _record_grpc_error(e, wallet_enablement_by_user_id_search.__qualname__)
            return None
        return enablement


def wallet_enablement_by_org_identity_search(
    unique_corp_id: str,
    dependent_id: str,
    organization_id: int,
    *,
    timeout: Optional[float] = None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.WalletEnablement]:
    """Search for a wallet enablement using an org identity.

    An 'Org-Identity' is a unique, composite key based on the Organization's ID and
    the eligibility member record's `unique_corp_id` & `dependent_id`.

    Note- record returned is not guaranteed to be active- you must look at the record itself to determine
    if it represents an eligible user's data. We may return historical data.

    Parameters:
        unique_corp_id <str>: The unique_corp_id of the member record.
        dependent_id <str>: The dependent_id of the member record.
        organization_id <str>: The ID of the organization this record should belong to.
        timeout <float, optional>: GRPC call timeout in seconds

    Returns:
        A WalletEnablement, if one is found.
    """

    with channel() as conn:
        stub = e9ygrpc.EligibilityServiceStub(conn)
        try:
            metadata = metadata if metadata is not None else get_trace_metadata()
            response: e9ypb.WalletEnablement = stub.GetWalletEnablementByOrgIdentity(  # type: ignore[name-defined, valid-type] # Name "e9ypb.WalletEnablement" is not defined
                request=e9ypb.OrgIdentityRequest(  # type: ignore[attr-defined] # Module has no attribute "OrgIdentityRequest"
                    organization_id=organization_id,
                    unique_corp_id=unique_corp_id,
                    dependent_id=dependent_id,
                ),
                metadata=metadata,
                timeout=_get_effective_timeout(
                    timeout, wallet_enablement_by_org_identity_search.__qualname__
                ),
            )
            enablement = translate.wallet_pb_to_wallet(response)
        except grpc.RpcError as e:
            _record_grpc_error(e, wallet_enablement_by_org_identity_search.__qualname__)
            return None
        return enablement


def get_eligible_features_for_user(
    user_id: int,
    feature_type: int,
    *,
    timeout: Optional[float] = None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.EligibleFeaturesForUserResponse]:
    """Get eligible features from e9y for the user

    Parameters:
      user_id <int>: id of the user
      feature_type <int>: the type of feature we are looking up
      timeout <float, optional>: GRPC call timeout in seconds

    Returns:
      response contains an integer list of features (ids) associated with the user
    """

    with channel() as conn:
        stub = e9ygrpc.EligibilityServiceStub(conn)
        try:
            metadata = metadata if metadata is not None else get_trace_metadata()
            response: e9ypb.GetEligibleFeaturesForUserResponse = stub.GetEligibleFeaturesForUser(  # type: ignore[name-defined, valid-type] # Name "e9ypb.GetEligibleFeaturesForUserResponse" is not defined
                request=e9ypb.GetEligibleFeaturesForUserRequest(  # type: ignore[attr-defined] # Module has no attribute "GetEligibleFeaturesForUserRequest"
                    user_id=user_id,
                    feature_type=feature_type,
                ),
                metadata=metadata,
                timeout=_get_effective_timeout(
                    timeout, get_eligible_features_for_user.__qualname__
                ),
            )
            translated_response = translate.eligible_features_for_user_pb_to_eligible_features_for_user_response(
                response
            )
        except grpc.RpcError as e:
            _record_grpc_error(e, get_eligible_features_for_user.__qualname__)
            return None
        return translated_response


def get_eligible_features_for_user_and_org(
    user_id: int,
    organization_id: int,
    feature_type: int,
    *,
    timeout: Optional[float] = None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.EligibleFeaturesForUserAndOrgResponse]:
    """Get eligible features from e9y for the user and org

    Parameters:
      user_id <int>: id of the user
      organization_id <int>: ID of the organization this record should belong to.
      feature_type <int>: the type of feature we are looking up
      timeout <float, optional>: GRPC call timeout in seconds

    Returns:
      response contains an integer list of features (ids) associated with the user and org
    """

    with channel() as conn:
        stub = e9ygrpc.EligibilityServiceStub(conn)
        try:
            metadata = metadata if metadata is not None else get_trace_metadata()
            response: e9ypb.GetEligibleFeaturesForUserAndOrgResponse = stub.GetEligibleFeaturesForUserAndOrg(  # type: ignore[name-defined, valid-type] # Name "e9ypb.GetEligibleFeaturesForUserAndOrgResponse" is not defined
                request=e9ypb.GetEligibleFeaturesForUserAndOrgRequest(  # type: ignore[attr-defined] # Module has no attribute "GetEligibleFeaturesForUserAndOrgRequest"
                    user_id=user_id,
                    organization_id=organization_id,
                    feature_type=feature_type,
                ),
                metadata=metadata,
                timeout=_get_effective_timeout(
                    timeout, get_eligible_features_for_user_and_org.__qualname__
                ),
            )
            translated_response = translate.eligible_features_for_user_and_org_pb_to_eligible_features_for_user_and_org_response(
                response
            )
        except grpc.RpcError as e:
            _record_grpc_error(e, get_eligible_features_for_user_and_org.__qualname__)
            return None
        return translated_response


def get_eligible_features_by_sub_population_id(
    sub_population_id: int,
    feature_type: int,
    *,
    timeout: Optional[float] = None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[model.EligibleFeaturesBySubPopulationIdResponse]:
    """Get eligible features from e9y for the sub-population

    Parameters:
      sub_population_id <int>: id of the sub-population
      feature_type <int>: the type of feature we are looking up
      timeout <float, optional>: GRPC call timeout in seconds

    Returns:
      response contains an integer list of features (ids) associated with the user
    """

    with channel() as conn:
        stub = e9ygrpc.EligibilityServiceStub(conn)
        try:
            metadata = metadata if metadata is not None else get_trace_metadata()
            response: e9ypb.GetEligibleFeaturesBySubPopulationIdResponse = stub.GetEligibleFeaturesBySubPopulationId(  # type: ignore[name-defined, valid-type] # Name "e9ypb.GetEligibleFeaturesBySubPopulationIdResponse" is not defined
                request=e9ypb.GetEligibleFeaturesBySubPopulationIdRequest(  # type: ignore[attr-defined] # Module has no attribute "GetEligibleFeaturesBySubPopulationIdRequest"
                    sub_population_id=sub_population_id,
                    feature_type=feature_type,
                ),
                metadata=metadata,
                timeout=_get_effective_timeout(
                    timeout, get_eligible_features_by_sub_population_id.__qualname__
                ),
            )
            translated_response = translate.eligible_features_by_sub_population_id_pb_to_eligible_features_by_sub_population_id_response(
                response
            )
        except grpc.RpcError as e:
            _record_grpc_error(
                e, get_eligible_features_by_sub_population_id.__qualname__
            )
            return None
        return translated_response


def get_sub_population_id_for_user(
    user_id: int,
    *,
    timeout: Optional[float] = None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[Int64Value]:
    """Gets the sub-population Id of the user

    Parameters:
      user_id <int>: id of the user
      timeout <float, optional>: GRPC call timeout in seconds

    Returns:
      response contains an integer ID of the sub-population that the user belongs to,
      or a None if the user is not in an organization or if that organization does not
      have an active population.
    """
    with channel() as conn:
        stub = e9ygrpc.EligibilityServiceStub(conn)
        try:
            metadata = metadata if metadata is not None else get_trace_metadata()
            response: e9ypb.GetSubPopulationIdForUserResponse = stub.GetSubPopulationIdForUser(  # type: ignore[name-defined, valid-type] # Name "e9ypb.GetSubPopulationIdForUserResponse" is not defined
                request=e9ypb.GetSubPopulationIdForUserRequest(  # type: ignore[attr-defined] # Module has no attribute "GetSubPopulationIdForUserRequest"
                    user_id=user_id,
                ),
                metadata=metadata,
                timeout=_get_effective_timeout(
                    timeout, get_sub_population_id_for_user.__qualname__
                ),
            )
            if response.HasField("sub_population_id"):  # type: ignore[attr-defined]
                return response.sub_population_id  # type: ignore[attr-defined]
            else:
                return None
        except grpc.RpcError as e:
            _record_grpc_error(e, get_sub_population_id_for_user.__qualname__)
        return None


def get_sub_population_id_for_user_and_org(
    user_id: int,
    organization_id: int,
    *,
    timeout: Optional[float] = None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Optional[Int64Value]:
    """Gets the sub-population Id of the user and org

    Parameters:
      user_id <int>: id of the user
      organization_id <int>: id of the organization
      timeout <float, optional>: GRPC call timeout in seconds

    Returns:
      response contains an integer ID of the sub-population that the user belongs to for a specified organization,
      or a None if the user is not in that organization or if that organization does not
      have an active population.
    """
    with channel() as conn:
        stub = e9ygrpc.EligibilityServiceStub(conn)
        try:
            metadata = metadata if metadata is not None else get_trace_metadata()
            response: e9ypb.GetSubPopulationIdForUserAndOrgResponse = stub.GetSubPopulationIdForUserAndOrg(  # type: ignore[name-defined, valid-type] # Name "e9ypb.GetSubPopulationIdForUserAndOrgResponse" is not defined
                request=e9ypb.GetSubPopulationIdForUserAndOrgRequest(  # type: ignore[attr-defined] # Module has no attribute "GetSubPopulationIdForUserAndOrgRequest"
                    user_id=user_id,
                    organization_id=organization_id,
                ),
                metadata=metadata,
                timeout=_get_effective_timeout(
                    timeout, get_sub_population_id_for_user_and_org.__qualname__
                ),
            )
            if response.HasField("sub_population_id"):  # type: ignore[attr-defined]
                return response.sub_population_id  # type: ignore[attr-defined]
            else:
                return None
        except grpc.RpcError as e:
            _record_grpc_error(e, get_sub_population_id_for_user_and_org.__qualname__)
        return None


def get_other_user_ids_in_family(
    user_id: int,
    *,
    timeout: Optional[float] = None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> List[int]:
    """Gets the other active user_id's for a "family" as defined by a shared "unique_corp_id"

    Parameters:
      user_id <int>: id of the user
      timeout <float, optional>: GRPC call timeout in seconds

    Returns:
      A list of user_id's, does not include the input user's own user_id
    """
    with channel() as conn:
        stub = e9ygrpc.EligibilityServiceStub(conn)
        try:
            metadata = metadata if metadata is not None else get_trace_metadata()
            response: e9ypb.GetOtherUserIdsInFamilyResponse = stub.GetOtherUserIdsInFamily(  # type: ignore[name-defined, valid-type] # Name "e9ypb.GetOtherUserIdsInFamilyResponse" is not defined
                request=e9ypb.GetOtherUserIdsInFamilyRequest(  # type: ignore[attr-defined] # Module has no attribute "GetOtherUserIdsInFamilyRequest"
                    user_id=user_id,
                ),
                metadata=metadata,
                timeout=_get_effective_timeout(
                    timeout, get_other_user_ids_in_family.__qualname__
                ),
            )
            user_ids: List[int] = response.user_ids  # type: ignore[attr-defined]
        except grpc.RpcError as e:
            _record_grpc_error(e, get_other_user_ids_in_family.__qualname__)
            return []
        return user_ids


def create_verification(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user_id: int,
    verification_type: str,
    organization_id: int,
    *,
    unique_corp_id: str | None = "",
    dependent_id: str | None = "",
    first_name: str | None = "",
    last_name: str | None = "",
    email: str | None = "",
    work_state: str | None = "",
    date_of_birth: datetime.date | None = None,
    eligibility_member_id: int | None = None,
    additional_fields: dict | None = None,
    verified_at: datetime.datetime | None = None,
    deactivated_at: datetime.datetime | None = None,
    timeout: Optional[float] = None,
    verification_session: str | None = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Tuple[model.EligibilityVerification, None] | Tuple[None, grpc.RpcError]:
    """ "Generate a new verification record in the eligibility database for a user.

    Parameters:
        user_id (int): The user ID associated with a Maven member
        verification_type (str): The type of verification flow used
        organization_id (int): The ID of the organization this record should belong to
        unique_corp_id (str, optional): The unique_corp_id of the member record
        dependent_id (str, optional): The dependent_id used to verify a user
        first_name (str, optional): The first name used to verify a user
        last_name (str, optional): The last name used to verify a user
        email (str, optional): The email used to verify a user
        work_state (str, optional): The state used to verify a user
        date_of_birth (datetime.date, optional): The date used to verify a member
        eligibility_member_id (int, optional): The ID of the e9y record used for verification
        additional_fields (dict, optional): Additional non-standard verification values
        verified_at (datetime.datetime, optional): When verification was performed
        deactivated_at (datetime.datetime, optional): When verification became inactive
        timeout (float, optional): GRPC call timeout in seconds
        verification_session (str, optional): Verification session identifier
        grpc_connection: The gRPC connection to use
        metadata: The metadata to include with the gRPC call

    Returns:
        Tuple containing either:
        - An EligibilityVerification record and None
        - None and a gRPC RpcError if the call failed
    """
    # Prepare connection and defaults
    grpc_connection = grpc_connection or channel()
    verification_session = verification_session or str(uuid.uuid4())
    metadata = metadata or get_trace_metadata()

    # Log verification attempt
    logger.info(
        "Creating verification",
        user_id=user_id,
        verification_type=verification_type,
        organization_id=organization_id,
        eligibility_member_id=eligibility_member_id,
    )

    # Prepare request data
    request_kwargs = {
        "user_id": str(user_id),
        "eligibility_member_id": str(eligibility_member_id)
        if eligibility_member_id is not None
        else "",
        "organization_id": organization_id,
        "verification_type": verification_type,
        "unique_corp_id": unique_corp_id or "",
        "dependent_id": str(dependent_id) if dependent_id is not None else "",
        "first_name": first_name or "",
        "last_name": last_name or "",
        "date_of_birth": str(date_of_birth) if date_of_birth else "",
        "email": email or "",
        "work_state": work_state or "",
        "additional_fields": json.dumps(additional_fields) if additional_fields else "",
        "verified_at": str(
            verified_at or datetime.datetime.now(tz=datetime.timezone.utc)
        ),
        "deactivated_at": str(deactivated_at) if deactivated_at else "",
        "verification_session": verification_session,
    }

    # Execute gRPC call with retry
    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)
    result = _retry_grpc_call(
        stub.CreateVerificationForUser,
        request=e9ypb.CreateVerificationForUserRequest(**request_kwargs),
        metadata=metadata,
        timeout=_get_effective_timeout(timeout, create_verification.__qualname__),
    )

    if result is None:
        logger.error(
            "Failed to create verification after multiple retries",
            user_id=user_id,
            eligibility_member_id=eligibility_member_id,
            organization_id=organization_id,
        )
        return None, grpc.RpcError(grpc.StatusCode.UNAVAILABLE, "Failed after retries")

    # Translate and return result
    try:
        verification = translate.verification_for_user_pb_to_eligibility_verification(
            result
        )
        return verification, None
    except Exception as e:
        logger.error(
            "Error processing verification response",
            error=str(e),
            user_id=user_id,
            eligibility_member_id=eligibility_member_id,
            organization_id=organization_id,
        )
        return None, grpc.RpcError(
            grpc.StatusCode.INTERNAL, "Response processing error"
        )


def _retry_grpc_call(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    error_codes_for_retry: Set[grpc.StatusCode] = None,  # type: ignore[assignment] # Incompatible default for argument "error_codes_for_retry" (default has type "None", argument has type "set[Any]")
    **kwargs,
) -> Any:
    """
    Retries a gRPC call with exponential backoff and jitter.

    Args:
        func: The gRPC function to call
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        retriable_codes: Set of gRPC status codes to retry
        **kwargs: Arguments to pass to the gRPC function
    """
    error_codes_for_retry = error_codes_for_retry or {
        grpc.StatusCode.UNAVAILABLE,
        grpc.StatusCode.DEADLINE_EXCEEDED,
    }

    retries = 0
    delay = initial_delay

    while retries < max_retries:
        try:
            return func(**kwargs)

        except grpc.RpcError as e:
            # Only retry on specified status codes
            if e.code() not in error_codes_for_retry:
                raise

            # Add tracing for retry
            span = ddtrace.tracer.current_span()
            if span:
                span.set_tag("error", True)
                span.set_tag("error.type", "grpc.RpcError")
                span.set_tag(
                    "error.msg",
                    f"gRPC call failed with {e.code()}. Retry {retries + 1}",
                )
                span.set_tag("grpc.status_code", e.code().value)

            # Log retry attempt
            logger.warning(
                f"gRPC call failed with {e.code()}. Retry {retries + 1}/{max_retries}. "
                f"Waiting {delay:.2f} seconds."
            )

            # Exit if max retries reached
            if retries == max_retries:
                logger.error("Max retries reached. Giving up.")
                return None

            # Add jitter to prevent synchronized retries
            jitter = random.uniform(0.8, 1.2)
            time.sleep(min(delay * jitter, max_delay))

            # Exponential backoff with jitter
            delay = min(delay * 2, max_delay)
            retries += 1

    return None


def create_multiple_verifications_for_user(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user_id: int,
    verification_type: str,
    *,
    verification_data_list: List[model.VerificationData],
    first_name: str | None = "",
    last_name: str | None = "",
    date_of_birth: datetime.date | None = None,
    verified_at: datetime.datetime | None = None,
    deactivated_at: datetime.datetime | None = None,
    timeout: Optional[float] = None,
    verification_session: str | None = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> Tuple[List[model.EligibilityVerification], None] | Tuple[None, grpc.RpcError]:
    """Creates a multiple verification records for a user.

    Parameters:
    - user_id: The ID of the user to create verifications for.
    - verification_type: The type of verification to perform.
    - verification_data_list: A list of verification data for each member.
    - first_name: The user's first name.
    - last_name: The user's last name.
    - date_of_birth: The user's date of birth.
    - verified_at: The datetime when the verification was completed.
    - deactivated_at: The datetime when the verification was deactivated.
    - timeout: The gRPC call timeout.
    - verification_session: The verification session identifier.
    - grpc_connection: The gRPC connection to use.
    - metadata: The metadata to include with the gRPC call.

    Returns:
    A tuple containing either:
    - A list of EligibilityVerification objects and None.
    - None and a gRPC RpcError if the call failed.
    """

    # Validate input
    if not verification_data_list:
        logger.error("No verification data provided")
        return None, grpc.RpcError(
            grpc.StatusCode.INVALID_ARGUMENT, "Empty verification data"
        )

    # Prepare connection and defaults
    grpc_connection = grpc_connection or channel()
    verification_session = verification_session or str(uuid.uuid4())
    metadata = metadata or get_trace_metadata()

    # Extract metadata for logging
    eligibility_member_ids = [
        verification_data.eligibility_member_id
        for verification_data in verification_data_list
    ]
    organization_ids = [
        verification_data.organization_id
        for verification_data in verification_data_list
    ]

    # Log additional context
    logger.info(
        "Creating multiple verifications",
        user_id=user_id,
        verification_type=verification_type,
        eligibility_member_ids=eligibility_member_ids,
        organization_ids=organization_ids,
        verification_count=len(verification_data_list),
    )

    # Prepare verification data
    try:
        verification_data_pb_list = [
            _prepare_verification_data_pb(vdata) for vdata in verification_data_list
        ]
    except ValueError as e:
        logger.error(f"Invalid verification data: {e}")
        return None, grpc.RpcError(grpc.StatusCode.INVALID_ARGUMENT, str(e))

    # Prepare request
    request_kwargs = {
        "user_id": Int64Value(value=user_id),
        "verification_type": verification_type,
        "verification_data_list": verification_data_pb_list,
        "first_name": first_name or "",
        "last_name": last_name or "",
        "date_of_birth": str(date_of_birth) if date_of_birth else "",
        "verified_at": str(
            verified_at or datetime.datetime.now(tz=datetime.timezone.utc)
        ),
        "deactivated_at": str(deactivated_at) if deactivated_at else "",
        "verification_session": verification_session,
    }

    # Execute gRPC call with retry
    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)
    result = _retry_grpc_call(
        stub.CreateMultipleVerificationsForUser,
        request=e9ypb.CreateMultipleVerificationsForUserRequest(**request_kwargs),
        metadata=metadata,
        timeout=_get_effective_timeout(
            timeout, create_multiple_verifications_for_user.__qualname__
        ),
    )

    if result is None:
        logger.error("Failed to create verifications after multiple retries")
        return None, grpc.RpcError(grpc.StatusCode.UNAVAILABLE, "Failed after retries")

    # Translate and return results
    try:
        verifications = [
            translate.verification_for_user_pb_to_eligibility_verification(v)
            for v in result.verification_list
        ]
        return verifications, None
    except Exception as e:
        logger.error(
            "Error processing verification response",
            error=str(e),
            user_id=user_id,
            eligibility_member_ids=eligibility_member_ids,
            organization_ids=organization_ids,
        )
        return None, grpc.RpcError(
            grpc.StatusCode.INTERNAL, "Response processing error"
        )


def _prepare_verification_data_pb(
    verification_data: model.VerificationData,
) -> e9ypb.VerificationData:  # type: ignore[valid-type] # is not valid as a type
    """Helper to prepare verification data protobuf."""

    # Handle None eligibility_member_id safely
    eligibility_member_id_value = None
    if verification_data.eligibility_member_id is not None:
        eligibility_member_id_value = Int64Value(
            value=verification_data.eligibility_member_id
        )

    return e9ypb.VerificationData(
        eligibility_member_id=eligibility_member_id_value,
        organization_id=verification_data.organization_id,
        unique_corp_id=verification_data.unique_corp_id or "",
        dependent_id=str(verification_data.dependent_id or ""),
        email=verification_data.email or "",
        work_state=verification_data.work_state or "",
        additional_fields=json.dumps(verification_data.additional_fields or {}),
    )


def _get_service_stub(
    method_name: str, *, grpc_connection: grpc.Channel | None = None
) -> e9ygrpc.EligibilityServiceStub:
    if not grpc_connection:
        logger.info("passed null connection to grpc endpoint", method=method_name)
        grpc_connection = channel()

    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)
    return stub


def get_all_verifications(
    user_id: int,
    *,
    organization_ids: List[int] | None = None,
    active_verifications_only: bool | None = None,
    timeout: Optional[float] = None,
    grpc_connection: grpc.Channel | None = None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> List[model.EligibilityVerification]:

    if organization_ids is None:
        organization_ids = []
    stub = _get_service_stub(
        get_all_verifications.__name__, grpc_connection=grpc_connection
    )
    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response = e9ypb.VerificationList = stub.GetAllVerificationsForUser(  # type: ignore[attr-defined] # Module has no attribute "Verification"
            request=e9ypb.GetAllVerificationsForUserRequest(  # type: ignore[attr-defined] # Module has no attribute "GetVerificationForUserRequest"
                user_id=user_id,
                organization_ids=organization_ids,
                active_verifications_only=active_verifications_only,
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, get_all_verifications.__qualname__),
        )
        verifications = [
            translate.verification_for_user_pb_to_eligibility_verification(re)
            for re in response.verification_list
        ]
    except grpc.RpcError as e:
        _record_grpc_error(e, get_all_verifications.__qualname__)
        logger.error("Unable to retrieve all verifications for user", user_id=user_id)
        return []

    return verifications


def get_verification(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user_id: int,
    organization_id: int | None = None,
    active_eligibility_only: bool | None = False,
    *,
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> model.EligibilityVerification | None:
    """Retrieve the most recent verification for a user

    Parameters:
        user_id <int>: The user ID associated with a Maven member
        timeout <float, optional>: GRPC call timeout in seconds
        organization_id <int: optional> : Organization to filter verifications to
        active_eligibility_only <bool:optional> : Filter returned verifications by those with a valid E9y record

    Returns:
        A EligibilityVerification record
    """

    if not grpc_connection:
        logger.info(
            "passed null connection to grpc endpoint", method="get_verification"
        )
        grpc_connection = channel()

    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)

    organization_id = str(organization_id) if organization_id is not None else ""  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", variable has type "Optional[int]")

    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response = e9ypb.Verification = stub.GetVerificationForUser(  # type: ignore[attr-defined] # Module has no attribute "Verification"
            request=e9ypb.GetVerificationForUserRequest(  # type: ignore[attr-defined] # Module has no attribute "GetVerificationForUserRequest"
                user_id=user_id,
                organization_id=organization_id,
                active_verifications_only=active_eligibility_only,
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(timeout, get_verification.__qualname__),
        )
        verification = translate.verification_for_user_pb_to_eligibility_verification(
            response
        )
    except grpc.RpcError as e:
        _record_grpc_error(e, get_verification.__qualname__)
        logger.error("Unable to retrieve verification for user", user_id=user_id)
        return None

    return verification


def deactivate_verification(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user_id: int,
    verification_id: int,
    *,
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> model.EligibilityVerification | None:
    """Deactivate a verification given a userID/verificationID

    Parameters:
        user_id <int>: The user ID associated with a Maven member
        timeout <float, optional>: GRPC call timeout in seconds
        verification_id <int> : Verification ID to delete

    Returns:
        A EligibilityVerification record
    """

    if not grpc_connection:
        logger.info(
            "passed null connection to grpc endpoint", method="deactivate_verification"
        )
        grpc_connection = channel()

    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)

    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response = e9ypb.Verification = stub.DeactivateVerificationForUser(  # type: ignore[attr-defined] # Module has no attribute "Verification"
            request=e9ypb.DeactivateVerificationForUserRequest(  # type: ignore[attr-defined] # Module has no attribute "DeactivateVerificationForUserRequest"
                user_id=user_id, verification_id=verification_id
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(
                timeout, deactivate_verification.__qualname__
            ),
        )
        verification = translate.verification_for_user_pb_to_eligibility_verification(
            response
        )
    except grpc.RpcError as e:
        _record_grpc_error(e, get_verification.__qualname__)
        logger.error(
            "Unable to deactivate verification for user",
            user_id=user_id,
            verification_id=verification_id,
        )
        return None

    return verification


def create_failed_verification_attempt(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    user_id: int,
    verification_type: str,
    *,
    organization_id: int | None = None,
    unique_corp_id: str | None = "",
    dependent_id: str | None = "",
    first_name: str | None = "",
    last_name: str | None = "",
    email: str | None = "",
    work_state: str | None = "",
    date_of_birth: datetime.date | None = None,
    eligibility_member_id: int | None = None,
    additional_fields: dict | None = None,
    policy_used: str | None = None,
    verified_at: datetime.datetime | None = None,
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> model.EligibilityVerificationAttempt | None:
    """Generate a record for a failed verification attempt in the eligibility database for a user

    Parameters:
        user_id <int>: The user ID associated with a Maven member
        verification_type <str>: The type of verification flow that was used to verify a member
        organization_id <str>: The ID of the organization this record should belong to.
        unique_corp_id <str>: The unique_corp_id of the member record.
        date_of_birth <datetime.date> The date used to verify a member.
        dependent_id <str>: The dependent_id used to verify a user. Defaults to blank value.
        first_name <str>: The first name used to verify a user. Defaults to blank value.
        last_name <str>: The last name used to verify a user. Defaults to a blank value.
        email <str>: The email used to verify a user. Defaults to a blank value.
        work_state <str>: The state used to verify a user. Defaults to a blank value.
        eligibility_member_id <int>: The ID associated with the e9y record used to verify a user, if e9y data was used during verification. Defaults to null value.
        additional_fields <dict>: Dictionary holding any non-standard values used in generating a verification ex) is_employee
        verified_at <datetime.datetime> The date we attempted to perform verification
        policy_used <str>: (Optional) The policy we tried to verify a user against
        timeout <float, optional>: GRPC call timeout in seconds

    Returns:
        A EligibilityVerification record
    """

    # Cast as a string, as protobuf expects string values here
    user_id_str = str(user_id)

    if organization_id is None:
        organization_id_str = ""
    else:
        organization_id_str = str(organization_id)

    if eligibility_member_id is None:
        eligibility_member_id_str = ""
    else:
        eligibility_member_id_str = str(eligibility_member_id)

    if date_of_birth is None:
        date_of_birth_str = ""
    else:
        date_of_birth_str = str(date_of_birth)

    if verified_at is None:
        verified_at_str = str(datetime.datetime.now(tz=datetime.timezone.utc))
    else:
        verified_at_str = str(verified_at)

    if additional_fields is None:
        additional_fields_str = ""
    else:
        additional_fields_str = json.dumps(additional_fields)

    if not grpc_connection:
        logger.info(
            "passed null connection to grpc endpoint",
            method="create_failed_verification",
        )
        grpc_connection = channel()

    stub = e9ygrpc.EligibilityServiceStub(grpc_connection)
    try:
        metadata = metadata if metadata is not None else get_trace_metadata()
        response = e9ypb.Verification = stub.CreateFailedVerification(  # type: ignore[attr-defined] # Module has no attribute "Verification"
            request=e9ypb.CreateFailedVerificationRequest(  # type: ignore[attr-defined] # Module has no attribute "CreateFailedVerificationRequest"
                user_id=user_id_str,
                eligibility_member_id=eligibility_member_id_str,
                organization_id=organization_id_str,
                verification_type=verification_type,
                unique_corp_id=unique_corp_id,
                dependent_id=dependent_id,
                first_name=first_name,
                last_name=last_name,
                date_of_birth=date_of_birth_str,
                email=email,
                work_state=work_state,
                additional_fields=additional_fields_str,
                verified_at=verified_at_str,
                policy_used=policy_used,
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(
                timeout, create_failed_verification_attempt.__qualname__
            ),
        )
        failed_verification = (
            translate.failed_verification_pb_to_eligibility_verification_attempt(
                response
            )
        )
    except grpc.RpcError as e:
        _record_grpc_error(e, create_failed_verification_attempt.__qualname__)
        logger.error(
            "Error creating failed verification record for user",
            user_id=user_id,
            eligibility_member_id=eligibility_member_id,
            organization_id=organization_id,
        )
        return None

    return failed_verification


def create_test_members_records_for_org(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    *,
    organization_id: int,
    test_member_records: List[dict[str, str]],
    timeout: Optional[float] = None,
    grpc_connection=None,
    metadata: Optional[list[tuple[str, str]]] = None,
) -> List[str]:
    if not grpc_connection:
        logger.info(
            "passed null connection to grpc endpoint",
            method="create_test_members_records_for_org",
        )
        grpc_connection = channel()
    stub = teste9ygrpc.EligibilityTestUtilityServiceStub(grpc_connection)

    try:
        parsed_records = translate.create_test_eligibility_members_json_to_pb_request(
            test_member_records=test_member_records
        )
        metadata = metadata if metadata is not None else get_trace_metadata()
        response: (  # type: ignore[valid-type] # Variable "maven_schemas.eligibility.eligibility_test_utility_pb2.CreateEligibilityMemberTestRecordsForOrganizationResponse" is not valid as a type
            teste9ypb.CreateEligibilityMemberTestRecordsForOrganizationResponse
        ) = stub.CreateEligibilityMemberTestRecordsForOrganization(
            request=teste9ypb.CreateEligibilityMemberTestRecordsForOrganizationRequest(
                organization_id=organization_id,
                test_member_records=parsed_records,
            ),
            metadata=metadata,
            timeout=_get_effective_timeout(
                timeout, "create_test_members_records_for_org"
            ),
        )
        # Translate gRPC response to members json str
        json_response = (
            translate.create_test_eligibility_members_response_to_members_response(
                response=response
            )
        )
        logger.info(
            f"Successfully created test member records for organization: {organization_id}",
            num_records=len(response.members),  # type: ignore[attr-defined] # teste9ypb.CreateEligibilityMemberTestRecordsForOrganizationResponse? has no attribute "members"
        )
    except grpc.RpcError as e:
        _record_grpc_error(e, "create_test_members_records_for_org")
        return []
    return json_response


def get_trace_metadata() -> list[tuple[str, str]]:
    """If there's a current span, pull all tags and add them as gRPC metadata (headers).

    The headers follow the existing `X-Maven-<tag>` convention.
    """

    if span := ddtrace.tracer.current_span():
        if hasattr(span, "_meta"):
            return [(_header(k), str(v)) for k, v in span._meta.items()]
    return []


@functools.lru_cache(maxsize=None)
def _header(tag: str) -> str:
    if tag.startswith(_SPAN_PREFIX):
        tag = tag[len(_SPAN_PREFIX) :]
    return f"x-maven-{inflection.dasherize(tag).lower()}"


def channel(host: str | None = None, port: int | None = None) -> grpc.Channel:
    host = host or os.environ.get("ELIGIBILITY_GRPC_SERVER_HOST", "eligibility-api")
    port = port or os.environ.get("ELIGIBILITY_GRPC_SERVER_PORT", 50051)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Union[int, str, None]", variable has type "Optional[int]")
    return grpc.insecure_channel(f"{host}:{port}")


_SPAN_PREFIX = "maven."
