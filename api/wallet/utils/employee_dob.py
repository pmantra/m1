from typing import Optional

from health.models.health_profile import HealthProfile
from wallet.models.reimbursement_wallet import ReimbursementWallet


def get_employee_health_profile_dob(wallet: ReimbursementWallet) -> Optional[str]:
    has_maven_benefit = bool(
        wallet.employee_member and wallet.employee_member.is_employee_with_maven_benefit
    )

    if has_maven_benefit:
        health_profile = HealthProfile.query.filter(
            HealthProfile.user_id == wallet.member.id
        ).one_or_none()

        date_of_birth = health_profile and health_profile.birthday
        return date_of_birth
    else:
        return None
