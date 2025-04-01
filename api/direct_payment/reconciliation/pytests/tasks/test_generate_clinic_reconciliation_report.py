from unittest.mock import Mock, patch

from direct_payment.clinic.models.clinic import FertilityClinicLocation
from direct_payment.reconciliation.tasks.libs.generate_clinic_reconciliation_report import (
    ClinicReconciliationReportGenerator,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from utils.random_string import generate_random_string


def test_empty_bills():
    with patch(
        "common.payments_gateway.client.PaymentsGatewayClient.get_reconciliation_by_recipient",
        return_value=[],
    ):
        report_generator = ClinicReconciliationReportGenerator(
            dry_run=True,
            clinic_group_name=generate_random_string(10),
            clinic_names=[generate_random_string(10), generate_random_string(10)],
            start_time=3,
            end_time=10,
        )

        rows, success = report_generator.generate_clinic_reconciliation_report()

        assert len(rows) == 0
        assert success is True


@patch(
    "common.payments_gateway.client.PaymentsGatewayClient.get_reconciliation_by_recipient"
)
@patch(
    "direct_payment.reconciliation.tasks.libs.generate_clinic_reconciliation_report.ClinicReconciliationReportGenerator._get_clinic_to_recipient_id_map"
)
@patch(
    "direct_payment.reconciliation.tasks.libs.generate_clinic_reconciliation_report.TreatmentProcedureRepository.read"
)
@patch(
    "direct_payment.reconciliation.tasks.libs.generate_clinic_reconciliation_report.User.query"
)
def test_generate_report(
    mock_user_query,
    mock_treatment_procedure_repo_read,
    mock_get_clinic_to_recipient_id_map,
    mock_get_bills,
    enterprise_user,
):
    recipient_id = generate_random_string(10)
    clinic_name = generate_random_string(15)
    payout_id = generate_random_string(10)
    procedure_name = generate_random_string(10)
    clinic_location_name = generate_random_string(10)
    stripe_transfer_id = generate_random_string(10)
    source_id = "123456"
    start_time = 3
    end_time = 10

    mock_get_clinic_to_recipient_id_map.return_value = {clinic_name: recipient_id}
    mock_user_query.get.return_value = enterprise_user

    mock_treatment_procedure_repo_read.return_value = TreatmentProcedure(
        member_id=123,
        cost=10000,
        procedure_name=procedure_name,
        start_date="2023-08-26",
        end_date="2023-08-27",
        fertility_clinic_location=FertilityClinicLocation(name=clinic_location_name),
    )

    bill = {
        "source_id": source_id,
        "amount": 100,
        "stripe_transfer_id": stripe_transfer_id,
        "source_type": "TreatmentProcedure",
        "stripe_payout_id": payout_id,
    }
    mock_response = Mock()
    mock_response.json.return_value = [bill]
    mock_get_bills.return_value = mock_response

    report_generator = ClinicReconciliationReportGenerator(
        dry_run=True,
        clinic_group_name=generate_random_string(10),
        clinic_names=[clinic_name],
        start_time=start_time,
        end_time=end_time,
    )

    rows, success = report_generator.generate_clinic_reconciliation_report()

    mock_get_clinic_to_recipient_id_map.assert_called_once()
    mock_treatment_procedure_repo_read.assert_called_once_with(
        treatment_procedure_id=int(source_id)
    )
    mock_get_bills.assert_called_once_with(
        recipient_id=recipient_id, start_time=start_time, end_time=end_time
    )

    assert len(rows) == 1

    assert enterprise_user.first_name == rows[0][0]
    assert enterprise_user.last_name == rows[0][1]
    assert "" == rows[0][2]  # dob
    assert procedure_name == rows[0][3]
    assert clinic_name == rows[0][4]
    assert clinic_location_name == rows[0][5]
    assert stripe_transfer_id == rows[0][6]
    assert payout_id == rows[0][7]
    assert "2023-08-26" == rows[0][8]  # start_time
    assert "2023-08-27" == rows[0][9]  # end_time
    assert "100.00" == rows[0][10]  # bill amount
    assert "1.00" == rows[0][11]  # paid amount

    assert success is True
