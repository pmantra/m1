from typing import List
from unittest import mock

import grpc
import pytest

from eligibility import e9y, repository
from eligibility.pytests.factories import (
    EligibilityMemberFactory,
    PreEligibilityOrganizationFactory,
    PreEligibilityResponseFactory,
    VerificationAttemptFactory,
    VerificationFactory,
    WalletEnablementFactory,
)
from eligibility.utils.feature_flags import NO_DOB_VERIFICATION, OVER_ELIGIBILITY


@pytest.fixture
def organization_employee_repository(session):
    return repository.OrganizationEmployeeRepository(session=session)


@pytest.fixture
def user_organization_employee_repository(session):
    return repository.UserOrganizationEmployeeRepository(session=session)


@pytest.fixture
def organization_repository(session, mock_sso_service):
    return repository.OrganizationRepository(session=session, sso=mock_sso_service)


@pytest.fixture()
def mock_organization_employee_repository():
    with mock.patch(
        "eligibility.repository.OrganizationEmployeeRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture()
def mock_user_organization_employee_repository():
    with mock.patch(
        "eligibility.repository.UserOrganizationEmployeeRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture()
def mock_organization_repository():
    with mock.patch(
        "eligibility.repository.OrganizationRepository", spec_set=True, autospec=True
    ) as m:
        yield m.return_value


@pytest.fixture()
def mock_member_repository():
    with mock.patch(
        "eligibility.repository.EligibilityMemberRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture()
def mock_feature_eligibility_repository():
    with mock.patch(
        "eligibility.repository.FeatureEligibilityRepository",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m.return_value


@pytest.fixture()
def mock_sso_service():
    with mock.patch(
        "authn.domain.service.SSOService", spec_set=True, autospec=True
    ) as m:
        yield m.return_value


@pytest.fixture()
def mock_e9y_service():
    with mock.patch("eligibility.e9y.grpc_service", spec_set=True, autospec=True) as m:
        yield m


@pytest.fixture()
def mock_associate_user_id_to_members():
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.associate_user_id_to_members"
    ) as m:
        yield m


@pytest.fixture()
def mock_generate_multiple_verifications_for_user():
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.generate_multiple_verifications_for_user",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m


@pytest.fixture()
def mock_retry_create_associations():
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.retry_create_associations",
        spec_set=True,
        autospec=True,
    ) as m:
        yield m


@pytest.fixture
def eligibility_member() -> e9y.EligibilityMember:
    return EligibilityMemberFactory.create()


@pytest.fixture
def eligibility_member_list() -> List[e9y.EligibilityMember]:
    return [EligibilityMemberFactory.create() for _ in range(5)]


@pytest.fixture
def multiple_eligibility_member_records_for_user() -> List[e9y.EligibilityMember]:
    organization_ids = [11, 22]
    members = []
    for organization_id in organization_ids:
        member = EligibilityMemberFactory.create(
            organization_id=organization_id,
        )
        members.append(member)
    return members


@pytest.fixture
def wallet_enablement(eligibility_member) -> e9y.WalletEnablement:
    return WalletEnablementFactory.create(
        member_id=eligibility_member.id,
        organization_id=eligibility_member.organization_id,
    )


@pytest.fixture
def verification() -> e9y.EligibilityVerification:
    return VerificationFactory.create()


@pytest.fixture
def multiple_verifications_for_user() -> List[e9y.EligibilityVerification]:
    user_id = 1
    organization_ids = [11, 22]
    verifications = []
    for organization_id in organization_ids:
        verification = VerificationFactory.create(
            user_id=user_id,
            organization_id=organization_id,
        )
        verifications.append(verification)
    return verifications


@pytest.fixture
def verification_attempt() -> e9y.EligibilityVerificationAttempt:
    return VerificationAttemptFactory.create()


@pytest.fixture
def pre_eligibility_response() -> e9y.PreEligibilityResponse:
    return PreEligibilityResponseFactory.create()


@pytest.fixture
def pre_eligibility_organization() -> e9y.PreEligibilityOrganization:
    return PreEligibilityOrganizationFactory.create()


@pytest.fixture
def grpc_error_with_code() -> grpc.RpcError:
    grpc_error = grpc.RpcError("Mock GRPC Error")
    grpc_error.code = lambda: grpc.StatusCode.UNIMPLEMENTED
    return grpc_error


@pytest.fixture
def mock_no_dob_verification_enabled(ff_test_data):
    def _mock(is_on: bool = True):
        ff_test_data.update(
            ff_test_data.flag(NO_DOB_VERIFICATION).variation_for_all(is_on)
        )

    return _mock


@pytest.fixture
def mock_overeligibility_enabled(ff_test_data):
    def _mock(is_on: bool = True):
        ff_test_data.update(
            ff_test_data.flag(OVER_ELIGIBILITY).variation_for_all(is_on)
        )

    return _mock
