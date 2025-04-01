from unittest import mock

import pytest

from eligibility import service
from eligibility.e9y import model as e9y_model


@pytest.fixture(autouse=True)
def mock_session():
    with mock.patch("storage.connection.db") as m:
        yield m.session


@pytest.fixture()
def eligibility_service(
    mock_organization_repository,
    mock_organization_employee_repository,
    mock_member_repository,
    mock_feature_eligibility_repository,
    mock_sso_service,
    mock_e9y_service,
    mock_session,
    mock_redis_ttl_cache,
):
    mock_e9y_service.member_id_search.return_value = None
    mock_sso_service.fetch_identities.return_value = []
    mock_organization_employee_repository.get_existing_claims.return_value = set()
    mock_organization_employee_repository.get_by_e9y_member_id_or_org_identity.return_value = (
        []
    )
    mock_organization_repository.get_organization_by_user_external_identities.return_value = (
        None,
        None,
    )
    mock_feature_eligibility_repository.get_eligible_features_for_user.return_value = (
        e9y_model.EligibleFeaturesForUserResponse(
            features=[],
            has_population=False,
        )
    )
    mock_feature_eligibility_repository.get_eligible_features_for_user_and_org.return_value = e9y_model.EligibleFeaturesForUserResponse(
        features=[],
        has_population=False,
    )
    mock_feature_eligibility_repository.get_eligible_features_by_sub_population_id.return_value = e9y_model.EligibleFeaturesBySubPopulationIdResponse(
        features=[],
        has_definition=False,
    )
    mock_feature_eligibility_repository.get_sub_population_id_for_user.return_value = (
        None
    )
    mock_feature_eligibility_repository.get_sub_population_id_for_user_and_org.return_value = (
        None
    )
    svc = service.EnterpriseVerificationService(
        employees=mock_organization_employee_repository,
        members=mock_member_repository,
        orgs=mock_organization_repository,
        features=mock_feature_eligibility_repository,
        sso=mock_sso_service,
        session=mock_session,
        org_id_cache=mock_redis_ttl_cache,
    )

    return svc


@pytest.fixture()
def mock_eligibility_service():
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService",
        autospec=True,
        spec_set=True,
    ) as m:
        with mock.patch(
            "eligibility.service.get_verification_service", autospec=True, spec_set=True
        ) as fm:
            svc = m.return_value
            fm.return_value = svc
            yield svc


@pytest.fixture
def mock_run_verification_v1():
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService._run_verification_by_verification_type_v1"
    ) as mock_var:
        yield mock_var


@pytest.fixture
def mock_run_verification_v2():
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService._run_verification_by_verification_type_v2"
    ) as mock_var:
        yield mock_var


@pytest.fixture
def org_enabled_for_e9y_v2():
    with mock.patch(
        "eligibility.utils.verification_utils.VerificationParams.is_organization_enabled_for_e9y_ingestion_v2",
        return_value=True,
    ) as mock_var:
        yield mock_var


@pytest.fixture
def org_disabled_for_e9y_v2():
    with mock.patch(
        "eligibility.utils.verification_utils.VerificationParams.is_organization_enabled_for_e9y_ingestion_v2",
        return_value=False,
    ) as mock_var:
        yield mock_var
