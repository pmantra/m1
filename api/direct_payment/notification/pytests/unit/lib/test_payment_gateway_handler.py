import datetime
import uuid
from unittest import mock

import pytest

from authn.models.user import User
from direct_payment.notification.errors import PaymentGatewayMessageProcessingError
from direct_payment.notification.lib.payment_gateway_handler import (
    process_payment_gateway_message,
)
from pytests.factories import ResourceFactory
from wallet.pytests.factories import (
    ReimbursementOrganizationSettingsFactory,
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementWalletBenefitFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)

REUSABLE_UUID = uuid.uuid4()


@pytest.fixture(scope="function")
def reimbursement_wallet_benefit():
    return ReimbursementWalletBenefitFactory.create()


@pytest.fixture(scope="function")
def reimbursement_wallet(enterprise_user, reimbursement_wallet_benefit):
    ben_resource = ResourceFactory.create()
    org_settings = ReimbursementOrganizationSettingsFactory(
        organization_id=enterprise_user.organization.id,
        allowed_reimbursement_categories__cycle_based=True,
        direct_payment_enabled=True,
        benefit_overview_resource_id=ben_resource.id,
    )
    wallet = ReimbursementWalletFactory.create(
        payments_customer_id=str(uuid.uuid4()),
    )
    wallet.reimbursement_organization_settings = org_settings
    wallet.user_id = enterprise_user.id

    wallet.reimbursement_wallet_benefit = reimbursement_wallet_benefit
    ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )
    return wallet


@pytest.fixture(scope="function")
def reimbursement_plan(reimbursement_wallet):
    today = datetime.date.today()

    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    plan = ReimbursementPlanFactory.create(
        category=new_category,
        start_date=today - datetime.timedelta(days=4),
        end_date=today - datetime.timedelta(days=2),
    )

    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category=new_category,
        reimbursement_organization_settings=reimbursement_wallet.reimbursement_organization_settings,
        reimbursement_request_category_maximum=0,
    )

    return plan


@pytest.mark.parametrize(
    argnames="message, expected_msg",
    argvalues=[
        (
            {},
            {
                "The event_type key is missing from the message. The message_payload key is missing from the message.",
            },
        ),
        (
            {"unknown_key": None},
            {
                "The event_type key is missing from the message. The message_payload key is missing from the message.",
            },
        ),
        (
            {"event_type": "payment_method_attach_event"},
            {
                "The message_payload key is missing from the message.",
            },
        ),
        (
            {"message_payload": {"key": "value"}},
            {
                "The event_type key is missing from the message.",
            },
        ),
        (
            {"event_type": None},
            {
                "Received unsupported event_type None from payment gateway. The message_payload key is missing from the "
                "message.",
            },
        ),
        (
            {"event_type": "unknown_event_type"},
            {
                "Received unsupported event_type unknown_event_type from payment gateway. The message_payload key is "
                "missing from the message.",
            },
        ),
        (
            {
                "event_type": "payment_method_attach_event",
                "message_payload": None,
                "error_payload": None,
            },
            {
                "The message_payload is None. The error_payload is None.",
            },
        ),
        (
            {
                "event_type": "payment_method_detach_event",
                "message_payload": {},
                "error_payload": {},
            },
            {
                "The message_payload is empty.",
            },
        ),
        (
            {
                "event_type": "payment_method_attach_event",
                "message_payload": ["clearly_wrong"],
                "error_payload": ["also_wrong"],
            },
            {
                "The message_payload does not implement Mapping. The error_payload does not implement Mapping.",
            },
        ),
        (
            {
                "event_type": "payment_method_attach_event",
                "message_payload": {
                    "customer_id": "clearly_wrong",
                    "payment_method": {},
                },
            },
            {
                "customer_id='clearly_wrong' is badly formed hexadecimal UUID string. payment_method is missing key: "
                "payment_method_type. payment_method is missing key: last4.",
            },
        ),
        (
            {
                "event_type": "payment_method_detach_event",
                "message_payload": {
                    "customer_id": str(REUSABLE_UUID),
                    "payment_method": None,
                },
            },
            {
                "payment_method was None in the message_payload.",
            },
        ),
        (
            {
                "event_type": "payment_method_attach_event",
                "message_payload": {
                    "customer_id": "    ",
                    "payment_method": ["clearly wrong"],
                },
            },
            {
                "customer_id is blank or missing in message_payload. payment_method does not implement Mapping.",
            },
        ),
        (
            {
                "event_type": "payment_method_attach_event",
                "message_payload": {
                    "customer_id": str(REUSABLE_UUID),
                    "payment_method": {
                        "payment_method_type": "",
                        "last4": "clearly_wrong_000",
                        "brand": "visa",
                        "payment_method_id": "something_made_up",
                    },
                },
            },
            {
                "value mapped to : payment_method_type in payment_method is blank or None. payment_method has "
                "last_4='clearly_wrong_000' which is not exactly 4 characters long.",
            },
        ),
    ],
)
def test_process_payment_gateway_event_message_errors(message, expected_msg):
    with pytest.raises(PaymentGatewayMessageProcessingError) as ex_info, mock.patch(
        "braze.client.BrazeClient.track_users"
    ) as mock_track_users:
        process_payment_gateway_message(message)
    assert set(ex_info.value.args[0]) == expected_msg
    assert mock_track_users.called is False


def test_process_payment_gateway_message_detached(
    reimbursement_wallet,
    reimbursement_wallet_benefit,
):
    message = {
        "event_type": "payment_method_detach_event",
        "message_payload": {
            "customer_id": str(reimbursement_wallet.payments_customer_id),
            "payment_method": {
                "payment_method_type": "card",
                "last4": "3223",
                "brand": "does_not_matter",
                "payment_method_id": "123456",
            },
        },
    }

    with mock.patch("utils.braze.send_event_by_ids") as mock_send_event_by_ids:
        assert process_payment_gateway_message(message)
    assert mock_send_event_by_ids.called
    kwargs = mock_send_event_by_ids.call_args.kwargs
    assert kwargs["event_name"] == "mmb_payment_method_removed"
    assert kwargs["event_data"] == {
        "payment_method_type": "card",
        "payment_method_last4": "3223",
        "benefit_id": reimbursement_wallet_benefit.maven_benefit_id,
    }
    assert kwargs["user_id"] == reimbursement_wallet.user_id


@pytest.mark.parametrize(
    argnames="updated_fee_calculation_feature_flag, card_funding",
    argvalues=[(True, "CREDIT"), (True, ""), (False, "")],
    ids=[
        "card funding attribute should be present if new fee calculation feature is on",
        "card funding attribute should be empty if new fee calculation feature is on and card funding is missing",
        "card funding attribute should be empty if new fee calculation feature is off",
    ],
)
def test_process_payment_gateway_message_attached(
    reimbursement_wallet,
    updated_fee_calculation_feature_flag,
    card_funding,
):
    message = {
        "event_type": "payment_method_attach_event",
        "message_payload": {
            "customer_id": str(reimbursement_wallet.payments_customer_id),
            "payment_method": {
                "payment_method_type": "card",
                "last4": "3223",
                "brand": "does_not_matter",
                "payment_method_id": "123456",
            },
        },
    }

    if card_funding:
        message["message_payload"]["payment_method"]["card_funding"] = card_funding

    with mock.patch(
        "utils.braze.send_event_by_ids"
    ) as mock_send_event_by_ids, mock.patch(
        "braze.client.BrazeClient.track_users"
    ) as mock_track_users:
        assert process_payment_gateway_message(message)
    assert mock_send_event_by_ids.called
    kwargs = mock_send_event_by_ids.call_args.kwargs

    assert kwargs["event_name"] == "mmb_payment_method_added"
    url_ = (
        reimbursement_wallet.reimbursement_organization_settings.benefit_overview_resource.custom_url
    )
    expected_event_data = {
        "payment_method_type": "card",
        "payment_method_last4": "3223",
        "program_overview_link": url_,
        "card_funding": card_funding,
    }

    if updated_fee_calculation_feature_flag:
        expected_event_data["card_funding"] = card_funding

    assert kwargs["event_data"] == expected_event_data
    assert kwargs["user_id"] == reimbursement_wallet.user_id

    # test for user tracking
    assert mock_track_users.called
    res_user_att = mock_track_users.call_args.kwargs["user_attributes"][0]
    exp_user = User.query.get(
        reimbursement_wallet.reimbursement_wallet_users[0].user_id
    )
    assert res_user_att.external_id == exp_user.esp_id
    assert len(res_user_att.attributes) == 1
    assert res_user_att.attributes["wallet_added_payment_method_datetime"] is not None
