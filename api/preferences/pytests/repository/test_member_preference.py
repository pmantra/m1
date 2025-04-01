import dataclasses

from preferences import models, repository
from preferences.pytests import factories


class TestMemberPreferencesRepository:
    def test_create(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        created_preference: models.Preference,
    ):
        # Given
        member_preference: models.MemberPreference = (
            factories.MemberPreferenceFactory.create_with_preference(
                preference=created_preference,
            )
        )
        input = dict(
            value=member_preference.value,
            member_id=member_preference.member_id,
            preference_id=member_preference.preference_id,
        )
        # When
        created: models.MemberPreference = member_preferences_repository.create(
            instance=member_preference
        )
        output = {f: getattr(created, f) for f in input}
        # Then
        assert output == input

    def test_update(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        created_member_preference: models.MemberPreference,
        faker,
    ):
        # Given
        new_value = faker.name()
        update = dataclasses.replace(created_member_preference, value=new_value)
        # When
        updated_member_preference = member_preferences_repository.update(
            instance=update
        )
        # Then
        assert updated_member_preference.value == new_value

    def test_get(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        created_member_preference: models.MemberPreference,
    ):
        # Given
        member_preference_id = created_member_preference.id
        # When
        fetched_member_preference = member_preferences_repository.get(
            id=member_preference_id
        )
        # Then
        assert fetched_member_preference == created_member_preference

    def test_get_not_found(
        self,
        member_preferences_repository: repository.PreferenceRepository,
    ):
        # Given
        member_preference_id = 999
        # When
        fetched = member_preferences_repository.get(id=member_preference_id)
        # Then
        assert fetched is None

    def test_get_by_member_id(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        created_member_preference: models.MemberPreference,
    ):
        # Given
        member_id = created_member_preference.member_id
        # When
        fetched_member_preference = member_preferences_repository.get_by_member_id(
            member_id=member_id,
        )
        # Then
        assert len(fetched_member_preference) == 1
        assert fetched_member_preference[0] == created_member_preference

    def test_get_by_member_id_not_found(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        created_member_preference: models.MemberPreference,
    ):
        # Given
        member_id = created_member_preference.member_id + 1
        # When
        fetched_member_preference = member_preferences_repository.get_by_member_id(
            member_id=member_id,
        )
        # Then
        assert len(fetched_member_preference) == 0

    def test_get_by_preference_id(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        created_member_preference: models.MemberPreference,
    ):
        # Given
        member_id = created_member_preference.member_id
        preference_id = created_member_preference.preference_id
        # When
        fetched_member_preference = member_preferences_repository.get_by_preference_id(
            member_id=member_id,
            preference_id=preference_id,
        )
        # Then
        assert fetched_member_preference == created_member_preference

    def test_get_by_preference_id__member_id_not_found(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        created_member_preference: models.MemberPreference,
    ):
        # Given
        member_id = created_member_preference.member_id + 1
        preference_id = created_member_preference.preference_id
        # When
        fetched_member_preference = member_preferences_repository.get_by_preference_id(
            member_id=member_id,
            preference_id=preference_id,
        )
        # Then
        assert fetched_member_preference is None

    def test_get_by_preference_id__preference_id_not_found(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        created_member_preference: models.MemberPreference,
    ):
        # Given
        member_id = created_member_preference.member_id
        preference_id = created_member_preference.preference_id + 1
        # When
        fetched_member_preference = member_preferences_repository.get_by_preference_id(
            member_id=member_id,
            preference_id=preference_id,
        )
        # Then
        assert fetched_member_preference is None

    def test_get_by_preference_name(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        preference_repository: repository.PreferenceRepository,
        created_member_preference: models.MemberPreference,
    ):
        # Given
        member_id = created_member_preference.member_id
        preference = preference_repository.get(
            id=created_member_preference.preference_id
        )
        preference_name = preference.name
        # When
        fetched_member_preference = (
            member_preferences_repository.get_by_preference_name(
                member_id=member_id,
                preference_name=preference_name,
            )
        )
        # Then
        assert fetched_member_preference == created_member_preference

    def test_get_by_preference_name__member_id_not_found(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        preference_repository: repository.PreferenceRepository,
        created_member_preference: models.MemberPreference,
    ):
        # Given
        member_id = created_member_preference.member_id + 1
        preference = preference_repository.get(
            id=created_member_preference.preference_id
        )
        preference_name = preference.name
        # When
        fetched_member_preference = (
            member_preferences_repository.get_by_preference_name(
                member_id=member_id,
                preference_name=preference_name,
            )
        )
        # Then
        assert fetched_member_preference is None

    def test_get_by_preference_name__preference_name_not_found(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        preference_repository: repository.PreferenceRepository,
        created_member_preference: models.MemberPreference,
    ):
        # Given
        member_id = created_member_preference.member_id
        preference = preference_repository.get(
            id=created_member_preference.preference_id
        )
        preference_name = f"{preference.name}_NOT_FOUND"
        # When
        fetched_member_preference = (
            member_preferences_repository.get_by_preference_name(
                member_id=member_id,
                preference_name=preference_name,
            )
        )
        # Then
        assert fetched_member_preference is None

    def test_delete(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        created_member_preference: models.MemberPreference,
    ):
        # Given
        member_preference_id = created_member_preference.id
        # When
        count = member_preferences_repository.delete(id=member_preference_id)
        fetched = member_preferences_repository.get(id=member_preference_id)
        # Then
        assert count == 1 and fetched is None

    def test_delete_by_member_id(
        self,
        member_preferences_repository: repository.MemberPreferencesRepository,
        created_member_preference: models.MemberPreference,
    ):
        # Given
        member_id = created_member_preference.member_id
        # When
        count = member_preferences_repository.delete_by_member_id(member_id=member_id)
        # Then
        assert count == 1
