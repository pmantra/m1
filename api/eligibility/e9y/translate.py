from __future__ import annotations

import datetime
import functools
import json
from typing import List

from eligibility.e9y import model
from eligibility.utils.e9y_test_utils import EligibilityMemberJSONEncoder
from maven_schemas import eligibility_pb2 as e9ypb
from maven_schemas.eligibility import eligibility_test_utility_pb2 as teste9ypb
from maven_schemas.eligibility import pre_eligibility_pb2 as pre9ypb

__all__ = (
    "member_pb_to_member",
    "wallet_pb_to_wallet",
    "verification_for_user_pb_to_eligibility_verification",
)


def member_pb_to_member(response: e9ypb.Member) -> model.EligibilityMember:  # type: ignore[name-defined, valid-type] # Name "e9ypb.Member" is not defined
    effective_range = None
    if response.HasField("effective_range"):  # type: ignore[attr-defined]
        lower = response.effective_range.lower or None  # type: ignore[attr-defined]
        upper = response.effective_range.upper or None  # type: ignore[attr-defined]
        effective_range = model.DateRange(
            lower=_to_date(lower),
            upper=_to_date(upper),
            lower_inc=response.effective_range.lower_inc,  # type: ignore[attr-defined]
            upper_inc=response.effective_range.upper_inc,  # type: ignore[attr-defined]
        )
    is_v2 = member_1_id = member_2_id = member_2_version = None
    # Excluding testing mock response
    if hasattr(response, "is_v2"):
        is_v2 = response.is_v2  # type: ignore[attr-defined]
    if hasattr(response, "member_1_id"):
        member_1_id = response.member_1_id or None  # type: ignore[attr-defined]
    if hasattr(response, "member_2_id"):
        member_2_id = response.member_2_id or None  # type: ignore[attr-defined]
    if hasattr(response, "version"):
        member_2_version = response.version or None  # type: ignore[attr-defined]
    return model.EligibilityMember(
        id=response.id or None,  # type: ignore[arg-type, attr-defined] # Argument "id" to "EligibilityMember" has incompatible type "Optional[Any]"; expected "int"
        organization_id=response.organization_id,  # type: ignore[attr-defined]
        file_id=response.file_id,  # type: ignore[attr-defined]
        first_name=response.first_name,  # type: ignore[attr-defined]
        last_name=response.last_name,  # type: ignore[attr-defined]
        date_of_birth=_to_date(response.date_of_birth),  # type: ignore[arg-type, attr-defined] # Argument "date_of_birth" to "EligibilityMember" has incompatible type "Optional[date]"; expected "date"
        created_at=response.created_at.ToDatetime(),  # type: ignore[attr-defined]
        updated_at=response.updated_at.ToDatetime(),  # type: ignore[attr-defined]
        record=json.loads(response.record),  # type: ignore[attr-defined]
        custom_attributes=response.custom_attributes,  # type: ignore[attr-defined]
        work_state=response.work_state or None,  # type: ignore[attr-defined]
        work_country=response.work_country or None,  # type: ignore[attr-defined]
        email=response.email,  # type: ignore[attr-defined]
        unique_corp_id=response.unique_corp_id,  # type: ignore[attr-defined]
        dependent_id=response.dependent_id,  # type: ignore[attr-defined]
        employer_assigned_id=response.employer_assigned_id,  # type: ignore[attr-defined]
        effective_range=effective_range,
        is_v2=is_v2,
        member_1_id=member_1_id,
        member_2_id=member_2_id,
        member_2_version=member_2_version,
    )


def member_list_pb_to_member_list(
    response: e9ypb.MemberList,  # type: ignore[name-defined, valid-type] # Name "e9ypb.MemberList" is not defined
) -> list[model.EligibilityMember]:
    member_records = []
    for m in response.member_list:  # type: ignore[attr-defined]
        member_records.append(member_pb_to_member(m))

    return member_records


def wallet_pb_to_wallet(response: e9ypb.WalletEnablement) -> model.WalletEnablement:  # type: ignore[name-defined, valid-type] # Name "e9ypb.WalletEnablement" is not defined
    start_date = _to_date(response.start_date)  # type: ignore[attr-defined]
    created_at = response.created_at.ToDatetime()  # type: ignore[attr-defined]
    updated_at = response.updated_at.ToDatetime()  # type: ignore[attr-defined]
    eligibility_date = _to_date(response.eligibility_date)  # type: ignore[attr-defined]
    eligibility_end_date = (
        _to_date(response.eligibility_end_date)  # type: ignore[attr-defined]
        if response.eligibility_end_date != ""  # type: ignore[attr-defined]
        else None
    )

    return model.WalletEnablement(
        member_id=response.member_id,  # type: ignore[attr-defined]
        organization_id=response.organization_id,  # type: ignore[attr-defined]
        enabled=response.enabled,  # type: ignore[attr-defined]
        insurance_plan=response.insurance_plan or None,  # type: ignore[attr-defined]
        start_date=start_date,
        eligibility_date=eligibility_date,
        eligibility_end_date=eligibility_end_date,
        created_at=created_at,
        updated_at=updated_at,
    )


def pre_eligibility_pb_to_pre_eligibility(
    response: pre9ypb.PreEligibilityResponse,  # type: ignore[valid-type] # Variable "maven_schemas.eligibility.pre_eligibility_pb2.PreEligibilityResponse" is not valid as a type
) -> model.PreEligibilityResponse:
    orgs = response.pre_eligibility_organizations  # type: ignore[attr-defined] # pre9ypb.PreEligibilityResponse? has no attribute "pre_eligibility_organizations"
    pre_eligibility_organizations = [
        pre_eligibility_org_pb_to_pre_eligibility_org(org) for org in orgs or []
    ]

    return model.PreEligibilityResponse(
        match_type=response.match_type,  # type: ignore[attr-defined] # pre9ypb.PreEligibilityResponse? has no attribute "match_type"
        pre_eligibility_organizations=pre_eligibility_organizations,
    )


def pre_eligibility_org_pb_to_pre_eligibility_org(
    org: pre9ypb.PreEligibilityOrganization,  # type: ignore[valid-type] # Variable "maven_schemas.eligibility.pre_eligibility_pb2.PreEligibilityOrganization" is not valid as a type
) -> model.PreEligibilityOrganization:
    eligibility_end_date = org.eligibility_end_date.ToDatetime()  # type: ignore[attr-defined] # pre9ypb.PreEligibilityOrganization? has no attribute "eligibility_end_date"
    return model.PreEligibilityOrganization(
        organization_id=org.organization_id, eligibility_end_date=eligibility_end_date  # type: ignore[attr-defined] # pre9ypb.PreEligibilityOrganization? has no attribute "organization_id"
    )


def verification_for_user_pb_to_eligibility_verification(
    response: e9ypb.VerificationForUser,  # type: ignore[name-defined, valid-type] # Name "e9ypb.VerificationForUser" is not defined
) -> model.EligibilityVerification:
    # Convert our upper range pb into normal date range
    lower = response.effective_range.lower or None  # type: ignore[attr-defined]
    upper = response.effective_range.upper or None  # type: ignore[attr-defined]
    effective_range = model.DateRange(
        lower=_to_date(lower),
        upper=_to_date(upper),
        lower_inc=response.effective_range.lower_inc,  # type: ignore[attr-defined]
        upper_inc=response.effective_range.upper_inc,  # type: ignore[attr-defined]
    )

    created_at = response.verification_created_at.ToDatetime()  # type: ignore[attr-defined]
    verified_at = response.verified_at.ToDatetime()  # type: ignore[attr-defined]

    is_active = True
    deactivated_at = None

    # Timestamps in protobuf default to the number of seconds and nanos since the epoch- if they're both zero, that means the timestamp value is null
    # https://protobuf.dev/reference/protobuf/google.protobuf/#timestamp
    if (
        response.verification_deactivated_at.nanos != 0  # type: ignore[attr-defined]
        or response.verification_deactivated_at.seconds != 0  # type: ignore[attr-defined]
    ):
        deactivated_at = response.verification_deactivated_at.ToDatetime()  # type: ignore[attr-defined]
        is_active = False

    # Cast blank values to be none
    dependent_id, eligibility_member_id, employer_assigned_id, work_state = (
        None,
        None,
        None,
        None,
    )
    if response.dependent_id != "":  # type: ignore[attr-defined]
        dependent_id = response.dependent_id  # type: ignore[attr-defined]
    if response.eligibility_member_id != "":  # type: ignore[attr-defined]
        eligibility_member_id = int(response.eligibility_member_id)  # type: ignore[attr-defined]
    if response.employer_assigned_id != "":  # type: ignore[attr-defined]
        employer_assigned_id = response.employer_assigned_id  # type: ignore[attr-defined]
    if response.work_state != "":  # type: ignore[attr-defined]
        work_state = response.work_state  # type: ignore[attr-defined]

    email, record, first_name, last_name = (
        None,
        None,
        None,
        None,
    )
    if response.email != "":  # type: ignore[attr-defined]
        email = response.email  # type: ignore[attr-defined]
    if response.record != "":  # type: ignore[attr-defined]
        record = json.loads(response.record)  # type: ignore[attr-defined]
    if response.first_name != "":  # type: ignore[attr-defined]
        first_name = response.first_name  # type: ignore[attr-defined]
    if response.last_name != "":  # type: ignore[attr-defined]
        last_name = response.last_name  # type: ignore[attr-defined]

    if response.additional_fields is None or response.additional_fields == "":  # type: ignore[attr-defined]
        additional_fields = ""
    else:
        additional_fields = json.loads(response.additional_fields)  # type: ignore[attr-defined]

    if response.verification_session == "":  # type: ignore[attr-defined]
        verification_session = None
    else:
        verification_session = response.verification_session  # type: ignore[attr-defined]

    return model.EligibilityVerification(
        verification_id=response.verification_id,  # type: ignore[attr-defined]
        user_id=response.user_id,  # type: ignore[attr-defined]
        organization_id=response.organization_id,  # type: ignore[attr-defined]
        unique_corp_id=response.unique_corp_id,  # type: ignore[attr-defined]
        date_of_birth=_to_date(response.date_of_birth),  # type: ignore[arg-type, attr-defined] # Argument "date_of_birth" to "EligibilityVerification" has incompatible type "Optional[date]"; expected "date"
        verification_type=response.verification_type,  # type: ignore[attr-defined]
        effective_range=effective_range,
        created_at=created_at,
        verified_at=verified_at,
        deactivated_at=deactivated_at,
        dependent_id=dependent_id,  # type: ignore[arg-type] # Argument "dependent_id" to "EligibilityVerification" has incompatible type "Optional[Any]"; expected "str"
        eligibility_member_id=eligibility_member_id,
        employer_assigned_id=employer_assigned_id,
        work_state=work_state,
        email=email,  # type: ignore[arg-type] # Argument "email" to "EligibilityVerification" has incompatible type "Optional[Any]"; expected "str"
        record=record,  # type: ignore[arg-type] # Argument "record" to "EligibilityVerification" has incompatible type "Optional[Any]"; expected "Dict[Any, Any]"
        first_name=first_name,  # type: ignore[arg-type] # Argument "first_name" to "EligibilityVerification" has incompatible type "Optional[Any]"; expected "str"
        last_name=last_name,  # type: ignore[arg-type] # Argument "last_name" to "EligibilityVerification" has incompatible type "Optional[Any]"; expected "str"
        is_active=is_active,
        additional_fields=additional_fields,  # type: ignore[arg-type] # Argument "additional_fields" to "EligibilityVerification" has incompatible type "str"; expected "Optional[Dict[Any, Any]]"
        verification_session=verification_session,
        is_v2=response.is_v2,  # type: ignore[attr-defined]
        verification_1_id=response.verification_1_id or None,  # type: ignore[attr-defined]
        verification_2_id=response.verification_2_id or None,  # type: ignore[attr-defined]
        eligibility_member_2_id=_to_int(response.eligibility_member_2_id),  # type: ignore[attr-defined]
        eligibility_member_2_version=_to_int(response.eligibility_member_2_version),  # type: ignore[attr-defined]
    )


def failed_verification_pb_to_eligibility_verification_attempt(
    response: e9ypb.VerificationAttempt,  # type: ignore[name-define, valid-type] # Name "e9ypb.VerificationAttempt" is not defined
) -> model.EligibilityVerificationAttempt:
    created_at = response.created_at.ToDatetime()  # type: ignore[attr-defined]
    verified_at = response.verified_at.ToDatetime()  # type: ignore[attr-defined]

    # Cast blank values to be none
    dependent_id, eligibility_member_id, work_state, organization_id = (
        None,
        None,
        None,
        None,
    )
    if response.dependent_id != "":  # type: ignore[attr-defined]
        dependent_id = response.dependent_id  # type: ignore[attr-defined]
    if response.eligibility_member_id != "":  # type: ignore[attr-defined]
        eligibility_member_id = int(response.eligibility_member_id)  # type: ignore[attr-defined]
    if response.work_state != "":  # type: ignore[attr-defined]
        work_state = response.work_state  # type: ignore[attr-defined]
    if response.organization_id != "":  # type: ignore[attr-defined]
        organization_id = int(response.organization_id)  # type: ignore[attr-defined]

    email, first_name, last_name = (
        None,
        None,
        None,
    )
    if response.email != "":  # type: ignore[attr-defined]
        email = response.email  # type: ignore[attr-defined]
    if response.first_name != "":  # type: ignore[attr-defined]
        first_name = response.first_name  # type: ignore[attr-defined]
    if response.last_name != "":  # type: ignore[attr-defined]
        last_name = response.last_name  # type: ignore[attr-defined]

    if response.additional_fields is None or response.additional_fields == "":  # type: ignore[attr-defined]
        additional_fields = {}
    else:
        additional_fields = json.loads(response.additional_fields)  # type: ignore[attr-defined]

    return model.EligibilityVerificationAttempt(
        user_id=int(response.user_id),  # type: ignore[attr-defined]
        organization_id=organization_id,  # type: ignore[arg-type, attr-defined] # Argument "organization_id" to "EligibilityVerificationAttempt" has incompatible type "Optional[int]"; expected "int"
        unique_corp_id=response.unique_corp_id,  # type: ignore[attr-defined]
        dependent_id=dependent_id,  # type: ignore[arg-type] # Argument "dependent_id" to "EligibilityVerificationAttempt" has incompatible type "Optional[Any]"; expected "str"
        first_name=first_name,  # type: ignore[arg-type] # Argument "first_name" to "EligibilityVerificationAttempt" has incompatible type "Optional[Any]"; expected "str"
        last_name=last_name,  # type: ignore[arg-type] # Argument "last_name" to "EligibilityVerificationAttempt" has incompatible type "Optional[Any]"; expected "str"
        date_of_birth=_to_date(response.date_of_birth),  # type: ignore[arg-type, attr-defined] # Argument "date_of_birth" to "EligibilityVerificationAttempt" has incompatible type "Optional[date]"; expected "date"
        email=email,  # type: ignore[arg-type] # Argument "email" to "EligibilityVerificationAttempt" has incompatible type "Optional[Any]"; expected "str"
        work_state=work_state,  # type: ignore[arg-type] # Argument "work_state" to "EligibilityVerificationAttempt" has incompatible type "Optional[Any]"; expected "str"
        policy_used="",
        verified_at=verified_at,
        created_at=created_at,
        verification_type=response.verification_type,  # type: ignore[attr-defined]
        successful_verification=response.successful_verification,  # type: ignore[attr-defined]
        id=response.verification_attempt_id,  # type: ignore[attr-defined]
        eligibility_member_id=eligibility_member_id,
        additional_fields=additional_fields,
    )


def eligible_features_for_user_pb_to_eligible_features_for_user_response(
    response: e9ypb.GetEligibleFeaturesForUserResponse,  # type: ignore[name-defined, valid-type] # Name "e9ypb.GetEligibleFeaturesForUserResponse" is not defined
) -> model.EligibleFeaturesForUserResponse:
    return model.EligibleFeaturesForUserResponse(
        features=response.features, has_population=response.has_population  # type: ignore[attr-defined]
    )


def eligible_features_for_user_and_org_pb_to_eligible_features_for_user_and_org_response(
    response: e9ypb.GetEligibleFeaturesForUserAndOrgResponse,  # type: ignore[name-defined, valid-type] # Name "e9ypb.GetEligibleFeaturesForUserResponse" is not defined
) -> model.EligibleFeaturesForUserAndOrgResponse:
    return model.EligibleFeaturesForUserAndOrgResponse(
        features=response.features, has_population=response.has_population  # type: ignore[attr-defined]
    )


def eligible_features_by_sub_population_id_pb_to_eligible_features_by_sub_population_id_response(
    response: e9ypb.GetEligibleFeaturesBySubPopulationIdResponse,  # type: ignore[name-defined, valid-type] # Name "e9ypb.GetEligibleFeaturesBySubPopulationIdResponse" is not defined
) -> model.EligibleFeaturesBySubPopulationIdResponse:
    return model.EligibleFeaturesBySubPopulationIdResponse(
        features=response.features, has_definition=response.has_definition  # type: ignore[attr-defined]
    )


def create_test_eligibility_members_json_to_pb_request(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    test_member_records: List[dict[str, str]],
):
    translated_records: List[teste9ypb.EligibilityMemberTestRecord] = []  # type: ignore[valid-type] # Variable "maven_schemas.eligibility.eligibility_test_utility_pb2.EligibilityMemberTestRecord" is not valid as a type
    # translate to EligibilityMemberTestRecord protobuf
    for record in test_member_records:
        # parse eligibility effective range
        effective_range = _parse_effective_range_for_eligibility_member(
            record.get("eligibility_start_date", ""),
            record.get("eligibility_end_date", ""),
        )
        translated = teste9ypb.EligibilityMemberTestRecord(
            first_name=record.get("first_name", ""),
            last_name=record.get("last_name", ""),
            dependent_id=record.get("dependent_id", ""),
            date_of_birth=record.get("date_of_birth", ""),
            email=record.get("email", ""),
            unique_corp_id=record.get("unique_corp_id", ""),
            effective_range=effective_range,
        )
        translated_records.append(translated)
    return translated_records


def _parse_effective_range_for_eligibility_member(
    eligibility_start_date: str, eligibility_end_date: str
) -> teste9ypb.DateRange:  # type: ignore[valid-type] # Variable "maven_schemas.eligibility.eligibility_test_utility_pb2.DateRange" is not valid as a type
    today = datetime.datetime.utcnow()
    one_year_before_today = today - datetime.timedelta(days=365)
    one_year_after_today = today + datetime.timedelta(days=365)
    default_start_date = one_year_before_today.strftime("%Y-%m-%d")
    default_end_date = one_year_after_today.strftime("%Y-%m-%d")

    effective_range = teste9ypb.DateRange()
    effective_range.lower = eligibility_start_date or default_start_date
    effective_range.upper = eligibility_end_date or default_end_date
    effective_range.lower_inc = True
    effective_range.upper_inc = False

    return effective_range


def create_test_eligibility_members_response_to_members_response(
    response: teste9ypb.CreateEligibilityMemberTestRecordsForOrganizationResponse,  # type: ignore[valid-type] # Variable "maven_schemas.eligibility.eligibility_test_utility_pb2.CreateEligibilityMemberTestRecordsForOrganizationResponse" is not valid as a type
) -> List[str]:
    records_created = response.members  # type: ignore[attr-defined] # teste9ypb.CreateEligibilityMemberTestRecordsForOrganizationResponse? has no attribute "members"
    encoded_members = []
    for record in records_created:
        member = member_pb_to_member(record)
        encoded = _translate_member_pb_record_to_json(member=member)
        encoded_members.append(encoded)
    return encoded_members


def _translate_member_pb_record_to_json(member: model.EligibilityMember) -> str:
    return json.dumps(member, cls=EligibilityMemberJSONEncoder)


@functools.lru_cache(maxsize=2000)
def _to_date(date: str | datetime.date | None) -> datetime.date | None:
    if not date:
        return None
    if isinstance(date, datetime.datetime):
        return date.date()
    if isinstance(date, datetime.date):
        return date
    if isinstance(date, str):
        return datetime.datetime.fromisoformat(date).date()
    return None


def _to_int(value: str | None) -> int | None:
    """
    parse optional str value to int
    if value cannot be parsed as int, return None
    """
    if value is None:
        return None
    try:
        parsed = int(value)
        return parsed
    except ValueError:
        return None
