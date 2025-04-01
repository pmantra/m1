import dataclasses
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy.exc

from authn.domain import model, repository
from authn.models import sso
from authn.pytests import factories
from storage.connection import db


class TestIdentityProviderRepository:
    def test_create(self, identity_provider_repository):
        # Given
        idp = factories.IdentityProviderFactory.create()
        inputs = (
            idp.name,
            idp.metadata,
        )
        # When
        created = identity_provider_repository.create(
            instance=idp,
        )
        # Then
        assert created.id and (created.name, created.metadata) == inputs

    def test_get(
        self,
        identity_provider_repository: repository.IdentityProviderRepository,
        created_identity_provider: model.IdentityProvider,
    ):
        # Given
        idp_id = created_identity_provider.id
        # When
        idp = identity_provider_repository.get(id=idp_id)
        # Then
        assert idp

    def test_update(
        self,
        identity_provider_repository: repository.IdentityProviderRepository,
        created_identity_provider: model.IdentityProvider,
        faker,
    ):
        # Given
        metadata = faker.bs()

        # When
        updated = identity_provider_repository.update(
            instance=dataclasses.replace(created_identity_provider, metadata=metadata)
        )
        # Then
        assert updated.metadata == metadata

    def test_get_no_idp(
        self, identity_provider_repository: repository.IdentityProviderRepository
    ):
        # Given
        idp_id = 1
        # When
        idp = identity_provider_repository.get(id=idp_id)
        # Then
        assert idp is None

    def test_get_by_name(
        self,
        identity_provider_repository: repository.IdentityProviderRepository,
        created_identity_provider: model.IdentityProvider,
    ):
        # Given
        idp_name = created_identity_provider.name
        # When
        idp = identity_provider_repository.get_by_name(name=idp_name)
        # Then
        assert idp

    def test_get_by_name_no_idp(
        self, identity_provider_repository: repository.IdentityProviderRepository, faker
    ):
        # Given
        name = faker.bs()
        # When
        idp = identity_provider_repository.get_by_name(name=name)
        # Then
        assert idp is None

    def test_all(
        self,
        identity_provider_repository: repository.IdentityProviderRepository,
        created_identity_provider: model.IdentityProvider,
    ):
        # When
        idps = identity_provider_repository.all()
        # Then
        assert idps == [created_identity_provider]

    def test_all_no_idps(self, identity_provider_repository):
        # When
        idps = identity_provider_repository.all()
        # Then
        assert idps == []

    def test_get_all_by_time_range(
        self,
        identity_provider_repository: repository.IdentityProviderRepository,
        created_identity_provider: model.IdentityProvider,
    ):
        # Given
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        # When
        fetched = identity_provider_repository.get_all_by_time_range(
            end=tomorrow, start=yesterday
        )
        # Then
        assert fetched[0] == created_identity_provider


class TestIDPFieldAliasRepository:
    def test_create(
        self,
        identity_provider_repository: repository.IdentityProviderRepository,
        idp_field_alias_repository: repository.IDPFieldAliasRepository,
    ):
        # Given
        idp = identity_provider_repository.create(
            instance=factories.IdentityProviderFactory.create()
        )
        field_alias = factories.IdentityProviderFieldAliasFactory.create(
            identity_provider_id=idp.id
        )
        inputs = (
            field_alias.field,
            field_alias.alias,
            idp.id,
        )
        # When
        created = idp_field_alias_repository.create(
            instance=field_alias,
        )
        # Then
        assert created.id and (created.field, created.alias, idp.id) == inputs

    def test_create_no_idp(
        self, idp_field_alias_repository: repository.IDPFieldAliasRepository
    ):
        # Given
        field_alias = factories.IdentityProviderFieldAliasFactory.create()
        # When/Then
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            idp_field_alias_repository.create(
                instance=field_alias,
            )

    def test_get(
        self,
        idp_field_alias_repository: repository.IDPFieldAliasRepository,
        created_idp_field_alias: model.IdentityProviderFieldAlias,
    ):
        # Given
        field_alias_id = created_idp_field_alias.id
        # When
        field_alias = idp_field_alias_repository.get(id=field_alias_id)
        # Then
        assert field_alias

    def test_update(
        self,
        idp_field_alias_repository: repository.IDPFieldAliasRepository,
        created_idp_field_alias: model.IdentityProviderFieldAlias,
        faker,
    ):
        # Given
        alias = faker.domain_name()

        # When
        updated = idp_field_alias_repository.update(
            instance=dataclasses.replace(created_idp_field_alias, alias=alias)
        )
        # Then
        assert updated.alias == alias

    def test_get_no_field_alias(
        self, idp_field_alias_repository: repository.IDPFieldAliasRepository
    ):
        # Given
        field_alias_id = 1
        # When
        field_alias = idp_field_alias_repository.get(id=field_alias_id)
        # Then
        assert field_alias is None

    def test_get_by_idp_id(
        self,
        idp_field_alias_repository: repository.IDPFieldAliasRepository,
        created_idp_field_alias: model.IdentityProviderFieldAlias,
    ):
        # Given
        idp_id = created_idp_field_alias.identity_provider_id
        # When
        field_aliases = idp_field_alias_repository.get_by_idp_id(idp_id=idp_id)
        # Then
        assert field_aliases == [created_idp_field_alias]

    def test_get_by_idp_id_no_aliases(
        self,
        idp_field_alias_repository: repository.IDPFieldAliasRepository,
    ):
        # Given
        idp_id = 1
        # When
        field_aliases = idp_field_alias_repository.get_by_idp_id(idp_id=idp_id)
        # Then
        assert field_aliases == []

    def test_all(
        self,
        idp_field_alias_repository: repository.IDPFieldAliasRepository,
        created_idp_field_alias: model.IdentityProviderFieldAlias,
    ):
        # When
        field_aliases = idp_field_alias_repository.all()
        # Then
        assert field_aliases == [created_idp_field_alias]

    def test_all_no_idps(self, idp_field_alias_repository):
        # When
        field_aliases = idp_field_alias_repository.all()
        # Then
        assert field_aliases == []


class TestLegacyIdentityTriggers:
    def test_new_external_identity_copied(
        self,
        created_oei,
        created_identity_provider,
        user_external_identity_repository,
    ):
        # Given
        legacy_identity: sso.ExternalIdentity = (
            factories.LegacyExternalIdentityFactory.create(
                organization=created_oei.organization,
                identity_provider_id=created_identity_provider.id,
            )
        )
        db.session.commit()
        # When
        identity = user_external_identity_repository.get_by_reporting_id(
            reporting_id=legacy_identity.rewards_id,
        )

        # Then
        assert identity is not None
        assert (
            identity.user_id,
            identity.unique_corp_id,
            identity.external_user_id,
            identity.external_organization_id,
            identity.reporting_id,
            identity.identity_provider_id,
        ) == (
            legacy_identity.user_id,
            legacy_identity.unique_corp_id,
            legacy_identity.external_user_id,
            created_oei.external_id,
            legacy_identity.rewards_id,
            legacy_identity.identity_provider_id,
        )

    def test_update_external_identity_copied(
        self,
        created_oei,
        created_identity_provider,
        user_external_identity_repository,
        faker,
    ):
        # Given
        legacy_identity: sso.ExternalIdentity = (
            factories.LegacyExternalIdentityFactory.create(
                organization=created_oei.organization,
            )
        )
        db.session.expire(legacy_identity)
        # When
        legacy_identity.unique_corp_id = faker.swift11()
        db.session.flush()
        identity = user_external_identity_repository.get_by_reporting_id(
            reporting_id=legacy_identity.rewards_id,
        )
        # Then
        assert identity is not None
        assert (
            identity.user_id,
            identity.unique_corp_id,
            identity.external_user_id,
            identity.external_organization_id,
            identity.reporting_id,
            identity.identity_provider_id,
        ) == (
            legacy_identity.user_id,
            legacy_identity.unique_corp_id,
            legacy_identity.external_user_id,
            created_oei.external_id,
            legacy_identity.rewards_id,
            legacy_identity.identity_provider_id,
        )

    def test_delete_external_identity_reflected(
        self,
        created_oei,
        created_identity_provider,
        user_external_identity_repository,
    ):
        # Given
        legacy_identity: sso.ExternalIdentity = (
            factories.LegacyExternalIdentityFactory.create(
                organization_id=created_oei.organization_id,
            )
        )
        # When
        db.session.query(sso.ExternalIdentity).filter_by(id=legacy_identity.id).delete()
        db.session.flush()
        identity = user_external_identity_repository.get_by_reporting_id(
            reporting_id=legacy_identity.rewards_id,
        )
        # Then
        assert identity is None


class TestUserExternalIdentityRepository:
    def test_create(
        self,
        user_external_identity_repository,
        identity_provider_repository,
        user_repository,
    ):
        # Given
        identity_provider = identity_provider_repository.create(
            instance=factories.IdentityProviderFactory.create()
        )
        user = user_repository.create(instance=factories.UserFactory.create())
        identity: model.UserExternalIdentity = (
            factories.UserExternalIdentityFactory.create(
                identity_provider_id=identity_provider.id,
                user_id=user.id,
                sso_email="test@example.com",
                auth0_user_id="auth0|abc",
                sso_user_first_name="hello",
                sso_user_last_name="world",
            )
        )
        input = dict(
            external_user_id=identity.external_user_id,
            reporting_id=identity.reporting_id,
            user_id=identity.user_id,
            unique_corp_id=identity.unique_corp_id,
            identity_provider_id=identity.identity_provider_id,
            external_organization_id=identity.external_organization_id,
            sso_email=identity.sso_email,
            auth0_user_id=identity.auth0_user_id,
            sso_user_first_name=identity.sso_user_first_name,
            sso_user_last_name=identity.sso_user_last_name,
        )
        # When
        created_identity = user_external_identity_repository.create(instance=identity)
        output = {f: getattr(created_identity, f) for f in input}
        # Then
        assert output == input

    def test_create_no_idp(
        self,
        user_external_identity_repository: repository.UserExternalIdentityRepository,
        created_user: model.User,
    ):
        # Given
        identity: model.UserExternalIdentity = (
            factories.UserExternalIdentityFactory.create(user_id=created_user.id)
        )
        # When/Then
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            user_external_identity_repository.create(instance=identity)

    def test_create_no_user(
        self,
        user_external_identity_repository: repository.UserExternalIdentityRepository,
        created_identity_provider: model.IdentityProvider,
    ):
        # Given
        identity: model.UserExternalIdentity = (
            factories.UserExternalIdentityFactory.create(
                identity_provider_id=created_identity_provider.id
            )
        )
        # When/Then
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            user_external_identity_repository.create(instance=identity)

    def test_get(
        self,
        user_external_identity_repository: repository.UserExternalIdentityRepository,
        created_external_identity: model.UserExternalIdentity,
    ):
        # Given
        identity_id = created_external_identity.id
        # When
        fetched_identity = user_external_identity_repository.get(id=identity_id)
        # Then
        assert fetched_identity == created_external_identity

    def test_get_no_identity(self, user_external_identity_repository):
        # Given
        identity_id = 1
        # When
        fetched_identity = user_external_identity_repository.get(id=identity_id)
        # Then
        assert fetched_identity is None

    def test_get_by_user_id(
        self,
        user_external_identity_repository: repository.UserExternalIdentityRepository,
        created_external_identity: model.UserExternalIdentity,
    ):
        # Given
        user_id = created_external_identity.user_id
        # When
        fetched_identities = user_external_identity_repository.get_by_user_id(
            user_id=user_id
        )
        # Then
        assert fetched_identities == [created_external_identity]

    def test_get_by_user_id_no_user(self, user_external_identity_repository):
        # Given
        user_id = 1
        # When
        fetched_identities = user_external_identity_repository.get_by_user_id(
            user_id=user_id
        )
        # Then
        assert fetched_identities == []

    def test_get_by_auth0_user_id(
        self,
        user_external_identity_repository,
        identity_provider_repository,
        user_repository,
    ):
        # Given
        identity_provider = identity_provider_repository.create(
            instance=factories.IdentityProviderFactory.create()
        )
        user = user_repository.create(instance=factories.UserFactory.create())
        identity: model.UserExternalIdentity = (
            factories.UserExternalIdentityFactory.create(
                identity_provider_id=identity_provider.id,
                user_id=user.id,
                sso_email="test@example.com",
                auth0_user_id="auth0|abc",
                sso_user_first_name="hello",
                sso_user_last_name="world",
            )
        )
        created_identity = user_external_identity_repository.create(instance=identity)
        # When
        fetched_result = user_external_identity_repository.get_by_auth0_user_id(
            auth0_user_id="auth0|abc"
        )
        # Then
        assert fetched_result.id == created_identity.id

    def test_get_by_reporting_id(
        self,
        user_external_identity_repository: repository.UserExternalIdentityRepository,
        created_external_identity: model.UserExternalIdentity,
    ):
        # Given
        reporting_id = created_external_identity.reporting_id
        # When
        fetched = user_external_identity_repository.get_by_reporting_id(
            reporting_id=reporting_id
        )
        # Then
        assert fetched == created_external_identity

    def test_get_by_reporting_id_no_identity(self, user_external_identity_repository):
        # Given
        reporting_id = "foo"
        # When
        fetched = user_external_identity_repository.get_by_reporting_id(
            reporting_id=reporting_id
        )
        # Then
        assert fetched is None

    def test_get_all_by_time_range(
        self,
        user_external_identity_repository: repository.UserExternalIdentityRepository,
        created_external_identity: model.UserExternalIdentity,
    ):
        # Given
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        # When
        fetched = user_external_identity_repository.get_all_by_time_range(
            end=tomorrow, start=yesterday
        )
        # Then
        assert fetched[0] == created_external_identity

    def test_update(
        self,
        user_external_identity_repository: repository.UserExternalIdentityRepository,
        created_external_identity: model.UserExternalIdentity,
    ):
        # Given
        created_external_identity.sso_email = "sso_email"
        created_external_identity.auth0_user_id = "mock_auth0_user_id"
        created_external_identity.sso_user_first_name = "first name"
        created_external_identity.sso_user_last_name = "last name"

        # When
        updated = user_external_identity_repository.update(
            instance=dataclasses.replace(created_external_identity)
        )
        # Then
        assert updated.sso_email == "sso_email"
        assert updated.auth0_user_id == "mock_auth0_user_id"
        assert updated.sso_user_first_name == "first name"
        assert updated.sso_user_last_name == "last name"
