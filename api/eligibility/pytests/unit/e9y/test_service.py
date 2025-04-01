import datetime
import json

import grpc
import pytest
from google.protobuf.timestamp_pb2 import Timestamp

from eligibility import service as svc
from eligibility.e9y import grpc_service, model
from health.models.health_profile import HealthProfile
from maven_schemas import eligibility_pb2 as e9ypb
from maven_schemas.eligibility import pre_eligibility_pb2 as pre9ypb
from models.tracks.track import TrackName
from storage.connection import db


@pytest.fixture
def eligibility_member_pb(eligibility_member):
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
    return member_pb


@pytest.fixture
def eligibility_member_list_pb(eligibility_member_list):
    member_list = []
    for member in eligibility_member_list:
        created_at, updated_at = Timestamp(), Timestamp()
        created_at.FromDatetime(member.created_at)
        updated_at.FromDatetime(member.updated_at)
        member_pb = e9ypb.Member(
            id=member.id,
            organization_id=member.organization_id,
            file_id=member.file_id,
            first_name=member.first_name,
            last_name=member.last_name,
            date_of_birth=member.date_of_birth.isoformat(),
            created_at=created_at,
            updated_at=updated_at,
            record=json.dumps(member.record),
            custom_attributes=member.custom_attributes,
            work_state=member.work_state,
            work_country=member.work_country,
            email=member.email,
            unique_corp_id=member.unique_corp_id,
            dependent_id=member.dependent_id,
            employer_assigned_id=member.employer_assigned_id,
            effective_range=e9ypb.DateRange(
                lower=member.effective_range.lower.isoformat(),
                upper=member.effective_range.upper.isoformat(),
                upper_inc=member.effective_range.upper_inc,
                lower_inc=member.effective_range.lower_inc,
            ),
            is_v2=member.is_v2,
            member_1_id=member.member_1_id,
            member_2_id=member.member_2_id,
            version=member.member_2_version,
        )
        member_list.append(member_pb)
    return e9ypb.MemberList(member_list=member_list)


@pytest.fixture
def wallet_enablement_pb(wallet_enablement):
    created_at, updated_at = Timestamp(), Timestamp()
    created_at.FromDatetime(wallet_enablement.created_at)
    updated_at.FromDatetime(wallet_enablement.updated_at)
    return e9ypb.WalletEnablement(
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


@pytest.fixture
def verification_response_pb(verification):
    created_at, verified_at = Timestamp(), Timestamp()
    created_at.FromDatetime(verification.created_at)
    verified_at.FromDatetime(verification.verified_at)

    return e9ypb.VerificationForUser(
        verification_id=verification.verification_id,
        user_id=verification.user_id,
        organization_id=verification.organization_id,
        unique_corp_id=verification.unique_corp_id,
        date_of_birth=verification.date_of_birth.isoformat(),
        verification_type=verification.verification_type,
        verification_created_at=created_at,
        verification_updated_at=verified_at,
        verified_at=verified_at,
        verification_deactivated_at=verification.deactivated_at,
        dependent_id=verification.dependent_id,
        eligibility_member_id=str(verification.eligibility_member_id),
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
        verification_session=verification.verification_session,
        is_v2=verification.is_v2,
        verification_1_id=verification.verification_1_id,
        verification_2_id=verification.verification_2_id,
    )


@pytest.fixture
def verification_list_response_pb(multiple_verifications_for_user):
    verification_list = []
    for verification in multiple_verifications_for_user:
        created_at, verified_at = Timestamp(), Timestamp()
        created_at.FromDatetime(verification.created_at)
        verified_at.FromDatetime(verification.verified_at)

        verification_for_user = e9ypb.VerificationForUser(
            verification_id=verification.verification_id,
            user_id=verification.user_id,
            organization_id=verification.organization_id,
            unique_corp_id=verification.unique_corp_id,
            date_of_birth=verification.date_of_birth.isoformat(),
            verification_type=verification.verification_type,
            verification_created_at=created_at,
            verification_updated_at=verified_at,
            verified_at=verified_at,
            verification_deactivated_at=verification.deactivated_at,
            dependent_id=verification.dependent_id,
            eligibility_member_id=str(verification.eligibility_member_id),
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
            verification_session=verification.verification_session,
            is_v2=verification.is_v2,
            verification_1_id=verification.verification_1_id,
            verification_2_id=verification.verification_2_id,
        )
        verification_list.append(verification_for_user)
    return e9ypb.VerificationList(verification_list=verification_list)


@pytest.fixture
def pre_eligibility_response_pb(pre_eligibility_response):
    return pre9ypb.PreEligibilityResponse(
        match_type=pre_eligibility_response.match_type,
        pre_eligibility_organizations=pre_eligibility_response.pre_eligibility_organizations,
    )


@pytest.mark.parametrize(
    argnames="method,call,params",
    argvalues=[
        (
            grpc_service.standard,
            "CheckStandardEligibility",
            dict(date_of_birth=datetime.date.today(), company_email="foo"),
        ),
        (
            grpc_service.alternate,
            "CheckAlternateEligibility",
            dict(
                date_of_birth=datetime.date.today(),
                work_state="hyrule",
                first_name="princess",
                last_name="zelda",
            ),
        ),
        (
            grpc_service.client_specific,
            "CheckClientSpecificEligibility",
            dict(
                is_employee=True,
                date_of_birth=datetime.date.today(),
                unique_corp_id="unique",
                organization_id=1,
            ),
        ),
        # TODO: cover client_specific with is_employee=False, own_date_of_birth=datetime.date.today()
        (grpc_service.member_id_search, "GetMemberById", dict(member_id=1)),
        (
            grpc_service.org_identity_search,
            "GetMemberByOrgIdentity",
            dict(organization_id=1, unique_corp_id="unique", dependent_id="dependent"),
        ),
        (
            grpc_service.no_dob_verification,
            "CheckNoDOBEligibility",
            dict(
                email="foo@bar.net",
                first_name="princess",
                last_name="zelda",
            ),
        ),
        (
            grpc_service.healthplan,
            "CheckHealthPlanEligibility",
            dict(
                date_of_birth=datetime.date.today(),
                first_name="princess",
                last_name="zelda",
                subscriber_id="test",
            ),
        ),
        (
            grpc_service.employer,
            "CheckEmployerEligibility",
            dict(
                company_email="foo@bar.net",
                date_of_birth=datetime.date.today(),
                dependent_date_of_birth=datetime.date.today(),
                employee_first_name="employee_first_name",
                employee_last_name="employee_last_name",
                first_name="first_name",
                last_name="last_name",
                work_state="CA",
                user_id=1,
            ),
        ),
    ],
)
def test_eligibility_checks(
    method, call, params, eligibility_member, eligibility_member_pb, e9y_grpc
):
    # Given
    check = getattr(e9y_grpc, call)
    check.return_value = eligibility_member_pb
    # When
    member = method(**params)
    # Then
    assert member == eligibility_member


def test_basic_eligibility(
    eligibility_member_list, eligibility_member_list_pb, e9y_grpc
):
    # Given
    method = grpc_service.basic
    call = "CheckBasicEligibility"
    check = getattr(e9y_grpc, call)
    check.return_value = eligibility_member_list_pb

    # When
    params = dict(
        date_of_birth=datetime.date.today(),
        first_name="Foo",
        last_name="Bar",
        user_id=1,
    )
    member_list = method(**params)
    # Then
    assert member_list == eligibility_member_list


def test_eligibility_check_overeligibility(
    eligibility_member_list, eligibility_member_list_pb, e9y_grpc
):
    # Given
    method = grpc_service.overeligibility
    call = "CheckEligibilityOverEligibility"
    check = getattr(e9y_grpc, call)
    check.return_value = eligibility_member_list_pb

    # When
    params = dict(
        date_of_birth=datetime.date.today(),
        first_name="Foo",
        last_name="Bar",
        user_id=12345,
        unique_corp_id="unique",
    )
    member_list = method(**params)
    # Then
    assert member_list == eligibility_member_list


def test_eligibility_check_overeligibility_no_result(
    eligibility_member_list, e9y_grpc, grpc_error_with_code
):
    # Given
    method = grpc_service.overeligibility
    call = "CheckEligibilityOverEligibility"
    check = getattr(e9y_grpc, call)
    check.side_effect = grpc_error_with_code

    # When
    params = dict(
        date_of_birth=datetime.date.today(),
        first_name="Foo",
        last_name="Bar",
        user_id=12345,
        unique_corp_id="unique",
    )
    response = method(**params)

    # Then
    assert response is None


def test_create_verification(e9y_grpc, verification, verification_response_pb):
    # Given
    method = grpc_service.create_verification
    call = "CreateVerificationForUser"
    create_verification = getattr(e9y_grpc, call)
    create_verification.return_value = verification_response_pb
    params = dict(
        user_id=verification.user_id,
        verification_type=verification.verification_type,
        organization_id=verification.organization_id,
        unique_corp_id=verification.unique_corp_id,
        dependent_id=verification.dependent_id,
        first_name=verification.first_name,
        last_name=verification.last_name,
        email=verification.email,
        work_state=verification.work_state,
        date_of_birth=verification.date_of_birth,
        eligibility_member_id=verification.eligibility_member_id,
        additional_fields=verification.additional_fields,
        verified_at=verification.verified_at,
    )

    # When
    returned_verification = method(**params)
    # Then
    assert (verification, None) == returned_verification


def test_create_multiple_verifications(
    e9y_grpc,
    multiple_eligibility_member_records_for_user,
    multiple_verifications_for_user,
    verification_list_response_pb,
):
    # Given
    verification_type = "alternate"
    first_name = "test"
    last_name = "test"
    date_of_birth = datetime.date.today()
    verified_at = multiple_verifications_for_user[0].verified_at
    verification_data_list = []
    for record in multiple_eligibility_member_records_for_user:
        vd = model.VerificationData(
            eligibility_member_id=record.id,
            organization_id=record.organization_id,
            unique_corp_id=record.unique_corp_id,
            dependent_id=record.dependent_id,
            email=record.email,
            work_state=record.work_state,
            additional_fields="",
        )
        verification_data_list.append(vd)

    method = grpc_service.create_multiple_verifications_for_user
    call = "CreateMultipleVerificationsForUser"
    create_multiple_verifications_for_user = getattr(e9y_grpc, call)
    create_multiple_verifications_for_user.return_value = verification_list_response_pb

    params = dict(
        user_id=1,
        verification_type=verification_type,
        verification_data_list=verification_data_list,
        first_name=first_name,
        last_name=last_name,
        date_of_birth=date_of_birth,
        verified_at=verified_at,
        deactivated_at=None,
    )

    # When
    returned_verifications = method(**params)
    # Then
    assert (multiple_verifications_for_user, None) == returned_verifications


def test_create_verification_null_values(e9y_grpc, verification):
    # Given
    verification_pb_response = e9ypb.VerificationForUser(
        verification_id=verification.verification_id,
        user_id=verification.user_id,
        organization_id=verification.organization_id,
        unique_corp_id=verification.unique_corp_id,
        date_of_birth=verification.date_of_birth.isoformat(),
        verification_type=verification.verification_type,
        record=json.dumps(verification.record),
        effective_range=e9ypb.DateRange(
            lower=verification.effective_range.lower.isoformat(),
            upper=verification.effective_range.upper.isoformat(),
            upper_inc=verification.effective_range.upper_inc,
            lower_inc=verification.effective_range.lower_inc,
        ),
    )
    params = dict(
        user_id=verification.user_id,
        verification_type=verification.verification_type,
        organization_id=verification.organization_id,
        unique_corp_id=verification.unique_corp_id,
        dependent_id=verification.dependent_id,
        first_name=verification.first_name,
        last_name=verification.last_name,
        email=verification.email,
        work_state=verification.work_state,
        date_of_birth=verification.date_of_birth,
        eligibility_member_id=verification.eligibility_member_id,
    )
    method = grpc_service.create_verification
    call = "CreateVerificationForUser"
    create_verification = getattr(e9y_grpc, call)
    create_verification.return_value = verification_pb_response

    # When
    returned_verification, _ = method(**params)
    # Then
    assert returned_verification.dependent_id is None
    assert returned_verification.first_name is None
    assert returned_verification.last_name is None
    assert returned_verification.email is None
    assert returned_verification.work_state is None
    assert returned_verification.eligibility_member_id is None


def test_create_verifications_no_retry_for_invalid_argument(
    e9y_grpc,
    verification,
):
    # Given
    method = grpc_service.create_verification
    call = "CreateVerificationForUser"
    create_verification = getattr(e9y_grpc, call)

    # Create error with non-retriable status code (INVALID_ARGUMENT is not in error_codes_for_retry)
    invalid_argument_error = grpc.RpcError("Invalid argument error")
    invalid_argument_error.code = lambda: grpc.StatusCode.INVALID_ARGUMENT
    invalid_argument_error.details = "Invalid input parameter"

    create_verification.side_effect = invalid_argument_error

    params = dict(
        user_id=verification.user_id,
        verification_type=verification.verification_type,
        organization_id=verification.organization_id,
        unique_corp_id=verification.unique_corp_id,
        dependent_id=verification.dependent_id,
        first_name=verification.first_name,
        last_name=verification.last_name,
        email=verification.email,
        work_state=verification.work_state,
        date_of_birth=verification.date_of_birth,
        eligibility_member_id=verification.eligibility_member_id,
    )

    # When/Then
    with pytest.raises(grpc.RpcError) as exc_info:
        method(**params)

    # Verify error details
    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    # Verify the function was called only once since error was not retriable
    assert create_verification.call_count == 1


def test_create_verification_retry_success(
    e9y_grpc,
    verification,
    verification_response_pb,
):
    # Given
    method = grpc_service.create_verification
    call = "CreateVerificationForUser"
    create_verification = getattr(e9y_grpc, call)

    # Simulate initial failures followed by success
    unavailable_error = grpc.RpcError("Mock GRPC Unavailable Error")
    unavailable_error.code = lambda: grpc.StatusCode.UNAVAILABLE

    create_verification.side_effect = [
        unavailable_error,
        unavailable_error,
        verification_response_pb,
    ]

    # Prepare common parameters
    params = dict(
        user_id=verification.user_id,
        verification_type=verification.verification_type,
        organization_id=verification.organization_id,
        unique_corp_id=verification.unique_corp_id,
        dependent_id=verification.dependent_id,
        first_name=verification.first_name,
        last_name=verification.last_name,
        email=verification.email,
        work_state=verification.work_state,
        date_of_birth=verification.date_of_birth,
        eligibility_member_id=verification.eligibility_member_id,
    )

    # When
    result = method(**params)

    # Then
    assert (verification, None) == result
    # Verify the function was called multiple times
    assert create_verification.call_count == 3


def test_create_verification_retry_failure(
    e9y_grpc,
    verification,
    verification_response_pb,
):
    # Given
    method = grpc_service.create_verification
    call = "CreateVerificationForUser"
    create_verification = getattr(e9y_grpc, call)

    # Simulate initial failures followed by success
    unavailable_error = grpc.RpcError("Mock GRPC Unavailable Error")
    unavailable_error.code = lambda: grpc.StatusCode.UNAVAILABLE

    create_verification.side_effect = [
        unavailable_error,
        unavailable_error,
        unavailable_error,
    ]

    # Prepare common parameters
    params = dict(
        user_id=verification.user_id,
        verification_type=verification.verification_type,
        organization_id=verification.organization_id,
        unique_corp_id=verification.unique_corp_id,
        dependent_id=verification.dependent_id,
        first_name=verification.first_name,
        last_name=verification.last_name,
        email=verification.email,
        work_state=verification.work_state,
        date_of_birth=verification.date_of_birth,
        eligibility_member_id=verification.eligibility_member_id,
    )

    # When
    _, returned_error = method(**params)

    # Then
    assert returned_error.args[0] == grpc.StatusCode.UNAVAILABLE
    # Verify the function was called max retries times
    assert create_verification.call_count == 3


def test_create_multiple_verifications_no_retry_for_invalid_argument(
    e9y_grpc,
    multiple_eligibility_member_records_for_user,
    multiple_verifications_for_user,
):
    # Given
    verification_data_list = []
    for record in multiple_eligibility_member_records_for_user:
        vd = model.VerificationData(
            eligibility_member_id=record.id,
            organization_id=record.organization_id,
            unique_corp_id=record.unique_corp_id,
            dependent_id=record.dependent_id,
            email=record.email,
            work_state=record.work_state,
            additional_fields="",
        )
        verification_data_list.append(vd)

    method = grpc_service.create_multiple_verifications_for_user
    call = "CreateMultipleVerificationsForUser"
    create_multiple_verifications_for_user = getattr(e9y_grpc, call)

    # Create error with non-retriable status code (INVALID_ARGUMENT is not in error_codes_for_retry)
    invalid_argument_error = grpc.RpcError("Invalid argument error")
    invalid_argument_error.code = lambda: grpc.StatusCode.INVALID_ARGUMENT
    invalid_argument_error.details = "Invalid input parameter"

    create_multiple_verifications_for_user.side_effect = invalid_argument_error

    params = dict(
        user_id=1,
        verification_type="alternate",
        verification_data_list=verification_data_list,
        first_name="test",
        last_name="test",
        date_of_birth=datetime.date.today(),
        verified_at=multiple_verifications_for_user[0].verified_at,
        deactivated_at=None,
    )

    # When/Then
    with pytest.raises(grpc.RpcError) as exc_info:
        method(**params)

    # Verify error details
    assert exc_info.value.code() == grpc.StatusCode.INVALID_ARGUMENT
    # Verify the function was called only once since error was not retriable
    assert create_multiple_verifications_for_user.call_count == 1


def test_create_multiple_verifications_retry_success(
    e9y_grpc,
    multiple_eligibility_member_records_for_user,
    multiple_verifications_for_user,
    verification_list_response_pb,
):
    # Prepare verification data list similar to original test
    verification_data_list = []
    for record in multiple_eligibility_member_records_for_user:
        vd = model.VerificationData(
            eligibility_member_id=record.id,
            organization_id=record.organization_id,
            unique_corp_id=record.unique_corp_id,
            dependent_id=record.dependent_id,
            email=record.email,
            work_state=record.work_state,
            additional_fields="",
        )
        verification_data_list.append(vd)

    # Setup mocking to simulate retry scenario
    method = grpc_service.create_multiple_verifications_for_user
    call = "CreateMultipleVerificationsForUser"
    create_multiple_verifications_for_user = getattr(e9y_grpc, call)

    # Simulate initial failures followed by success
    unavailable_error = grpc.RpcError("Mock GRPC Unavailable Error")
    unavailable_error.code = lambda: grpc.StatusCode.UNAVAILABLE

    create_multiple_verifications_for_user.side_effect = [
        unavailable_error,
        unavailable_error,
        verification_list_response_pb,
    ]

    # Prepare common parameters
    params = dict(
        user_id=1,
        verification_type="alternate",
        verification_data_list=verification_data_list,
        first_name="test",
        last_name="test",
        date_of_birth=datetime.date.today(),
        verified_at=multiple_verifications_for_user[0].verified_at,
        deactivated_at=None,
    )

    # When
    returned_verifications = method(**params)

    # Then
    assert (multiple_verifications_for_user, None) == returned_verifications
    # Verify the function was called multiple times
    assert create_multiple_verifications_for_user.call_count == 3


def test_create_multiple_verifications_retry_failure(
    e9y_grpc,
    multiple_eligibility_member_records_for_user,
    multiple_verifications_for_user,
):
    verification_data_list = []
    for record in multiple_eligibility_member_records_for_user:
        vd = model.VerificationData(
            eligibility_member_id=record.id,
            organization_id=record.organization_id,
            unique_corp_id=record.unique_corp_id,
            dependent_id=record.dependent_id,
            email=record.email,
            work_state=record.work_state,
            additional_fields="",
        )
        verification_data_list.append(vd)

    # Setup mocking for continuous failures
    method = grpc_service.create_multiple_verifications_for_user
    call = "CreateMultipleVerificationsForUser"
    create_multiple_verifications_for_user = getattr(e9y_grpc, call)

    # Simulate repeated unavailable errors
    unavailable_error = grpc.RpcError("Mock GRPC Unavailable Error")
    unavailable_error.code = lambda: grpc.StatusCode.UNAVAILABLE

    create_multiple_verifications_for_user.side_effect = [
        unavailable_error,
        unavailable_error,
        unavailable_error,
        unavailable_error,
    ]

    # Prepare common parameters
    params = dict(
        user_id=1,
        verification_type="alternate",
        verification_data_list=verification_data_list,
        first_name="test",
        last_name="test",
        date_of_birth=datetime.date.today(),
        verified_at=multiple_verifications_for_user[0].verified_at,
        deactivated_at=None,
    )

    # When
    _, returned_error = method(**params)

    # Then
    assert returned_error.args[0] == grpc.StatusCode.UNAVAILABLE
    # Verify the function was called max retries times
    assert create_multiple_verifications_for_user.call_count == 3


@pytest.mark.parametrize(
    argnames="method,call,params",
    argvalues=[
        (
            grpc_service.wallet_enablement_by_org_identity_search,
            "GetWalletEnablementByOrgIdentity",
            dict(organization_id=1, unique_corp_id="unique", dependent_id="dependent"),
        ),
    ],
)
def test_wallet_enablement_checks(
    method, call, params, wallet_enablement, wallet_enablement_pb, e9y_grpc
):
    # Given
    check = getattr(e9y_grpc, call)
    check.return_value = wallet_enablement_pb
    # When
    wallet = method(**params)
    # Then
    assert wallet == wallet_enablement


@pytest.mark.parametrize(
    argnames="method,call,params",
    argvalues=[
        (
            grpc_service.wallet_enablement_by_org_identity_search,
            "GetWalletEnablementByOrgIdentity",
            dict(organization_id=1, unique_corp_id="unique", dependent_id="dependent"),
        ),
    ],
)
def test_wallet_enablement_checks_no_end_date(
    method, call, params, wallet_enablement, wallet_enablement_pb, e9y_grpc
):
    # Given
    wallet_enablement.eligibility_end_date = None
    wallet_enablement_pb.eligibility_end_date = ""

    check = getattr(e9y_grpc, call)

    check.return_value = wallet_enablement_pb
    # When
    wallet = method(**params)
    # Then
    assert wallet == wallet_enablement


@pytest.mark.parametrize(
    argnames="method,call,params",
    argvalues=[
        (
            grpc_service.standard,
            "CheckStandardEligibility",
            dict(date_of_birth=datetime.date.today(), company_email="foo"),
        ),
        (
            grpc_service.alternate,
            "CheckAlternateEligibility",
            dict(
                date_of_birth=datetime.date.today(),
                work_state="hyrule",
                first_name="princess",
                last_name="zelda",
            ),
        ),
        (
            grpc_service.client_specific,
            "CheckClientSpecificEligibility",
            dict(
                is_employee=True,
                date_of_birth=datetime.date.today(),
                unique_corp_id="unique",
                organization_id=1,
            ),
        ),
        # TODO: cover client_specific with is_employee=False, own_date_of_birth=datetime.date.today()
        (grpc_service.member_id_search, "GetMemberById", dict(member_id=1)),
        (
            grpc_service.org_identity_search,
            "GetMemberByOrgIdentity",
            dict(organization_id=1, unique_corp_id="unique", dependent_id="dependent"),
        ),
        (
            grpc_service.wallet_enablement_by_org_identity_search,
            "GetWalletEnablementByOrgIdentity",
            dict(organization_id=1, unique_corp_id="unique", dependent_id="dependent"),
        ),
        (
            grpc_service.no_dob_verification,
            "CheckNoDOBEligibility",
            dict(
                email="foo@bar.net",
                first_name="princess",
                last_name="zelda",
            ),
        ),
        (
            grpc_service.employer,
            "CheckEmployerEligibility",
            dict(
                company_email="foo@bar.net",
                date_of_birth=datetime.date.today(),
                dependent_date_of_birth=datetime.date.today(),
                employee_first_name="employee_first_name",
                employee_last_name="employee_last_name",
                first_name="first_name",
                last_name="last_name",
                work_state="CA",
                user_id=1,
            ),
        ),
    ],
)
def test_eligibility_checks_fail(method, call, params, e9y_grpc, grpc_error_with_code):
    # Given
    check = getattr(e9y_grpc, call)
    check.side_effect = grpc_error_with_code
    # When
    member = method(**params)
    # Then
    assert member is None


@pytest.mark.parametrize(
    argnames="method,call,params",
    argvalues=[
        (
            grpc_service.member_search,
            "CheckPreEligibility",
            dict(
                user_id=None,
                first_name="foo",
                last_name="bar",
                date_of_birth=datetime.date.today(),
            ),
        ),
    ],
)
def test_pre_eligibility_check(
    method,
    call,
    params,
    pre_eligibility_response,
    pre_eligibility_response_pb,
    pre9y_grpc,
):
    # Given
    check = getattr(pre9y_grpc, call)
    check.return_value = pre_eligibility_response_pb
    # When
    response = method(**params)
    # Then
    assert response == pre_eligibility_response


@pytest.mark.parametrize(
    argnames="method,call,params",
    argvalues=[
        (
            grpc_service.member_search,
            "CheckPreEligibility",
            dict(
                user_id=None,
                first_name="foo",
                last_name="bar",
                date_of_birth=datetime.date.today(),
            ),
        ),
    ],
)
def test_pre_eligibility_check_fail(
    method,
    call,
    params,
    pre_eligibility_response,
    pre_eligibility_response_pb,
    pre9y_grpc,
    grpc_error_with_code,
):
    # Given
    check = getattr(pre9y_grpc, call)
    check.side_effect = grpc_error_with_code
    # When
    response = method(**params)
    # Then
    assert response is None


def test_member_to_employee(eligibility_member):
    # Given
    expected = dict(
        organization_id=eligibility_member.organization_id,
        eligibility_member_id=eligibility_member.id,
        json=eligibility_member.record.copy(),
        email=eligibility_member.email,
        date_of_birth=eligibility_member.date_of_birth,
        first_name=eligibility_member.first_name,
        last_name=eligibility_member.last_name,
        work_state=eligibility_member.work_state,
        unique_corp_id=eligibility_member.unique_corp_id,
        dependent_id=eligibility_member.dependent_id,
        deleted_at=None,
        address=dict(
            employee_first_name=eligibility_member.first_name,
            employee_last_name=eligibility_member.last_name,
            address_1=eligibility_member.record["address_1"],
            address_2=eligibility_member.record["address_2"],
            city=eligibility_member.record["city"],
            state=eligibility_member.record["state"],
            zip_code=eligibility_member.record["zip_code"],
            country=eligibility_member.record["country"],
        ),
        eligibility_member_2_id=eligibility_member.member_2_id or None,
        eligibility_member_2_version=eligibility_member.member_2_version or None,
    )
    expected["json"]["address"] = expected["address"]
    # When
    translated = svc.member_to_employee(eligibility_member)
    # Then
    translated_dict = {k: getattr(translated, k) for k in expected}
    assert translated_dict == expected


def test_eligibility_member_id_0_to_none(eligibility_member):
    # Given
    eligibility_member.id = 0
    expected = dict(
        organization_id=eligibility_member.organization_id,
        eligibility_member_id=None,
        json=eligibility_member.record.copy(),
        email=eligibility_member.email,
        date_of_birth=eligibility_member.date_of_birth,
        first_name=eligibility_member.first_name,
        last_name=eligibility_member.last_name,
        work_state=eligibility_member.work_state,
        unique_corp_id=eligibility_member.unique_corp_id,
        dependent_id=eligibility_member.dependent_id,
        deleted_at=None,
        address=dict(
            employee_first_name=eligibility_member.first_name,
            employee_last_name=eligibility_member.last_name,
            address_1=eligibility_member.record["address_1"],
            address_2=eligibility_member.record["address_2"],
            city=eligibility_member.record["city"],
            state=eligibility_member.record["state"],
            zip_code=eligibility_member.record["zip_code"],
            country=eligibility_member.record["country"],
        ),
    )
    expected["json"]["address"] = expected["address"]
    # When
    translated = svc.member_to_employee(eligibility_member)
    # Then
    translated_dict = {k: getattr(translated, k) for k in expected}
    assert translated_dict == expected


def test_check_health_profile_happy_path_unaffected_tracks():
    exempt_tracks = (
        TrackName.PARTNER_PREGNANT,
        TrackName.PREGNANCY,
        TrackName.POSTPARTUM,
        TrackName.PARTNER_NEWPARENT,
    )
    for track_name in TrackName:
        if track_name not in exempt_tracks:
            assert svc.check_health_profile(0, None, "", track_name)


@pytest.mark.parametrize(
    argnames=("track_name"),
    argvalues=(
        (
            TrackName.PARTNER_PREGNANT,
            TrackName.PREGNANCY,
            TrackName.POSTPARTUM,
            TrackName.PARTNER_NEWPARENT,
        )
    ),
)
def test_check_health_profile_already_set(
    track_name,
    factories,
):
    recipient = factories.EnterpriseUserFactory.create()
    recipient.health_profile.json = {"due_date": "2024-01-01", "children": [{}]}
    assert svc.check_health_profile(0, recipient, "", track_name)


@pytest.mark.parametrize(
    argnames=("track_name", "can_set_from_partner", "check_field"),
    argvalues=(
        (
            (TrackName.PARTNER_PREGNANT, True, "due_date"),
            (TrackName.PARTNER_PREGNANT, False, "due_date"),
            (TrackName.PREGNANCY, True, "due_date"),
            (TrackName.PREGNANCY, False, "due_date"),
            (TrackName.POSTPARTUM, True, "children"),
            (TrackName.POSTPARTUM, False, "children"),
            (TrackName.PARTNER_NEWPARENT, True, "children"),
            (TrackName.PARTNER_NEWPARENT, False, "children"),
        )
    ),
)
def test_check_health_profile_already_not_already_set(
    factories, track_name, can_set_from_partner, check_field
):
    if can_set_from_partner:
        partner_json = {"due_date": "2024-01-01", "children": [{}]}
    else:
        partner_json = {"children": []}
    recipient = factories.EnterpriseUserFactory.create()
    partner = factories.EnterpriseUserFactory.create()
    partner.health_profile.json = partner_json
    recipient.health_profile.json = {}
    db.session.add_all([partner, recipient])
    db.session.commit()
    assert (
        svc.check_health_profile(partner.id, recipient, "", track_name)
        is can_set_from_partner
    )
    if can_set_from_partner:
        recipient_health_profile_json = (
            db.session.query(HealthProfile.json)
            .filter(HealthProfile.user_id == recipient.id)
            .scalar()
        )
        assert recipient_health_profile_json[check_field] == partner_json[check_field]


@pytest.mark.parametrize(
    "method_name,expected_timeout",
    [
        ("standard", grpc_service.ELIGIBILITY_TIMEOUT_DEFAULT),
        ("alternate", 7.0),
        ("client_specific", 7.0),
        ("member_id_search", grpc_service.ELIGIBILITY_TIMEOUT_DEFAULT),
        ("org_identity_search", grpc_service.ELIGIBILITY_TIMEOUT_DEFAULT),
        ("member_search", 2.0),
        ("wallet_enablement_by_id_search", grpc_service.ELIGIBILITY_TIMEOUT_DEFAULT),
        (
            "wallet_enablement_by_user_id_search",
            grpc_service.ELIGIBILITY_TIMEOUT_DEFAULT,
        ),
        (
            "wallet_enablement_by_org_identity_search",
            grpc_service.ELIGIBILITY_TIMEOUT_DEFAULT,
        ),
        ("get_eligible_features_for_user", 5.0),
        ("create_verification", 5.0),
        ("get_verification", 5.0),
        (
            "create_failed_verification_attempt",
            grpc_service.ELIGIBILITY_TIMEOUT_DEFAULT,
        ),
    ],
)
def test_get_effective_timeout(method_name, expected_timeout):
    # test ELIGIBILITY_TIMEOUT_SETTING
    timeout_wo_override = grpc_service._get_effective_timeout(None, method_name)
    assert timeout_wo_override == expected_timeout

    # test override with passed in
    timeout_w_override = grpc_service._get_effective_timeout(56.78, method_name)
    assert timeout_w_override == 56.78
