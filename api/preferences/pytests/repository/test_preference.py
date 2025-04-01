import dataclasses

from preferences import models, repository
from preferences.pytests import factories


class TestPreferenceRepository:
    def test_create(self, preference_repository: repository.PreferenceRepository):
        # Given
        preference: models.Preference = factories.PreferenceFactory.create()
        input_ = dict(
            name=preference.name,
            default_value=preference.default_value,
            type=preference.type,
        )
        # When
        created: models.Preference = preference_repository.create(instance=preference)
        output = {f: getattr(created, f) for f in input_}
        # Then
        assert output == input_

    def test_update(
        self,
        preference_repository: repository.PreferenceRepository,
        created_preference: models.Preference,
        faker,
    ):
        # Given
        new_name = faker.name()
        update = dataclasses.replace(created_preference, name=new_name)
        # When
        updated_preference = preference_repository.update(instance=update)
        # Then
        assert updated_preference.name == new_name

    def test_get(
        self,
        preference_repository: repository.PreferenceRepository,
        created_preference: models.Preference,
    ):
        # Given
        preference_id = created_preference.id
        # When
        fetched_preference = preference_repository.get(id=preference_id)
        # Then
        assert fetched_preference == created_preference

    def test_get_not_found(
        self, preference_repository: repository.PreferenceRepository
    ):
        # Given
        preference_id = 999
        # When
        fetched = preference_repository.get(id=preference_id)
        # Then
        assert fetched is None

    def test_get_by_name(
        self,
        preference_repository: repository.PreferenceRepository,
        created_preference: models.Preference,
    ):
        # Given
        preference_name = created_preference.name
        # When
        fetched_preference = preference_repository.get_by_name(name=preference_name)
        # Then
        assert fetched_preference == created_preference

    def test_get_by_name_not_found(
        self,
        preference_repository: repository.PreferenceRepository,
        faker,
    ):
        # Given
        preference_name = faker.word()
        # When
        fetched = preference_repository.get_by_name(name=preference_name)
        # Then
        assert fetched is None

    def test_delete(
        self,
        preference_repository: repository.PreferenceRepository,
        created_preference: models.Preference,
    ):
        # Given
        preference_id = created_preference.id
        # When
        count = preference_repository.delete(id=preference_id)
        fetched = preference_repository.get(id=preference_id)
        # Then
        assert count == 1 and fetched is None
