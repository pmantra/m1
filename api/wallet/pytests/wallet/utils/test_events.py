from unittest.mock import patch

import pytest

from authn.models.user import User
from wallet.models.constants import (
    AllowedMembers,
    ReimbursementRequestExpenseTypes,
    ReimbursementRequestState,
)
from wallet.utils.events import (
    send_reimbursement_request_state_event,
    send_wallet_qualification_event,
)


@pytest.mark.parametrize(
    argnames="state,erisa_workflow,appeal_of_fixture,expected_event_name",
    argvalues=[
        (ReimbursementRequestState.NEW, False, None, None),
        (ReimbursementRequestState.NEW, True, None, None),
        (ReimbursementRequestState.NEW, False, "denied_reimbursement_request", None),
        (ReimbursementRequestState.NEW, True, "denied_reimbursement_request", None),
        (ReimbursementRequestState.PENDING, False, None, None),
        (ReimbursementRequestState.PENDING, True, None, None),
        (
            ReimbursementRequestState.PENDING,
            False,
            "denied_reimbursement_request",
            None,
        ),
        (ReimbursementRequestState.PENDING, True, "denied_reimbursement_request", None),
        (
            ReimbursementRequestState.APPROVED,
            False,
            None,
            "wallet_reimbursement_state_approved",
        ),
        (
            ReimbursementRequestState.APPROVED,
            False,
            "denied_reimbursement_request",
            "wallet_reimbursement_state_approved",
        ),
        (
            ReimbursementRequestState.APPROVED,
            True,
            None,
            "wallet_reimbursement_state_approved",
        ),
        (
            ReimbursementRequestState.APPROVED,
            True,
            "denied_reimbursement_request",
            "wallet_reimbursement_state_appeal_approved_erisa",
        ),
        (
            ReimbursementRequestState.DENIED,
            False,
            None,
            "wallet_reimbursement_state_declined",
        ),
        (
            ReimbursementRequestState.DENIED,
            False,
            "denied_reimbursement_request",
            "wallet_reimbursement_state_declined",
        ),
        (
            ReimbursementRequestState.DENIED,
            True,
            None,
            "wallet_reimbursement_state_declined_erisa",
        ),
        (
            ReimbursementRequestState.DENIED,
            True,
            "denied_reimbursement_request",
            "wallet_reimbursement_state_appeal_declined_erisa",
        ),
        (
            ReimbursementRequestState.REIMBURSED,
            False,
            None,
            "wallet_reimbursement_state_reimbursed",
        ),
        (
            ReimbursementRequestState.REIMBURSED,
            True,
            None,
            "wallet_reimbursement_state_reimbursed",
        ),
        (
            ReimbursementRequestState.REIMBURSED,
            False,
            "denied_reimbursement_request",
            "wallet_reimbursement_state_reimbursed",
        ),
        (
            ReimbursementRequestState.REIMBURSED,
            True,
            "denied_reimbursement_request",
            "wallet_reimbursement_state_reimbursed",
        ),
    ],
)
def test_send_reimbursement_request_state_event(
    valid_reimbursement_request,
    state,
    erisa_workflow,
    appeal_of_fixture,
    expected_event_name,
    request,
):
    # workaround to avoid needing a plug-in to pass fixtures in parametrize (https://github.com/pytest-dev/pytest/issues/349)
    appeal_of = (
        request.getfixturevalue(appeal_of_fixture) if appeal_of_fixture else None
    )

    valid_reimbursement_request.state = state
    valid_reimbursement_request.erisa_workflow = erisa_workflow
    valid_reimbursement_request.appeal_of = appeal_of.id if appeal_of else None

    with patch("utils.braze_events.braze.send_event") as mock_send_event:
        send_reimbursement_request_state_event(valid_reimbursement_request)

        if expected_event_name:
            assert mock_send_event.call_count == 1
            assert mock_send_event.call_args.kwargs["event_name"] == expected_event_name
        else:
            assert mock_send_event.call_count == 0


@pytest.mark.parametrize(
    argnames="categories, is_direct_payment_eligible, primary_expense_type, allowed_members, expected_event_name, "
    "exp_event_data",
    argvalues=[
        (
            ("other", 3000, None),
            False,
            ReimbursementRequestExpenseTypes.FERTILITY,
            AllowedMembers.SINGLE_ANY_USER,
            "wallet_state_qualified",
            False,
        ),
        (
            ("other", 3000, None),
            False,
            ReimbursementRequestExpenseTypes.CHILDCARE,
            AllowedMembers.SINGLE_ANY_USER,
            "wallet_state_qualified",
            False,
        ),
        (
            ("fertility", 5000, None),
            True,
            ReimbursementRequestExpenseTypes.FERTILITY,
            AllowedMembers.SHAREABLE,
            "mmb_wallet_qualified_and_shareable",
            True,
        ),
        (
            ("fertility", 5000, None),
            True,
            ReimbursementRequestExpenseTypes.CHILDCARE,
            AllowedMembers.SINGLE_EMPLOYEE_ONLY,
            "mmb_wallet_qualified_not_shareable",
            True,
        ),
    ],
    ids=[
        "Classic Wallet fertility primary expense type",
        "Classic Wallet childcare primary expense type",
        "DP wallet shareable wallet",
        "DP wallet non-shareable wallet",
    ],
)
def test_send_wallet_qualification_event(
    enterprise_user,
    wallet_for_events,
    ff_test_data,
    categories,
    is_direct_payment_eligible,
    primary_expense_type,
    allowed_members,
    expected_event_name,
    exp_event_data,
):
    wallet = wallet_for_events(categories, is_direct_payment_eligible, allowed_members)
    wallet.primary_expense_type = primary_expense_type

    with patch("utils.braze_events.braze.send_event") as mock_send_event, patch(
        "braze.client.BrazeClient.track_users"
    ) as mock_track_users:
        send_wallet_qualification_event(wallet)
    kwargs = mock_send_event.call_args.kwargs
    assert kwargs["event_name"] == expected_event_name
    assert kwargs["user"] == enterprise_user
    if exp_event_data:
        assert kwargs["event_data"] == {
            "program_overview_link": wallet.reimbursement_organization_settings.benefit_overview_resource.custom_url,
            "benefit_id": enterprise_user.member_benefit.benefit_id,
        }
    else:
        assert "event_data" not in kwargs
    # test for user tracking
    assert mock_track_users.called
    res_user_att = mock_track_users.call_args.kwargs["user_attributes"][0]
    exp_user = User.query.get(wallet.reimbursement_wallet_users[0].user_id)
    assert res_user_att.external_id == exp_user.esp_id
    assert len(res_user_att.attributes) == 1
    assert res_user_att.attributes["wallet_qualification_datetime"] is not None
