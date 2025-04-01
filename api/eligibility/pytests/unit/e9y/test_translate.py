import datetime
import json

import pytest
from google.protobuf.timestamp_pb2 import Timestamp

from eligibility.e9y import translate
from maven_schemas import eligibility_pb2 as e9ypb
from maven_schemas.eligibility import pre_eligibility_pb2 as pre9ypb


def test_member_pb_to_member(eligibility_member):
    # Given
    eligibility_member.id = None
    created_at, updated_at = Timestamp(), Timestamp()
    created_at.FromDatetime(eligibility_member.created_at)
    updated_at.FromDatetime(eligibility_member.updated_at)
    member_pb = e9ypb.Member(
        id=eligibility_member.id,
        organization_id=eligibility_member.organization_id,
        file_id=eligibility_member.file_id,
        first_name=eligibility_member.first_name,
        last_name=eligibility_member.last_name,
        date_of_birth=eligibility_member.date_of_birth.isoformat(),
        created_at=created_at,
        updated_at=updated_at,
        record=json.dumps(eligibility_member.record),
        custom_attributes=eligibility_member.custom_attributes,
        work_state=eligibility_member.work_state,
        work_country=eligibility_member.work_country,
        email=eligibility_member.email,
        unique_corp_id=eligibility_member.unique_corp_id,
        dependent_id=eligibility_member.dependent_id,
        employer_assigned_id=eligibility_member.employer_assigned_id,
        effective_range=e9ypb.DateRange(
            lower=eligibility_member.effective_range.lower.isoformat(),
            upper=eligibility_member.effective_range.upper.isoformat(),
            upper_inc=eligibility_member.effective_range.upper_inc,
            lower_inc=eligibility_member.effective_range.lower_inc,
        ),
        is_v2=eligibility_member.is_v2,
        member_1_id=eligibility_member.member_1_id,
        member_2_id=eligibility_member.member_2_id,
        version=eligibility_member.member_2_version,
    )
    # When
    translated = translate.member_pb_to_member(member_pb)
    # Then
    assert translated == eligibility_member


def test_member_pb_to_member_no_effective_range(eligibility_member):
    # Given
    eligibility_member.effective_range = None
    eligibility_member.id = None
    created_at, updated_at = Timestamp(), Timestamp()
    created_at.FromDatetime(eligibility_member.created_at)
    updated_at.FromDatetime(eligibility_member.updated_at)
    member_pb = e9ypb.Member(
        id=eligibility_member.id,
        organization_id=eligibility_member.organization_id,
        file_id=eligibility_member.file_id,
        first_name=eligibility_member.first_name,
        last_name=eligibility_member.last_name,
        date_of_birth=eligibility_member.date_of_birth.isoformat(),
        created_at=created_at,
        updated_at=updated_at,
        record=json.dumps(eligibility_member.record),
        custom_attributes=eligibility_member.custom_attributes,
        work_state=eligibility_member.work_state,
        work_country=eligibility_member.work_country,
        email=eligibility_member.email,
        unique_corp_id=eligibility_member.unique_corp_id,
        dependent_id=eligibility_member.dependent_id,
        employer_assigned_id=eligibility_member.employer_assigned_id,
        is_v2=eligibility_member.is_v2,
        member_1_id=eligibility_member.member_1_id,
        member_2_id=eligibility_member.member_2_id,
        version=eligibility_member.member_2_version,
    )
    translated = translate.member_pb_to_member(member_pb)
    assert translated == eligibility_member


def test_member_list_pb_to_member_list(eligibility_member_list):
    # Given
    member_list = []
    for eligibility_member in eligibility_member_list:
        eligibility_member.id = None
        created_at, updated_at = Timestamp(), Timestamp()
        created_at.FromDatetime(eligibility_member.created_at)
        updated_at.FromDatetime(eligibility_member.updated_at)
        member_pb = e9ypb.Member(
            id=eligibility_member.id,
            organization_id=eligibility_member.organization_id,
            file_id=eligibility_member.file_id,
            first_name=eligibility_member.first_name,
            last_name=eligibility_member.last_name,
            date_of_birth=eligibility_member.date_of_birth.isoformat(),
            created_at=created_at,
            updated_at=updated_at,
            record=json.dumps(eligibility_member.record),
            custom_attributes=eligibility_member.custom_attributes,
            work_state=eligibility_member.work_state,
            work_country=eligibility_member.work_country,
            email=eligibility_member.email,
            unique_corp_id=eligibility_member.unique_corp_id,
            dependent_id=eligibility_member.dependent_id,
            employer_assigned_id=eligibility_member.employer_assigned_id,
            effective_range=e9ypb.DateRange(
                lower=eligibility_member.effective_range.lower.isoformat(),
                upper=eligibility_member.effective_range.upper.isoformat(),
                upper_inc=eligibility_member.effective_range.upper_inc,
                lower_inc=eligibility_member.effective_range.lower_inc,
            ),
            is_v2=eligibility_member.is_v2,
            member_1_id=eligibility_member.member_1_id,
            member_2_id=eligibility_member.member_2_id,
            version=eligibility_member.member_2_version,
        )
        member_list.append(member_pb)
    # When
    list = e9ypb.MemberList(member_list=member_list)
    translated = translate.member_list_pb_to_member_list(list)

    # Then
    for t in translated:
        assert t in eligibility_member_list


def test_verification_for_user_pb_to_verification_for_user(verification):
    # Given
    created_at, verified_at = Timestamp(), Timestamp()
    created_at.FromDatetime(verification.created_at)
    verified_at.FromDatetime(verification.verified_at)

    verification_session = None
    if verification.verification_session is not None:
        verification_session = str(verification.verification_session)

    verification_pb = e9ypb.VerificationForUser(
        verification_id=verification.verification_id,
        user_id=verification.user_id,
        organization_id=verification.organization_id,
        unique_corp_id=verification.unique_corp_id,
        date_of_birth=verification.date_of_birth.isoformat(),
        verification_type=verification.verification_type,
        verification_created_at=created_at,
        verification_updated_at=verified_at,
        verification_deactivated_at=verification.deactivated_at,
        verified_at=verified_at,
        dependent_id=verification.dependent_id,
        eligibility_member_id=str(verification.eligibility_member_id),
        employer_assigned_id=verification.employer_assigned_id,
        work_state=verification.work_state,
        email=verification.email,
        first_name=verification.first_name,
        last_name=verification.last_name,
        record=json.dumps(verification.record),
        effective_range=e9ypb.DateRange(
            lower=verification.effective_range.lower.isoformat(),
            upper=verification.effective_range.upper.isoformat(),
            upper_inc=verification.effective_range.upper_inc,
            lower_inc=verification.effective_range.lower_inc,
        ),
        additional_fields=json.dumps(verification.additional_fields),
        verification_session=verification_session,
        is_v2=verification.is_v2,
        verification_1_id=verification.verification_1_id,
        verification_2_id=verification.verification_2_id,
        eligibility_member_2_id=str(verification.eligibility_member_2_id),
        eligibility_member_2_version=str(verification.eligibility_member_2_version),
    )
    translated = translate.verification_for_user_pb_to_eligibility_verification(
        verification_pb
    )
    assert translated == verification


def test_verification_for_user_pb_to_verification_for_user_null_values(
    verification,
):
    # Given
    verification.eligibility_member_id = None
    verification.first_name = None
    verification.last_name = None
    verification.employer_assigned_id = None
    verification.is_active = False
    verification.deactivated_at = datetime.datetime(2022, 1, 1, 0, 0, 0)
    verification.verification_session = None
    verification.eligibility_member_2_id = None
    verification.eligibility_member_2_version = None

    created_at, verified_at, deactivated_at = Timestamp(), Timestamp(), Timestamp()
    created_at.FromDatetime(verification.created_at)
    verified_at.FromDatetime(verification.verified_at)
    deactivated_at.FromDatetime(verification.deactivated_at)

    verification_pb = e9ypb.VerificationForUser(
        verification_id=verification.verification_id,
        user_id=verification.user_id,
        organization_id=verification.organization_id,
        unique_corp_id=verification.unique_corp_id,
        date_of_birth=verification.date_of_birth.isoformat(),
        verification_type=verification.verification_type,
        verification_created_at=created_at,
        verification_updated_at=verified_at,
        verification_deactivated_at=deactivated_at,
        verified_at=verified_at,
        dependent_id=verification.dependent_id,
        work_state=verification.work_state,
        email=verification.email,
        record=json.dumps(verification.record),
        effective_range=e9ypb.DateRange(
            lower=verification.effective_range.lower.isoformat(),
            upper=verification.effective_range.upper.isoformat(),
            upper_inc=verification.effective_range.upper_inc,
            lower_inc=verification.effective_range.lower_inc,
        ),
        additional_fields=json.dumps(verification.additional_fields),
        verification_session=verification.verification_session,
        is_v2=verification.is_v2,
        verification_1_id=verification.verification_1_id,
        verification_2_id=verification.verification_2_id,
        eligibility_member_2_id=str(verification.eligibility_member_2_id),
        eligibility_member_2_version=str(verification.eligibility_member_2_version),
    )
    translated = translate.verification_for_user_pb_to_eligibility_verification(
        verification_pb
    )
    assert translated == verification


def test_verification_attempt_pb_to_eligibility_verification_attempt(
    verification_attempt,
):
    # Given
    created_at, verified_at = Timestamp(), Timestamp()
    created_at.FromDatetime(verification_attempt.created_at)
    verified_at.FromDatetime(verification_attempt.verified_at)

    verification_pb = e9ypb.VerificationAttempt(
        verification_attempt_id=verification_attempt.id,
        organization_id=str(verification_attempt.organization_id),
        unique_corp_id=verification_attempt.unique_corp_id,
        dependent_id=verification_attempt.dependent_id,
        first_name=verification_attempt.first_name,
        last_name=verification_attempt.last_name,
        email=verification_attempt.email,
        user_id=str(verification_attempt.user_id),
        date_of_birth=verification_attempt.date_of_birth.isoformat(),
        work_state=verification_attempt.work_state,
        eligibility_member_id=str(verification_attempt.eligibility_member_id),
        additional_fields=json.dumps(verification_attempt.additional_fields),
        verification_type=verification_attempt.verification_type,
        policy_used=verification_attempt.policy_used,
        successful_verification=verification_attempt.successful_verification,
        created_at=created_at,
        updated_at=verified_at,
        verified_at=verified_at,
    )
    translated = translate.failed_verification_pb_to_eligibility_verification_attempt(
        verification_pb
    )
    assert translated == verification_attempt


def test_wallet_pb_to_wallet(wallet_enablement):
    # Given
    created_at, updated_at = Timestamp(), Timestamp()
    created_at.FromDatetime(wallet_enablement.created_at)
    updated_at.FromDatetime(wallet_enablement.updated_at)
    wallet_pb = e9ypb.WalletEnablement(
        member_id=wallet_enablement.member_id,
        organization_id=wallet_enablement.organization_id,
        enabled=wallet_enablement.enabled,
        insurance_plan=wallet_enablement.insurance_plan,
        start_date=wallet_enablement.start_date.isoformat(),
        eligibility_date=wallet_enablement.eligibility_date.isoformat(),
        eligibility_end_date=wallet_enablement.eligibility_end_date.isoformat(),
        created_at=created_at,
        updated_at=updated_at,
    )
    # When
    translated = translate.wallet_pb_to_wallet(wallet_pb)
    # Then
    assert translated == wallet_enablement


def test_wallet_pb_to_wallet_null_end_date(wallet_enablement):
    # Given
    created_at, updated_at = Timestamp(), Timestamp()
    created_at.FromDatetime(wallet_enablement.created_at)
    updated_at.FromDatetime(wallet_enablement.updated_at)
    wallet_pb = e9ypb.WalletEnablement(
        member_id=wallet_enablement.member_id,
        organization_id=wallet_enablement.organization_id,
        enabled=wallet_enablement.enabled,
        insurance_plan=wallet_enablement.insurance_plan,
        start_date=wallet_enablement.start_date.isoformat(),
        eligibility_date=wallet_enablement.eligibility_date.isoformat(),
        eligibility_end_date=wallet_enablement.eligibility_end_date.isoformat(),
        created_at=created_at,
        updated_at=updated_at,
    )
    # When
    translated = translate.wallet_pb_to_wallet(wallet_pb)
    # Then
    assert translated == wallet_enablement


def test_pre_eligibility_pb_to_pre_eligibility(pre_eligibility_response):
    # Given
    pre_eligibility_response_pb = pre9ypb.PreEligibilityResponse(
        match_type=pre_eligibility_response.match_type,
        pre_eligibility_organizations=pre_eligibility_response.pre_eligibility_organizations,
    )
    # When
    translated = translate.pre_eligibility_pb_to_pre_eligibility(
        pre_eligibility_response_pb
    )
    # Then
    assert translated == pre_eligibility_response


@pytest.mark.parametrize(
    argnames="input,expected",
    argvalues=[(None, None), ("12345678", 12345678), ("123abc", None)],
)
def test_to_int(input, expected):
    assert translate._to_int(input) == expected
