import luhn

from wallet.utils.wallet_benefit_id import generate_wallet_benefit


def test_generate_benefit_id():
    wallet_benefit_id = generate_wallet_benefit()

    assert wallet_benefit_id.maven_benefit_id == str(wallet_benefit_id.rand) + str(
        wallet_benefit_id.incremental_id
    ) + str(wallet_benefit_id.checksum)
    assert luhn.verify(wallet_benefit_id.maven_benefit_id)
