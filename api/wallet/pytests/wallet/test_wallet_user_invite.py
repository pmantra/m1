from storage.connection import db
from wallet.models.wallet_user_invite import WalletUserInvite


def test_uuids_for_wallet_user_invites(enterprise_user, qualified_alegeus_wallet_hra):
    num_invites_to_create = 20
    invitations = [
        WalletUserInvite(
            created_by_user_id=enterprise_user.id,
            reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
            date_of_birth_provided="2023-11-03",
            email="wembanyama@height.fr",
        )
        for _ in range(num_invites_to_create)
    ]
    db.session.add_all(invitations)
    db.session.commit()

    invites = db.session.query(WalletUserInvite).all()
    assert all(invites), "Failed to persist and load wallet_user_invites!"

    first = invites[0]

    first_id = str(first.id)

    # Test the ability to query based on str
    first_invitation = (
        db.session.query(WalletUserInvite).filter(WalletUserInvite.id == first_id).one()
    )
    assert first_invitation == first
