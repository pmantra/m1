from __future__ import annotations

import dataclasses
from unittest import mock
from unittest.mock import MagicMock

import onelogin.saml2.auth
import pytest

from authn.domain import service
from authn.pytests import factories
from authn.resources import sso
from authn.services.integrations import saml


@pytest.fixture
def mock_session():
    with mock.patch("storage.connection.db") as m:
        yield m


@pytest.fixture(scope="module")
def MockSSOService():
    with mock.patch("authn.domain.service.SSOService") as m:
        with mock.patch(
            "authn.domain.service.get_sso_service", autospec=True, return_value=m
        ) as m:
            yield m


@pytest.fixture
def mock_sso_service(MockSSOService):
    yield MockSSOService.return_value
    MockSSOService.reset_mock()


@pytest.fixture(scope="module")
def MockUserRepository():
    with mock.patch(
        "authn.domain.repository.UserRepository", autospec=True, spec_set=True
    ) as m:
        yield m


@pytest.fixture(scope="module")
def MockUserAuthRepository():
    with mock.patch(
        "authn.domain.repository.UserAuthRepository", autospec=True, spec_set=True
    ) as m:
        yield m


@pytest.fixture
def mock_user_auth_repository(MockUserAuthRepository):
    repo = MockUserAuthRepository.return_value
    repo.create.side_effect = lambda *args, instance, **kwargs: instance
    repo.update.side_effect = lambda *args, instance, **kwargs: instance
    yield repo
    MockUserAuthRepository.reset_mock()


@pytest.fixture
def mock_user_repository(MockUserRepository):
    yield MockUserRepository.return_value
    MockUserRepository.reset_mock()


@pytest.fixture(scope="module")
def MockUserMFARepository():
    with mock.patch(
        "authn.domain.repository.UserMFARepository", autospec=True, spec_set=True
    ) as m:
        yield m


@pytest.fixture
def mock_mfa_repository(MockUserMFARepository):
    repo = MockUserMFARepository.return_value
    repo.create.side_effect = lambda *args, instance, **kwargs: instance
    repo.update.side_effect = lambda *args, instance, **kwargs: instance
    yield repo
    MockUserMFARepository.reset_mock()


@pytest.fixture(scope="module")
def MockOranizationAuthRepository():
    with mock.patch(
        "authn.domain.repository.OrganizationAuthRepository",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture
def mock_organization_auth_repo(MockOranizationAuthRepository):
    repo = MockOranizationAuthRepository.return_value
    repo.create.side_effect = lambda *args, instance, **kwargs: instance
    repo.update.side_effect = lambda *args, instance, **kwargs: instance
    yield repo
    MockOranizationAuthRepository.reset_mock()


@pytest.fixture(scope="module")
def MockIdentityProviderRepository():
    with mock.patch(
        "authn.domain.repository.IdentityProviderRepository",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture
def mock_idp_repository(MockIdentityProviderRepository):
    repo = MockIdentityProviderRepository.return_value
    repo.create.side_effect = lambda *args, instance, **kwargs: instance
    repo.update.side_effect = lambda *args, instance, **kwargs: instance
    yield repo
    MockIdentityProviderRepository.reset_mock()


@pytest.fixture(scope="module")
def MockIDPFieldAliasRepository():
    with mock.patch(
        "authn.domain.repository.IDPFieldAliasRepository",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture
def mock_idp_field_alias_repository(MockIDPFieldAliasRepository):
    repo = MockIDPFieldAliasRepository.return_value
    repo.create.side_effect = lambda *args, instance, **kwargs: instance
    repo.update.side_effect = lambda *args, instance, **kwargs: instance
    yield repo
    MockIDPFieldAliasRepository.reset_mock()


@pytest.fixture(scope="module")
def MockUserExternalIdentityRepository():
    with mock.patch(
        "authn.domain.repository.UserExternalIdentityRepository",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m


@pytest.fixture
def mock_user_external_identity_repository(MockUserExternalIdentityRepository):
    repo = MockUserExternalIdentityRepository.return_value
    repo.create.side_effect = lambda *args, instance, **kwargs: instance
    repo.update.side_effect = lambda *args, instance, **kwargs: instance
    yield repo
    MockUserExternalIdentityRepository.reset_mock()


@pytest.fixture
def mock_mfa_service():
    with mock.patch(
        "authn.domain.service.mfa.MFAService", autospec=True, spec_set=True
    ) as m:
        yield m.return_value


# TODO: Better mock the service
@pytest.fixture(scope="function")
def mock_mfa_service_is_mfa_required_for_user_profile():
    with mock.patch(
        "authn.domain.service.mfa.MFAService.is_mfa_required_for_user_profile"
    ) as m:
        yield m


@pytest.fixture(scope="function")
def mock_mfa_service_is_mfa_required_for_org():
    with mock.patch("authn.domain.service.mfa.MFAService.is_mfa_required_for_org") as m:
        yield m


@pytest.fixture(scope="function")
def mock_mfa_service_get_org_id_by_user_id():
    with mock.patch("authn.domain.service.mfa.MFAService.get_org_id_by_user_id") as m:
        yield m


@pytest.fixture
def mfa_service(
    mock_mfa_repository,
    mock_session,
    mock_user_service,
    mock_organization_auth_repo,
) -> service.mfa.MFAService:
    return service.mfa.MFAService(
        repo=mock_mfa_repository,
        session=mock_session,
        user_service=mock_user_service,
        organization_auth=mock_organization_auth_repo,
    )


@pytest.fixture
def mock_user_service():
    with mock.patch(
        "authn.domain.service.user.UserService", autospec=True, spec_set=True
    ) as m:
        yield m.return_value


@pytest.fixture(scope="function")
def mock_user_service_get_identities():
    with mock.patch("authn.domain.service.user.UserService.get_org_id_by_user_id") as m:
        yield m


@pytest.fixture
def user_service(mock_user_repository) -> service.UserService:
    return service.UserService(
        users=mock_user_repository,
    )


@pytest.fixture
def mock_onelogin_service():
    with mock.patch(
        "authn.services.integrations.saml.OneLoginSAMLVerificationService",
        autospec=True,
        spec_set=True,
    ) as m:
        yield m.return_value


@pytest.fixture
def sso_service(
    mock_user_external_identity_repository,
    mock_idp_repository,
    mock_idp_field_alias_repository,
    mock_user_service,
    mock_onelogin_service,
) -> service.SSOService:
    return service.SSOService(
        identities=mock_user_external_identity_repository,
        idps=mock_idp_repository,
        field_aliases=mock_idp_field_alias_repository,
        users=mock_user_service,
    )


@pytest.fixture(scope="function", autouse=True)
def mock_twilio():
    with mock.patch("authn.services.integrations.twilio", autospec=True) as m:
        with mock.patch("authn.domain.service.mfa.twilio", new=m):
            yield m


@pytest.fixture
def mock_get_organization_id_for_user():
    with mock.patch("tracks.service.TrackSelectionService") as p:
        mock_service = MagicMock()
        mock_service.get_organization_id_for_user = MagicMock()
        p.return_value = mock_service
        yield mock_service.get_organization_id_for_user


@pytest.fixture(scope="package", autouse=True)
def mock_is_valid_number():
    with mock.patch("phonenumbers.is_valid_number", autospec=True) as m:
        m.return_value = True
        yield m


@pytest.fixture(scope="package")
def translation_error() -> saml.SAMLTranslationError:
    attribs = dataclasses.asdict(factories.SAMLAssertionFactory.create())
    auth_object = mock.MagicMock(spec_set=onelogin.saml2.auth.OneLogin_Saml2_Auth)
    auth_object.get_attributes = mock.Mock(return_value=attribs)
    auth_object.get_attribute.side_effect = attribs.get
    return saml.SAMLTranslationError(
        "WTF",
        configuration=mock.MagicMock(spec=saml.OneLoginSAMLConfiguration).return_value,
        auth_object=auth_object,
    )


@pytest.fixture(scope="package")
def verification_error() -> saml.SAMLVerificationError:
    errors = {
        "idp": {"message": "yikes!", "reason": ":shrug:", "codes": ["1234", "5678"]}
    }
    return saml.SAMLVerificationError(
        "Soooo not verified.",
        errors,
        configuration=mock.MagicMock(spec=saml.OneLoginSAMLConfiguration).return_value,
    )


@pytest.fixture(scope="package")
def identity_error() -> service.SSOIdentityError:
    identity = factories.UserExternalIdentityFactory.create()
    provider = factories.IdentityProviderFactory.create()
    assertion = factories.SAMLAssertionFactory.create()
    return service.SSOIdentityError(
        "Who am I?",
        assertion=assertion,
        identity=identity,
        provider=provider,
    )


@pytest.fixture(
    params=[
        "translation_error",
        "verification_error",
        "identity_error",
    ]
)
def sso_error(
    request,
    translation_error,
    verification_error,
    identity_error,
) -> tuple[Exception, int]:
    errors = {
        "translation_error": translation_error,
        "verification_error": verification_error,
        "identity_error": identity_error,
    }
    error = errors[request.param]
    status_code = sso.SAMLConsumerResource._get_status_code(error)
    return error, status_code


@pytest.fixture(scope="function")
def mock_migrate_job():
    with mock.patch("authn.jobs.migrate_users_to_auth0.migrate_users_to_auth0") as m:
        yield m


@pytest.fixture(scope="function")
def mock_import_helper():
    with mock.patch("authn.services.integrations.idp.import_helper") as helper:
        yield helper
