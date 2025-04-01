import os
from unittest.mock import patch

import pytest

from common.payments_gateway import (
    Customer,
    PaymentsGatewayClient,
    PaymentsGatewayException,
)
from wallet.models.constants import BillingConsentAction
from wallet.pytests.factories import (
    ReimbursementWalletBillingConsentFactory,
    ReimbursementWalletFactory,
)
from wallet.services.payments import (
    assign_payments_customer_id_to_org,
    assign_payments_customer_id_to_wallet,
    get_direct_payments_billing_consent,
    save_employer_direct_billing_account,
    set_direct_payments_billing_consent,
)


@pytest.fixture
def mock_billing_url_env_var():
    with patch.dict(
        os.environ,
        {"BILLING_URL": "http://payments-server-service.dps.svc.cluster.local/"},
    ), patch(
        "wallet.services.payments.INTERNAL_TRUST_PAYMENT_GATEWAY_URL",
        "http://payments-server-service.dps.svc.cluster.local/",
    ):
        yield


def test_assign_payments_customer_id_to_wallet(qualified_alegeus_wallet_hra):
    with patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user"
    ) as member_id_search_mock, patch(
        "common.payments_gateway.PaymentsGatewayClient.create_customer"
    ) as mock_create_customer:
        member_id_search_mock.return_value = None
        mock_create_customer.return_value = Customer.create_from_dict(
            {
                "customer_id": "00112233-4455-6677-8899-aabbccddeeff",
                "customer_setup_status": "succeeded",
                "payment_method_types": ["card"],
            }
        )

        assign_payments_customer_id_to_wallet(qualified_alegeus_wallet_hra)

    assert (
        qualified_alegeus_wallet_hra.payments_customer_id
        == "00112233-4455-6677-8899-aabbccddeeff"
    )


def test_assign_payments_customer_id_to_wallet_exception(qualified_alegeus_wallet_hra):
    qualified_alegeus_wallet_hra.payments_customer_id = (
        "00112233-4455-6677-8899-aabbccddeeff"
    )

    with pytest.raises(ValueError):
        assign_payments_customer_id_to_wallet(qualified_alegeus_wallet_hra)


def test_assign_payments_customer_id_to_org(
    db, wallet_org_settings, mock_billing_url_env_var
):
    with patch("common.payments_gateway.get_client") as mock_get_client, patch(
        "common.payments_gateway.PaymentsGatewayClient.create_customer"
    ) as mock_create_customer:
        mock_get_client.return_value = PaymentsGatewayClient(
            base_url=os.environ["BILLING_URL"]
        )
        mock_create_customer.return_value = Customer.create_from_dict(
            {
                "customer_id": "00112233-4455-6677-8899-aabbccddeeff",
                "customer_setup_status": "succeeded",
                "payment_method_types": ["us_bank_account"],
            }
        )

        assign_payments_customer_id_to_org(wallet_org_settings)
    actual_args = mock_get_client.call_args_list[0].args[0]
    expected_args = "http://payments-server-service.dps.svc.cluster.local/"
    assert mock_get_client.call_count == 1
    assert (
        wallet_org_settings.payments_customer_id
        == "00112233-4455-6677-8899-aabbccddeeff"
    )
    assert expected_args == actual_args


def test_assign_payments_customer_id_to_org__exception(wallet_org_settings):
    wallet_org_settings.payments_customer_id = "00112233-4455-6677-8899-aabbccddeeff"

    with pytest.raises(ValueError):
        assign_payments_customer_id_to_org(wallet_org_settings)


def test_save_employer_direct_billing_account__success(
    wallet_org_settings, mock_billing_url_env_var
):
    with patch("common.payments_gateway.get_client") as mock_get_client, patch(
        "common.payments_gateway.PaymentsGatewayClient.create_customer"
    ) as mock_create_customer, patch(
        "common.payments_gateway.PaymentsGatewayClient.add_bank_account"
    ) as mock_add_bank_account, patch(
        "wallet.services.payments.emit_audit_log_update"
    ) as mock_emit_log:
        mock_get_client.return_value = PaymentsGatewayClient(
            base_url=os.environ["BILLING_URL"]
        )
        mock_create_customer.return_value = Customer.create_from_dict(
            {
                "customer_id": "00112233-4455-6677-8899-aabbccddeeff",
                "customer_setup_status": "succeeded",
                "payment_method_types": ["us_bank_account"],
            }
        )
        mock_emit_log.return_value = None
        save_employer_direct_billing_account(
            wallet_org_settings,
            account_type="checking",
            account_holder_type="company",
            account_number="123456789",
            routing_number="987654321",
        )
        mock_emit_log.assert_called_once()
        actual_args = mock_get_client.call_args_list[0].args[0]
        expected_args = "http://payments-server-service.dps.svc.cluster.local/"
        assert mock_get_client.call_count == 2
        assert mock_create_customer.call_count == 1
        assert mock_add_bank_account.call_count == 1
        assert (
            wallet_org_settings.payments_customer_id
            == "00112233-4455-6677-8899-aabbccddeeff"
        )
        assert actual_args == expected_args


def test_save_employer_direct_billing_account__existing_customer_success(
    wallet_org_settings, mock_billing_url_env_var
):
    wallet_org_settings.payments_customer_id = "00112233-4455-6677-8899-aabbccddeeff"

    with patch("common.payments_gateway.get_client") as mock_get_client, patch(
        "common.payments_gateway.PaymentsGatewayClient.create_customer"
    ) as mock_create_customer, patch(
        "common.payments_gateway.PaymentsGatewayClient.add_bank_account"
    ) as mock_add_bank_account, patch(
        "wallet.services.payments.emit_audit_log_update"
    ) as mock_emit_log:
        mock_get_client.return_value = PaymentsGatewayClient(
            base_url=os.environ["BILLING_URL"]
        )
        mock_emit_log.return_value = None
        save_employer_direct_billing_account(
            wallet_org_settings,
            account_type="checking",
            account_holder_type="company",
            account_number="123456789",
            routing_number="987654321",
        )
        expected_args = "http://payments-server-service.dps.svc.cluster.local/"
        actual_args = mock_get_client.call_args_list[0].args[0]
        mock_emit_log.assert_called_once()
        assert mock_get_client.call_count == 1
        assert mock_create_customer.call_count == 0
        assert mock_add_bank_account.call_count == 1
        assert expected_args == actual_args


def test_save_employer_direct_billing_account__customer_failure(
    wallet_org_settings, mock_billing_url_env_var
):
    with patch("common.payments_gateway.get_client") as mock_get_client, patch(
        "common.payments_gateway.PaymentsGatewayClient.create_customer"
    ) as mock_create_customer, patch(
        "common.payments_gateway.PaymentsGatewayClient.add_bank_account"
    ) as mock_add_bank_account:
        mock_get_client.return_value = PaymentsGatewayClient(
            base_url=os.environ["BILLING_URL"]
        )
        mock_create_customer.side_effect = PaymentsGatewayException("Mock Error", 500)
        with pytest.raises(RuntimeError):
            save_employer_direct_billing_account(
                wallet_org_settings,
                account_type="checking",
                account_holder_type="company",
                account_number="123456789",
                routing_number="987654321",
            )
        expected_args = "http://payments-server-service.dps.svc.cluster.local/"
        actual_args = mock_get_client.call_args_list[0].args[0]
        assert mock_get_client.call_count == 1
        assert mock_create_customer.call_count == 1
        assert mock_add_bank_account.call_count == 0
        assert expected_args == actual_args


def test_save_employer_direct_billing_account__account_failure(
    wallet_org_settings, mock_billing_url_env_var
):
    with patch("common.payments_gateway.get_client") as mock_get_client, patch(
        "common.payments_gateway.PaymentsGatewayClient.create_customer"
    ) as mock_create_customer, patch(
        "common.payments_gateway.PaymentsGatewayClient.add_bank_account"
    ) as mock_add_bank_account:
        mock_get_client.return_value = PaymentsGatewayClient(
            base_url=os.environ["BILLING_URL"]
        )
        mock_create_customer.return_value = Customer.create_from_dict(
            {
                "customer_id": "00112233-4455-6677-8899-aabbccddeeff",
                "customer_setup_status": "succeeded",
                "payment_method_types": ["us_bank_account"],
            }
        )
        mock_add_bank_account.side_effect = PaymentsGatewayException("Mock Error", 500)

        with pytest.raises(RuntimeError):
            save_employer_direct_billing_account(
                wallet_org_settings,
                account_type="checking",
                account_holder_type="company",
                account_number="123456789",
                routing_number="987654321",
            )
        expected_args = "http://payments-server-service.dps.svc.cluster.local/"
        actual_args = mock_get_client.call_args_list[0].args[0]
        assert mock_get_client.call_count == 2
        assert mock_create_customer.call_count == 1
        assert mock_add_bank_account.call_count == 1
        assert expected_args == actual_args


def test_get_direct_payments_billing_consent__none(qualified_alegeus_wallet_hra):
    result = get_direct_payments_billing_consent(qualified_alegeus_wallet_hra)
    assert result is False


def test_get_direct_payments_billing_consent__other(qualified_alegeus_wallet_hra):
    wallet = ReimbursementWalletFactory()
    ReimbursementWalletBillingConsentFactory(
        reimbursement_wallet=wallet,
        acting_user_id=qualified_alegeus_wallet_hra.employee_member.id,
        action=BillingConsentAction.CONSENT,
    )
    result = get_direct_payments_billing_consent(qualified_alegeus_wallet_hra)
    assert result is False


def test_get_direct_payments_billing_consent__consented(
    qualified_alegeus_wallet_hra, enterprise_user
):
    ReimbursementWalletBillingConsentFactory(
        reimbursement_wallet=qualified_alegeus_wallet_hra,
        acting_user_id=enterprise_user.id,
        action=BillingConsentAction.CONSENT,
    )
    result = get_direct_payments_billing_consent(qualified_alegeus_wallet_hra)
    assert result is True


def test_get_direct_payments_billing_consent__revoked(
    qualified_alegeus_wallet_hra, enterprise_user
):
    ReimbursementWalletBillingConsentFactory(
        reimbursement_wallet=qualified_alegeus_wallet_hra,
        acting_user_id=enterprise_user.id,
        action=BillingConsentAction.CONSENT,
    )
    ReimbursementWalletBillingConsentFactory(
        reimbursement_wallet=qualified_alegeus_wallet_hra,
        acting_user_id=enterprise_user.id,
        action=BillingConsentAction.REVOKE,
    )
    result = get_direct_payments_billing_consent(qualified_alegeus_wallet_hra)
    assert result is False


def test_get_direct_payments_billing_consent__outdated(
    qualified_alegeus_wallet_hra, enterprise_user
):
    ReimbursementWalletBillingConsentFactory(
        reimbursement_wallet=qualified_alegeus_wallet_hra,
        acting_user_id=enterprise_user.id,
        action=BillingConsentAction.CONSENT,
        version=0,
    )
    result = get_direct_payments_billing_consent(qualified_alegeus_wallet_hra)
    assert result is False


def test_set_direct_payments_billing_consent__consented(
    qualified_alegeus_wallet_hra, enterprise_user
):
    result = set_direct_payments_billing_consent(
        wallet=qualified_alegeus_wallet_hra,
        actor=enterprise_user,
        consent_granted=True,
        ip_address="127.0.0.1",
    )
    assert result is True


def test_set_direct_payments_billing_consent__revoked(
    qualified_alegeus_wallet_hra, enterprise_user
):
    result1 = set_direct_payments_billing_consent(
        wallet=qualified_alegeus_wallet_hra,
        actor=enterprise_user,
        consent_granted=True,
        ip_address="127.0.0.1",
    )
    result2 = set_direct_payments_billing_consent(
        wallet=qualified_alegeus_wallet_hra,
        actor=enterprise_user,
        consent_granted=False,
        ip_address="127.0.0.1",
    )
    result3 = get_direct_payments_billing_consent(qualified_alegeus_wallet_hra)

    assert result1 is True
    assert result2 is False
    assert result3 is False
