import dataclasses

import pytest

from authn.domain import model, repository
from authn.pytests import factories


class TestUserMetadataRepository:
    def test_create(
        self,
        user_repository: repository.UserRepository,
        user_metadata_repository: repository.UserMetadataRepository,
        created_user: model.User,
    ):
        # Given
        metadata: model.UserMetadata = factories.UserMetadataFactory.create(
            user_id=created_user.id
        )
        input = dict(
            user_id=metadata.user_id,
            zendesk_user_id=metadata.zendesk_user_id,
            first_name=metadata.first_name,
            last_name=metadata.last_name,
            timezone=metadata.timezone,
            middle_name=metadata.middle_name,
            image_id=metadata.image_id,
        )
        # When
        created_metadata = user_metadata_repository.create(instance=metadata)
        output = {f: getattr(created_metadata, f) for f in input}
        # Then
        assert output == input

    def test_create_no_user(
        self, user_metadata_repository: repository.UserMetadataRepository
    ):
        # Given
        metadata: model.UserMetadata = factories.UserMetadataFactory.create()
        # When
        created = user_metadata_repository.create(instance=metadata)
        # Then
        assert created is None

    def test_update(
        self,
        user_metadata_repository: repository.UserMetadataRepository,
        created_metadata: model.UserMetadata,
        faker,
    ):
        # Given
        new_last_name = faker.last_name()
        update = dataclasses.replace(created_metadata, last_name=new_last_name)
        # When
        updated_metadata = user_metadata_repository.update(instance=update)
        # Then
        assert updated_metadata.last_name == new_last_name
        # FIXME: This can't be reliably tested without halting execution for at least a second.
        #   This is because MySQL defaults to one-second resolution on datetimes. Yikes.
        # assert updated_metadata.updated_at > update.updated_at

    def test_update_no_user(
        self, user_metadata_repository: repository.UserMetadataRepository
    ):
        # Given
        metadata: model.UserMetadata = factories.UserMetadataFactory.create()
        # When
        updated = user_metadata_repository.update(instance=metadata)
        # Then
        assert updated is None

    def test_get(
        self,
        user_metadata_repository: repository.UserMetadataRepository,
        created_metadata: model.UserMetadata,
    ):
        # Given
        user_id = created_metadata.user_id
        # When
        fetched_metadata = user_metadata_repository.get(id=user_id)
        # Then
        assert fetched_metadata == created_metadata

    def test_get_no_user(
        self, user_metadata_repository: repository.UserMetadataRepository
    ):
        # Given
        user_id = 1
        # When
        fetched = user_metadata_repository.get(id=user_id)
        # Then
        assert fetched is None

    def test_get_no_metadata(
        self,
        user_repository: repository.UserRepository,
        user_metadata_repository: repository.UserMetadataRepository,
        created_user: model.User,
    ):
        # Given
        user = factories.UserFactory.create(first_name=None, last_name=None)
        created_user = user_repository.create(instance=user)
        user_id = created_user.id
        # When
        fetched = user_metadata_repository.get(id=user_id)
        # Then
        assert fetched is None

    def test_delete(
        self,
        user_metadata_repository: repository.UserMetadataRepository,
        created_metadata: model.UserMetadata,
    ):
        # Given
        user_id = created_metadata.user_id
        # When
        count = user_metadata_repository.delete(id=user_id)
        fetched = user_metadata_repository.get(id=user_id)
        # Then
        assert count == 1 and fetched is None

    def test_delete_no_user(
        self, user_metadata_repository: repository.UserMetadataRepository
    ):
        # Given
        user_id = 1
        # When
        affected = user_metadata_repository.delete(id=user_id)
        # Then
        assert affected == 0

    @pytest.mark.xfail(
        reason=(
            "This will currently return 1 if the user exists "
            "because it's not yet an actual table."
        )
    )
    def test_delete_no_metadata(
        self,
        user_metadata_repository: repository.UserMetadataRepository,
        created_user: model.User,
    ):
        # Given
        user_id = created_user.id
        # When
        affected = user_metadata_repository.delete(id=user_id)
        # Then
        assert affected == 0
