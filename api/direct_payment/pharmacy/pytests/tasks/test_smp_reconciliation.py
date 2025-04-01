import datetime
from unittest.mock import Mock, patch

from direct_payment.pharmacy.tasks.libs.smp_reconciliation_file import (
    generate_reconciliation_report,
    get_results,
)


class TestGenerateReconciliationReport:
    def test_get_results_empty(self):
        mock_response = Mock()
        mock_response.json.return_value = []
        with patch(
            "common.payments_gateway.client.PaymentsGatewayClient.get_reconciliation_by_recipient",
            return_value=mock_response,
        ):
            assert [] == get_results(None, None)

    @patch(
        "common.payments_gateway.client.PaymentsGatewayClient.get_reconciliation_by_recipient"
    )
    @patch(
        "direct_payment.pharmacy.tasks.libs.smp_reconciliation_file.PharmacyPrescriptionService.get_by_procedure_ids",
    )
    @patch("authn.models.user.User.query.get")
    def test_get_results(
        self,
        mock_user_get,
        mock_get_by_procedure_ids,
        mock_get_bills,
        enterprise_user,
        new_prescription,
    ):
        mock_response = Mock()
        given_prescription = new_prescription()
        given_prescription.shipped_json = {"Rx #": "123"}
        given_prescription.actual_shipped_date = datetime.datetime.now(
            datetime.timezone.utc
        )
        bill = {
            "source_id": given_prescription.treatment_procedure_id,
            "amount": 100,
            "stripe_transfer_id": "tr_xxxxx",
        }
        mock_response.json.return_value = [bill]
        mock_get_bills.return_value = mock_response
        mock_get_by_procedure_ids.return_value = [given_prescription]
        mock_user_get.return_value = [enterprise_user]
        ret = get_results(None, None)
        assert len(ret) == 1

    def test_dry_run(self):
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_reconciliation_file.get_results"
        ) as mock_get_results, patch(
            "direct_payment.pharmacy.tasks.libs.smp_reconciliation_file.PharmacyFileHandler"
        ) as mock_handler:
            mock_get_results.return_value = [["test", "data"]]

            result = generate_reconciliation_report(
                dry_run=True, start_time=None, end_time=None
            )

            assert result is True
            mock_handler.assert_not_called()

    def test_gcs_upload_success(self, smp_gcs_ff_enabled):
        smp_gcs_ff_enabled(True)
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_reconciliation_file.get_results"
        ) as mock_get_results, patch(
            "direct_payment.pharmacy.tasks.libs.smp_reconciliation_file.PharmacyFileHandler"
        ) as mock_handler:
            mock_get_results.return_value = [["test", "data"]]
            mock_instance = mock_handler.return_value
            mock_instance.upload_reconciliation_file.return_value = True

            result = generate_reconciliation_report(
                dry_run=False, start_time=None, end_time=None
            )
            assert result is True
            mock_instance.upload_reconciliation_file.assert_called_once()

    def test_gcs_upload_failure(self, smp_gcs_ff_enabled):
        smp_gcs_ff_enabled(True)
        with patch(
            "direct_payment.pharmacy.tasks.libs.smp_reconciliation_file.get_results"
        ) as mock_get_results, patch(
            "direct_payment.pharmacy.tasks.libs.smp_reconciliation_file.PharmacyFileHandler"
        ) as mock_handler:
            mock_get_results.return_value = [["test", "data"]]
            mock_instance = mock_handler.return_value
            mock_instance.upload_reconciliation_file.return_value = False

            result = generate_reconciliation_report(
                dry_run=False, start_time=None, end_time=None
            )
            assert result is False
            mock_instance.upload_reconciliation_file.assert_called_once()
