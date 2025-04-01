import pytest
from werkzeug.exceptions import NotFound

from wallet.resources.reimbursement_wallet_bank_account import (
    UserReimbursementWalletBankAccountResource,
)


def test_wallet_or_404__success(qualified_wallet, enterprise_user):
    qualified_wallet.member = enterprise_user

    resource = UserReimbursementWalletBankAccountResource()
    wallet = resource._wallet_or_404(enterprise_user, qualified_wallet.id)

    assert wallet is not None


def test_wallet_or_404__fail_wallet_does_not_exist(enterprise_user, logs):
    wallet_id = -1
    resource = UserReimbursementWalletBankAccountResource()
    error_msg = f"Could not find associated wallet with ID={wallet_id}"
    with pytest.raises(NotFound, match="404 Not Found"):
        wallet = resource._wallet_or_404(enterprise_user, wallet_id)
        log = next((r for r in logs if error_msg in r["event"]), None)
        assert wallet is None
        assert log is not None


def test_wallet_or_404__fail_wallet_not_associated_with_user(
    qualified_wallet, enterprise_user, logs
):
    resource = UserReimbursementWalletBankAccountResource()
    error_msg = f"Wallet with ID={qualified_wallet.id} is not associated with User ID={enterprise_user.id}"
    with pytest.raises(NotFound, match="404 Not Found"):
        wallet = resource._wallet_or_404(enterprise_user, qualified_wallet.id)
        log = next((r for r in logs if error_msg in r["event"]), None)
        assert wallet is None
        assert log is not None
