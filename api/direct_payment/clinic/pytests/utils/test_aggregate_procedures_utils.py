import datetime
from unittest.mock import patch

from direct_payment.clinic.utils.aggregate_procedures_utils import (
    get_benefit_e9y_start_and_expiration_date,
)
from direct_payment.treatment_procedure.utils.procedure_utils import (
    calculate_benefits_expiration_date,
)
from eligibility.pytests import factories as eligibility_factories
from pytests import factories
from wallet.models.constants import WalletState
from wallet.pytests.factories import ReimbursementWalletFactory


def test_get_benefit_e9y_start_and_expiration_date():
    enterprise_user = factories.EnterpriseUserFactory.create()
    wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
    factories.ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    e9y_start_date = datetime.date.today() - datetime.timedelta(days=30)
    e9y_end_date = datetime.date.today() + datetime.timedelta(days=100)
    benefit_expires_date = calculate_benefits_expiration_date
    e9y_wallet_enablement = eligibility_factories.WalletEnablementFactory.create(
        member_id=1,
        start_date=e9y_start_date,
        eligibility_end_date=e9y_end_date,
    )
    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search",
        return_value=e9y_wallet_enablement,
    ) as mock_service:
        (
            member_eligibility_start_date,
            benefit_expires_date,
        ) = get_benefit_e9y_start_and_expiration_date(wallet, enterprise_user.id)

        mock_service.assert_called_once()
        assert member_eligibility_start_date == e9y_start_date
        assert benefit_expires_date == benefit_expires_date


def test_get_benefit_e9y_start_and_expiration_date_no_wallet_enablement_found():
    enterprise_user = factories.EnterpriseUserFactory.create()
    wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)
    factories.ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    e9y_wallet_enablement = None

    with patch(
        "eligibility.e9y.grpc_service.wallet_enablement_by_user_id_search",
        return_value=e9y_wallet_enablement,
    ) as mock_service:
        (
            member_eligibility_start_date,
            benefit_expires_date,
        ) = get_benefit_e9y_start_and_expiration_date(wallet, enterprise_user.id)

        mock_service.assert_called_once()
        assert member_eligibility_start_date is None
        assert benefit_expires_date is None
