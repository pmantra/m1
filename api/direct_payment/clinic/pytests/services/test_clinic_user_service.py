from direct_payment.clinic.models.user import AccountStatus, FertilityClinicUserProfile
from direct_payment.clinic.pytests.factories import FertilityClinicAllowedDomainFactory
from direct_payment.clinic.services.user import FertilityClinicUserService
from direct_payment.clinic.utils.clinic_helpers import get_user_email_domain


def test_get_active_user_ids_on_allowed_domain_multiple(fertility_clinic_with_users):
    allowed_domain = fertility_clinic_with_users.allowed_domains[0]
    active_user_ids = (
        FertilityClinicUserService().get_active_user_ids_on_allowed_domain(
            allowed_domain
        )
    )
    for id in active_user_ids:
        u = FertilityClinicUserProfile.query.filter(
            FertilityClinicUserProfile.user_id == id
        ).one_or_none()
        assert u is not None
        assert get_user_email_domain(u.email) == allowed_domain.domain
        assert u.status == AccountStatus.ACTIVE


def test_get_active_user_ids_on_allowed_domain_none(fertility_clinic_with_users):
    unused_domain = FertilityClinicAllowedDomainFactory(
        domain="notused.com", fertility_clinic=fertility_clinic_with_users
    )
    active_user_ids = (
        FertilityClinicUserService().get_active_user_ids_on_allowed_domain(
            unused_domain
        )
    )
    assert len(active_user_ids) == 0
