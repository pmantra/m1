from authn.models.user import User
from wallet.models.models import MemberTypeDetails
from wallet.services.reimbursement_benefits import get_member_type_details


class ManagedBenefitsInfo:
    """Queries and retrieves the user's direct payment information based on their member details."""

    @classmethod
    def get_mmb_info_by_user(cls, user: User) -> MemberTypeDetails:
        """
        Uses the get_member_type_details function from reimbursement_benefits
        to get info about the member's reimbursement and wallet settings
        which will be used to determine MMB info surfaced in MPractice
        """

        return get_member_type_details(user)
