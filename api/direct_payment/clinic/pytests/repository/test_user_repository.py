import pytest

from direct_payment.clinic.models.user import AccountStatus


class TestFertilityClinicUserRepository:
    def test_get(self, active_fc_user, fertility_clinic_user_repository):
        assert (
            fertility_clinic_user_repository.get(
                fertility_clinic_user_profile_id=active_fc_user.id
            ).id
            == active_fc_user.id
        )

    def test_get_by_user_id(self, active_fc_user, fertility_clinic_user_repository):
        assert (
            fertility_clinic_user_repository.get_by_user_id(
                user_id=active_fc_user.user_id
            ).id
            == active_fc_user.id
        )

    @pytest.mark.parametrize(
        argnames="clinic_id,status,expected_status",
        argvalues=[
            (1, None, AccountStatus.ACTIVE),
            (1, AccountStatus.INACTIVE, AccountStatus.INACTIVE),
        ],
    )
    def test_get_by_fertility_clinic_id(
        self, clinic_id, status, expected_status, fertility_clinic_user_repository
    ):
        profiles = fertility_clinic_user_repository.get_by_fertility_clinic_id(
            fertility_clinic_id=clinic_id,
            status=status,
        )
        for profile in profiles:
            assert any(clinic.id == clinic_id for clinic in profile.clinics)
            assert profile.status == expected_status
