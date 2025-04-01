import dataclasses

import pytest

from authn.domain import model, repository
from authn.pytests import factories


class TestUserMFARepository:
    def test_create(
        self,
        user_mfa_repository: repository.UserMFARepository,
        created_user: model.User,
    ):
        # Given
        mfa: model.UserMFA = factories.UserMFAFactory.create(user_id=created_user.id)
        input = dict(
            user_id=mfa.user_id,
            sms_phone_number=mfa.sms_phone_number,
            otp_secret=mfa.otp_secret,
            external_user_id=mfa.external_user_id,
            verified=mfa.verified,
        )
        # When
        created_mfa = user_mfa_repository.create(instance=mfa)
        output = {f: getattr(created_mfa, f) for f in input}
        # Then
        assert output == input

    def test_create_no_user(self, user_mfa_repository: repository.UserMFARepository):
        # Given
        mfa: model.UserMFA = factories.UserMFAFactory.create()
        # When
        created_mfa = user_mfa_repository.create(instance=mfa)
        # Then
        assert created_mfa is None

    def test_update(
        self,
        user_mfa_repository: repository.UserMFARepository,
        created_mfa: model.UserMFA,
        faker,
    ):
        # Given
        new_phone = faker.phone_number()
        update = dataclasses.replace(created_mfa, sms_phone_number=new_phone)
        # When
        updated_mfa = user_mfa_repository.update(instance=update)
        # Then
        assert updated_mfa.sms_phone_number == new_phone
        # FIXME: This can't be reliably tested without halting execution for at least a second.
        #   This is because MySQL defaults to one-second resolution on datetimes. Yikes.
        # assert updated_mfa.updated_at > update.updated_at

    def test_update_no_user(self, user_mfa_repository: repository.UserMFARepository):
        # Given
        mfa: model.UserMFA = factories.UserMFAFactory.create()
        # When
        updated = user_mfa_repository.update(instance=mfa)
        # Then
        assert updated is None

    def test_get(
        self,
        user_mfa_repository: repository.UserMFARepository,
        created_mfa: model.UserMFA,
    ):
        # Given
        user_id = created_mfa.user_id
        # When
        fetched_mfa = user_mfa_repository.get(id=user_id)
        # Then
        assert fetched_mfa == created_mfa

    def test_get_no_user(self, user_mfa_repository: repository.UserMFARepository):
        # Given
        user_id = 1
        # When
        fetched = user_mfa_repository.get(id=user_id)
        # Then
        assert fetched is None

    def test_get_no_mfa(
        self,
        user_mfa_repository: repository.UserMFARepository,
        created_user: model.User,
    ):
        # Given
        user_id = created_user.id
        # When
        fetched = user_mfa_repository.get(id=user_id)
        # Then
        assert fetched.mfa_state.value == "disabled"

    @pytest.mark.skip(
        reason="The delete function is update the mfa_state to None, while the field in DB definition can't be None. The code and test code is problematic. Skip for now and need to review the MFA workflow"
    )
    def test_delete(
        self,
        user_mfa_repository: repository.UserMFARepository,
        created_mfa: model.UserMFA,
    ):
        # Given
        user_id = created_mfa.user_id
        # When
        count = user_mfa_repository.delete(id=user_id)
        fetched = user_mfa_repository.get(id=user_id)
        # Then
        assert count == 1 and fetched.mfa_state is None

    def test_delete_no_user(self, user_mfa_repository: repository.UserMFARepository):
        # Given
        user_id = 1
        # When
        affected = user_mfa_repository.delete(id=user_id)
        # Then
        assert affected == 0

    @pytest.mark.xfail(
        reason=(
            "This will currently return 1 if the user exists "
            "because it's not yet an actual table."
        )
    )
    def test_delete_no_mfa(
        self,
        user_mfa_repository: repository.UserMFARepository,
        created_user: model.User,
    ):
        # Given
        user_id = created_user.id
        # When
        affected = user_mfa_repository.delete(id=user_id)
        # Then
        assert affected == 0
