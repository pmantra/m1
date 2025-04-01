from __future__ import annotations

from flask_restful import abort

from common.services.api import PermissionedUserResource
from utils.log import logger
from wallet.models.models import MemberWalletStateSchema
from wallet.services.reimbursement_wallet import ReimbursementWalletService

log = logger(__name__)


class ReimbursementWalletStateResource(PermissionedUserResource):
    def __init__(self) -> None:
        self.wallet_service = ReimbursementWalletService()

    def get(self) -> dict | None:
        try:
            member_wallet_state: MemberWalletStateSchema = (
                self.wallet_service.get_member_wallet_state(user=self.user)
            )
        except Exception as e:
            log.exception(
                "Exception encountered while fetching MemberWalletState",
                user_id=self.user.id,
                error=e,
            )
            abort(500, message=f"Could not complete request {e}")
            return None
        else:
            return member_wallet_state.serialize()
