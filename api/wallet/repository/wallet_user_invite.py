from __future__ import annotations

import sqlalchemy

from authn.models.user import User
from storage import connection
from storage.connector import RoutingSession
from wallet.models.wallet_user_invite import WalletUserInvite


class WalletUserInviteRepository:
    def __init__(
        self,
        session: sqlalchemy.orm.scoping.ScopedSession | RoutingSession | None = None,
    ):
        self.session = session or connection.db.session

    def get_latest_unclaimed_invite(
        self,
        user_id: int,
    ) -> WalletUserInvite | None:
        return (
            self.session.query(WalletUserInvite)
            .join(User, User.email == WalletUserInvite.email)
            .filter(
                User.id == user_id,
                WalletUserInvite.claimed == False,
            )
            .order_by(WalletUserInvite.created_at.desc())
            .first()
        )

    def get_invitation_by_id(self, invitation_id: str) -> WalletUserInvite | None:
        return (
            self.session.query(WalletUserInvite)
            .filter(WalletUserInvite.id == invitation_id)
            .one_or_none()
        )
