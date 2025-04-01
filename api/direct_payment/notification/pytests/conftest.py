import uuid

import pytest

from direct_payment.billing.pytests import factories as bill_factories
from pytests import factories
from wallet.models.constants import WalletUserStatus, WalletUserType
from wallet.pytests import factories as wallet_factories


@pytest.fixture
def notified_user():
    user = factories.EnterpriseUserFactory.create()
    return user


@pytest.fixture
def notified_user_wallet():
    def fn(inp_user):
        res = wallet_factories.ReimbursementWalletFactory.create(
            payments_customer_id=str(uuid.uuid4())
        )

        wallet_factories.ReimbursementWalletUsersFactory.create(
            user_id=inp_user.id,
            reimbursement_wallet_id=res.id,
            type=WalletUserType.EMPLOYEE,
            status=WalletUserStatus.ACTIVE,
        )
        return res

    return fn


@pytest.fixture
def non_notified_user_wallet():
    res = wallet_factories.ReimbursementWalletFactory.create(
        payments_customer_id=str(uuid.uuid4())
    )
    return res


@pytest.fixture
def notified_user_bill():
    def fn(inp_wallet):
        res = bill_factories.BillFactory.build(
            payor_id=inp_wallet.id,
        )
        return res

    return fn


@pytest.fixture
def non_notified_user_bill(non_notified_user_wallet):
    return bill_factories.BillFactory.build(
        payor_id=non_notified_user_wallet.id,
    )
