from datetime import datetime, timedelta, timezone

from authn.domain import model, repository
from authn.pytests import factories


class TestOrganizationAuthRepository:
    def test_create(
        self,
        organization_auth_repository: repository.OrganizationAuthRepository,
        created_org,
    ):
        # Given
        organization_auth: model.OrganizationAuth = (
            factories.OrganizationAuthFactory.create(organization_id=created_org.id)
        )
        # When
        created = organization_auth_repository.create(instance=organization_auth)

        # Then
        assert created.organization_id == created_org.id
        assert created.mfa_required is False

    def test_delete_by_organization_id_with_record_in_table(
        self,
        organization_auth_repository: repository.OrganizationAuthRepository,
        created_org,
    ):
        # Given
        organization_auth: model.OrganizationAuth = (
            factories.OrganizationAuthFactory.create(organization_id=created_org.id)
        )
        organization_auth_repository.create(instance=organization_auth)
        to_be_delete_id = created_org.id

        # When
        deleted = organization_auth_repository.delete_by_organization_id(
            organization_id=to_be_delete_id
        )
        fetched = organization_auth_repository.get_by_organization_id(
            organization_id=to_be_delete_id
        )

        # Then
        assert deleted == 1
        assert fetched is None

    def test_delete_by_organization_id_with_record_not_in_table(
        self,
        organization_auth_repository: repository.OrganizationAuthRepository,
    ):
        # Given
        to_be_delete_id = 999

        # When
        deleted = organization_auth_repository.delete_by_organization_id(
            organization_id=to_be_delete_id
        )

        # Then
        assert deleted == 0

    def test_update_with_record_in_table(
        self,
        organization_auth_repository: repository.OrganizationAuthRepository,
        created_org,
    ):
        # Given
        organization_auth: model.OrganizationAuth = (
            factories.OrganizationAuthFactory.create(organization_id=created_org.id)
        )
        organization_auth_repository.create(instance=organization_auth)
        to_be_update_id = created_org.id

        # When
        updated = organization_auth_repository.update_by_organization_id(
            organization_id=to_be_update_id, new_mfa_required=True
        )
        fetched = organization_auth_repository.get_by_organization_id(
            organization_id=to_be_update_id
        )

        # Then
        assert updated == 1
        assert fetched is not None
        assert fetched.mfa_required is True

    def test_update_with_record_not_in_table(
        self,
        organization_auth_repository: repository.OrganizationAuthRepository,
    ):
        # Given
        to_be_update_id = 999

        # When
        updated = organization_auth_repository.update_by_organization_id(
            organization_id=to_be_update_id, new_mfa_required=True
        )
        # Then
        assert updated == 0

    def test_get_all_by_time_range(
        self,
        organization_auth_repository: repository.OrganizationAuthRepository,
        created_org,
    ):
        # Given
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        organization_auth: model.OrganizationAuth = (
            factories.OrganizationAuthFactory.create(organization_id=created_org.id)
        )
        created_org_auth = organization_auth_repository.create(
            instance=organization_auth
        )
        # When
        fetched = organization_auth_repository.get_all_by_time_range(
            end=tomorrow, start=yesterday
        )
        # Then
        assert fetched[0] == created_org_auth
