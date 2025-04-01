from unittest import mock

import pytest

from eligibility import service
from eligibility.e9y import model as e9y_models
from eligibility.pytests import factories as e9y_factories
from eligibility.utils.feature_flags import OVER_ELIGIBILITY
from tracks import repository
from tracks import service as tracks_service


@pytest.fixture(autouse=True)
def _mock_zendesk(mock_zendesk_module):
    with mock.patch("views.enterprise.zendesk", new=mock_zendesk_module):
        yield


@pytest.fixture
def verification_service(session, mock_e9y_service):
    svc = service.EnterpriseVerificationService(session=session)
    svc.e9y.grpc = mock_e9y_service
    svc.e9y.grpc_connection = mock.ANY
    yield svc


@pytest.fixture(scope="package", autouse=True)
def apply_patch_e9y_service_functions(patch_e9y_service_functions):
    yield


@pytest.fixture(scope="package", autouse=False)
def verification() -> e9y_models.EligibilityVerification:
    return e9y_factories.VerificationFactory.create()


@pytest.fixture
def tracks_repository(session):
    return repository.TracksRepository(session=session)


@pytest.fixture()
def track_service() -> tracks_service.TrackSelectionService:
    svc = tracks_service.TrackSelectionService()
    return svc


@pytest.fixture
def mock_overeligibility_enabled(ff_test_data):
    def _mock(is_on: bool = False):
        ff_test_data.update(
            ff_test_data.flag(OVER_ELIGIBILITY).variation_for_all(is_on)
        )

    return _mock
