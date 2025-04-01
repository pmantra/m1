from tracks import TrackSelectionService
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository


class WalletInfo:
    """Queries and retrieves the user's wallet information."""

    @classmethod
    def get_wallet_info_by_user_id(cls, user_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Gets information about a user's wallet.
        If the user does not have a wallet, use their org to get the settings information.
        """
        if wallet := ReimbursementWalletRepository().get_wallet_by_active_user_id(
            user_id
        ):
            return wallet

        track_svc = TrackSelectionService()
        return track_svc.get_organization_for_user(user_id=user_id)
