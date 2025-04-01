import datetime

import pytest

from wallet.models.constants import ReimbursementRequestState, WalletState
from wallet.models.reimbursement import ReimbursementRequest
from wallet.pytests.factories import (
    ReimbursementRequestFactory,
    ReimbursementWalletFactory,
)

headers = {"STRIPE_SIGNATURE": "pk_test_fake_key"}


@pytest.fixture()
def reimbursement_wallet(enterprise_user):
    return ReimbursementWalletFactory.create(
        member=enterprise_user, state=WalletState.QUALIFIED
    )


@pytest.fixture()
def reimbursement_request(reimbursement_wallet):
    category = reimbursement_wallet.reimbursement_organization_settings.allowed_reimbursement_categories[
        0
    ].reimbursement_request_category
    reimbursement_request = ReimbursementRequestFactory.create(
        amount=50,
        reimbursement_wallet_id=reimbursement_wallet.id,
        category=category,
        state=ReimbursementRequestState.APPROVED,
        reimbursement_payout_date=datetime.date.today(),
    )
    return reimbursement_request


def test_stripe_reimbursement_hook_payout_paid(
    client, db, stripe_event, reimbursement_request, sync_queue
):
    success_event = stripe_event(
        reimbursement_request.id, "payout.paid", reimbursement_request.amount
    )
    response = client.post(
        "/api/v1/vendor/stripe/reimbursements-webhook",
        json=success_event,
        headers=headers,
    )
    assert response.status == "200 OK"

    reimbursement_request = (
        db.session.query(ReimbursementRequest)
        .filter(ReimbursementRequest.id == reimbursement_request.id)
        .first()
    )

    assert reimbursement_request.state == ReimbursementRequestState.REIMBURSED


def test_stripe_reimbursement_hook_payout_failed(
    client, db, stripe_event, reimbursement_request, sync_queue
):
    failed_event = stripe_event(
        reimbursement_request.id, "payout.failed", reimbursement_request.amount
    )

    response = client.post(
        "/api/v1/vendor/stripe/reimbursements-webhook",
        json=failed_event,
        headers=headers,
    )

    # we send 200 response to stripe to acknowledge we successfully processed the failed event
    assert response.status == "200 OK"

    reimbursement_request = db.session.query(ReimbursementRequest).filter(
        ReimbursementRequest.id == reimbursement_request.id
    )

    assert reimbursement_request.first().state == ReimbursementRequestState.FAILED
