import pytest

from authn.domain import model, repository
from authn.pytests import factories
from models.enterprise import Organization
from pytests import factories as common_factories
from pytests.factories import OrganizationFactory


@pytest.fixture
def user_repository(session) -> repository.UserRepository:
    return repository.UserRepository(session=session, is_in_uow=True)


@pytest.fixture
def user_auth_repository(session) -> repository.UserAuthRepository:
    return repository.UserAuthRepository(session=session, is_in_uow=True)


@pytest.fixture
def organization_auth_repository(session) -> repository.OrganizationAuthRepository:
    return repository.OrganizationAuthRepository(session=session, is_in_uow=True)


@pytest.fixture
def user_mfa_repository(session) -> repository.UserMFARepository:
    return repository.UserMFARepository(session=session, is_in_uow=True)


@pytest.fixture
def user_metadata_repository(
    session,
) -> repository.UserMetadataRepository:
    return repository.UserMetadataRepository(session=session, is_in_uow=True)


@pytest.fixture
def user_external_identity_repository(
    session,
) -> repository.UserExternalIdentityRepository:
    return repository.UserExternalIdentityRepository(session=session, is_in_uow=True)


@pytest.fixture
def identity_provider_repository(session) -> repository.IdentityProviderRepository:
    return repository.IdentityProviderRepository(session=session, is_in_uow=True)


@pytest.fixture
def idp_field_alias_repository(session) -> repository.IDPFieldAliasRepository:
    return repository.IDPFieldAliasRepository(session=session, is_in_uow=True)


@pytest.fixture
def created_org() -> Organization:
    return OrganizationFactory.create(name="Core Services")


@pytest.fixture
def created_user(user_repository) -> model.User:
    user: model.User = factories.UserFactory.create()
    created: model.User = user_repository.create(instance=user)
    return created


@pytest.fixture
def created_user_auth(user_auth_repository, created_user) -> model.User:
    user_auth: model.UserAuth = factories.UserAuthFactory.create(
        user_id=created_user.id
    )
    result_count = user_auth_repository.create(instance=user_auth)
    return result_count


@pytest.fixture
def created_organization_auth(
    created_org, organization_auth_repository
) -> model.OrganizationAuth:
    organization_auth: model.OrganizationAuth = (
        factories.OrganizationAuthFactory.create(organization_id=created_org.id)
    )
    result = organization_auth_repository.create(instance=organization_auth)
    return result


@pytest.fixture
def created_metadata(created_user, user_metadata_repository) -> model.UserMetadata:
    metadata: model.UserMetadata = factories.UserMetadataFactory.create(
        user_id=created_user.id
    )
    created: model.UserMetadata = user_metadata_repository.create(instance=metadata)
    return created


@pytest.fixture
def created_mfa(created_user, user_mfa_repository) -> model.UserMFA:
    mfa: model.UserMFA = factories.UserMFAFactory.create(user_id=created_user.id)
    created = user_mfa_repository.create(instance=mfa)
    return created


@pytest.fixture
def created_identity_provider(identity_provider_repository) -> model.IdentityProvider:
    idp = identity_provider_repository.create(
        instance=factories.IdentityProviderFactory.create(name="OKTA"),
    )
    return idp


@pytest.fixture
def created_external_identity(
    created_identity_provider,
    created_user,
    user_external_identity_repository,
) -> model.UserExternalIdentity:
    identity: model.UserExternalIdentity = factories.UserExternalIdentityFactory.create(
        identity_provider_id=created_identity_provider.id,
        user_id=created_user.id,
    )
    created = user_external_identity_repository.create(instance=identity)
    return created


@pytest.fixture
def created_oei(created_identity_provider):
    oei = common_factories.OrganizationExternalIDFactory.create(
        identity_provider_id=created_identity_provider.id,
    )
    return oei


@pytest.fixture
def created_idp_field_alias(
    created_identity_provider, idp_field_alias_repository
) -> model.IdentityProviderFieldAlias:
    field_alias = idp_field_alias_repository.create(
        instance=factories.IdentityProviderFieldAliasFactory.create(
            identity_provider_id=created_identity_provider.id
        )
    )
    return field_alias
