from models.FHIR.wallet import WalletInfo
from pytests.factories import EnterpriseUserFactory, ReimbursementWalletUsersFactory


def test_get_wallet_info_by_user_id_returns_user(qualified_alegeus_wallet_hra):
    # wallet.member / wallet.user_id reference here
    user = EnterpriseUserFactory.create()
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
        user_id=user.id,
    )
    wallet_result = WalletInfo.get_wallet_info_by_user_id(user.id)
    assert wallet_result.id == qualified_alegeus_wallet_hra.id


def test_get_wallet_info_by_user_id_returns_none(qualified_alegeus_wallet_hra):
    # wallet.member / wallet.user_id reference here
    user = EnterpriseUserFactory.create()
    ReimbursementWalletUsersFactory.create(
        reimbursement_wallet_id=qualified_alegeus_wallet_hra.id,
        user_id=user.id,
    )
    result = WalletInfo.get_wallet_info_by_user_id(2312321)
    assert result is None
