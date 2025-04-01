from typing import List

from authn.domain.service import UserService
from direct_payment.clinic.models.clinic import FertilityClinicAllowedDomain
from direct_payment.clinic.models.user import AccountStatus
from direct_payment.clinic.repository.user import FertilityClinicUserRepository
from direct_payment.clinic.utils.clinic_helpers import get_user_email_domain


class FertilityClinicUserService:
    def __init__(self) -> None:
        self.repository = FertilityClinicUserRepository()
        self.user_service = UserService()

    def get_active_user_ids_on_allowed_domain(
        self, allowed_domain: FertilityClinicAllowedDomain
    ) -> List[int]:
        fertility_clinic_user_profiles = self.repository.get_by_fertility_clinic_id(
            fertility_clinic_id=allowed_domain.fertility_clinic.id,
            status=AccountStatus.ACTIVE,
        )

        # While it would be possible to just fetch by {'email_like': f"%@{allowed_domain.domain}"}
        # that would return all users - practitioner, member, and fertility clinic, so further processing
        # would still be required to accurately check for active fc users
        users = self.user_service.get_all_by_ids(
            [profile.user_id for profile in fertility_clinic_user_profiles]
        )

        active_users_on_domain = []
        for u in users:
            domain = get_user_email_domain(u.email)
            if domain == allowed_domain.domain:
                active_users_on_domain.append(u.id)

        return active_users_on_domain  # type: ignore[return-value] # Incompatible return value type (got "List[Optional[int]]", expected "List[int]")
