from direct_payment.notification.lib.user_inference_library import (
    get_user_from_wallet_or_payor_id,
)


class TestUserInferenceLibrary:
    def test_get_user_from_wallet_or_payor_id(
        self, notified_user, notified_user_wallet, notified_user_bill
    ):
        wallet = notified_user_wallet(notified_user)
        bill = notified_user_bill(wallet)
        res_wallet_user = get_user_from_wallet_or_payor_id(wallet.id)
        assert {notified_user} == set(res_wallet_user)
        res_bill_user = get_user_from_wallet_or_payor_id(bill.payor_id)
        assert {notified_user} == set(res_bill_user)

    def test_get_user_from_wallet_id_failed(
        self, notified_user, non_notified_user_wallet
    ):
        res = get_user_from_wallet_or_payor_id(non_notified_user_wallet.id)
        assert {notified_user} != set(res)

    def test_get_user_from_payor_id_failed(
        self,
        non_notified_user_bill,
        notified_user,
    ):
        res = get_user_from_wallet_or_payor_id(non_notified_user_bill.payor_id)
        assert {notified_user} != set(res)
