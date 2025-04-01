from unittest.mock import patch

import pytest

from wallet.models.constants import ReimbursementRequestState, WalletState
from wallet.pytests.factories import (
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
)

"""
We can remove this file once the Wallet / Alegeus integration is fully completed.
See:
    wallet.resources.reimbursement_wallet_bank_account.py,
    wallet.pytests.resources.test_reimbursement_wallet_bank_account.py

"""


@pytest.fixture()
def qualified_wallet(enterprise_user):
    enterprise_user.profile.stripe_account_id = "test"
    wallet = ReimbursementWalletFactory.create(
        member=enterprise_user,
        state=WalletState.QUALIFIED,
        reimbursement_organization_settings__allowed_reimbursement_categories=[
            ("fertility", 5000, None),
            ("other", 3000, None),
        ],
    )
    return wallet


def test_cannot_remove_bank_account_with_in_flight_requests(
    client, qualified_wallet, api_helpers, enterprise_user
):
    category = qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    ReimbursementRequestFactory.create(
        amount=50,
        reimbursement_wallet_id=qualified_wallet.id,
        reimbursement_request_category_id=category.id,
        state=ReimbursementRequestState.PENDING,
    )

    with patch("views.payments.send_general_ticket_to_zendesk") as zd_task:
        res = client.delete(
            f"/api/v1/users/{enterprise_user.id}/bank_accounts",
            headers=api_helpers.json_headers(enterprise_user),
        )
        content = api_helpers.load_json(res)
        assert res.status_code == 200
        assert content["data"] is None
        assert len(content["errors"]) == 1
        assert zd_task.call_count == 1


def test_can_remove_bank_account(client, qualified_wallet, api_helpers):
    category = qualified_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    ReimbursementRequestFactory.create(
        amount=50,
        reimbursement_wallet_id=qualified_wallet.id,
        reimbursement_request_category_id=category.id,
        state=ReimbursementRequestState.REIMBURSED,
    )

    with patch("views.payments.send_general_ticket_to_zendesk") as zd_task:
        res = client.delete(
            f"/api/v1/users/{qualified_wallet.member.id}/bank_accounts",
            headers=api_helpers.json_headers(qualified_wallet.member),
        )
        assert res.status_code == 200
        assert zd_task.call_count == 0
        assert qualified_wallet.member.member_profile.stripe_account_id is None
