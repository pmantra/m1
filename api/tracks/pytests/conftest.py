from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from unittest import mock

import pytest

from eligibility import service
from eligibility.pytests import factories as e9y_factories
from models.tracks import TrackName
from tracks import repository
from tracks import service as tracks_service

if TYPE_CHECKING:
    from models.enterprise import OrganizationEmployee, UserOrganizationEmployee
    from models.tracks.client_track import ClientTrack


@pytest.fixture
def tracks_repository(session):
    return repository.TracksRepository(session=session)


@pytest.fixture
def org_employee(default_user, factories) -> "OrganizationEmployee":
    return factories.OrganizationEmployeeFactory.create(email=default_user.email)


@pytest.fixture
def user_organization_employee(
    default_user, org_employee, factories
) -> "UserOrganizationEmployee":
    return factories.UserOrganizationEmployeeFactory.create(
        user=default_user, organization_employee=org_employee
    )


@pytest.fixture
def mock_org_with_track(factories):
    organization = factories.OrganizationFactory.create()
    factories.ClientTrackFactory.create(
        organization=organization, track=TrackName.ADOPTION
    )
    return organization


@pytest.fixture
def client_track(org_employee, factories) -> "ClientTrack":
    return factories.ClientTrackFactory.create(organization=org_employee.organization)


@pytest.fixture
def verification_service(session, mock_e9y_service):
    svc = service.EnterpriseVerificationService(session=session)
    svc.e9y.grpc = mock_e9y_service
    yield svc


@pytest.fixture
def mock_valid_verification(default_user, mock_org_with_track):
    verification = e9y_factories.VerificationFactory.create(
        user_id=default_user.id,
        organization_id=mock_org_with_track.id,
        eligibility_member_id=1,
        verification_id=2,
    )
    verification.effective_range.upper = datetime.utcnow().date() + timedelta(days=365)
    return verification


@pytest.fixture(autouse=True)
def patch_get_verification_for_user(mock_valid_verification):
    with mock.patch(
        "eligibility.EligibilityMemberRepository.get_verification_for_user",
        return_value=mock_valid_verification,
    ):
        yield mock_valid_verification


@pytest.fixture(autouse=True)
def patch_get_verification_for_user_and_org(mock_valid_verification):
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=mock_valid_verification,
    ):
        yield mock_valid_verification


@pytest.fixture(scope="package", autouse=True)
def apply_patch_e9y_service_functions(patch_e9y_service_functions):
    yield


@pytest.fixture()
def track_service() -> tracks_service.TrackSelectionService:
    svc = tracks_service.TrackSelectionService()
    return svc
