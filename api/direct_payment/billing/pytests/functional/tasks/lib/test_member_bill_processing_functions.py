from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from common.payments_gateway import PaymentsGatewayException
from direct_payment.billing import models
from direct_payment.billing.models import BillStatus
from direct_payment.billing.pytests import factories
from direct_payment.billing.tasks.lib.member_bill_processing_functions import (
    ProcessingStatus,
    process_member_bills_driver,
)


class TestBillProcessingFunctions:
    def test_process_member_bills_driver(
        self,
        bill_repository,
        multiple_pre_created_bills,
    ):
        expected_results_dict = {
            1: ProcessingStatus(True, BillStatus.PROCESSING.value),
            4: ProcessingStatus(True, BillStatus.PROCESSING.value),
        }

        expected_dict = {}
        mock_return_values = []
        for expected_bill_index, expected_result in expected_results_dict.items():
            input_bill = multiple_pre_created_bills[expected_bill_index]
            expected_dict[input_bill.uuid] = expected_result
            side_effect = MagicMock(
                uuid=input_bill.uuid,
                status=BillStatus(expected_result.status_message),
            )
            mock_return_values.append(side_effect)
        [
            bill_repository.create(instance=bill)
            # ignored paid refund
            for bill in [
                factories.BillFactory.build(
                    payor_id=1,
                    amount=-20,
                    payor_type=models.PayorType.MEMBER,
                    status=models.BillStatus.PAID,
                ),
                # ignored NEW bill (processing date in future)
                factories.BillFactory.build(
                    payor_id=1,
                    amount=200,
                    payor_type=models.PayorType.MEMBER,
                    status=models.BillStatus.NEW,
                    processing_scheduled_at_or_after=datetime.now(timezone.utc)
                    + timedelta(days=+60),
                ),
            ]
        ]
        with patch(
            "direct_payment.billing.billing_service.BillingService.set_new_bill_to_processing",
            side_effect=mock_return_values,
        ) as processing_mock:
            results = process_member_bills_driver(dry_run=False)
            assert results == expected_dict
            assert processing_mock.call_count == 2

    # TODO: @Rajneesh parametrize this
    def test_process_member_bills_driver_with_good_exception(
        self, multiple_pre_created_bills
    ):
        expected_dict = {
            multiple_pre_created_bills[1].uuid: ProcessingStatus(
                True, "message: A test error, code: 101"
            ),
            multiple_pre_created_bills[4].uuid: ProcessingStatus(
                True, "message: A test error, code: 101"
            ),
        }

        with patch(
            "direct_payment.billing.billing_service.BillingService.set_new_bill_to_processing",
            side_effect=PaymentsGatewayException(message="A test error", code=101),
        ):
            results = process_member_bills_driver(False)
            assert results == expected_dict

    # TODO: @Rajneesh parametrize this
    def test_process_member_bills_driver_with_bad_exception(
        self, multiple_pre_created_bills
    ):
        expected_dict = {
            multiple_pre_created_bills[1].uuid: ProcessingStatus(
                False, "MissingPaymentGatewayInformation"
            ),
            multiple_pre_created_bills[4].uuid: ProcessingStatus(
                False, "MissingPaymentGatewayInformation"
            ),
        }
        results = process_member_bills_driver(False)
        assert results == expected_dict

    def test_process_member_bills_driver_with_dryrun(self, multiple_pre_created_bills):
        inp_bill_1 = multiple_pre_created_bills[1]
        inp_bill_4 = multiple_pre_created_bills[4]
        expected_dict = {
            inp_bill_1.uuid: ProcessingStatus(True, "Dry Run"),
            inp_bill_4.uuid: ProcessingStatus(True, "Dry Run"),
        }
        with patch(
            "direct_payment.billing.billing_service.BillingService.set_new_bill_to_processing"
        ) as processing_mock:
            results = process_member_bills_driver(True)
            assert results == expected_dict
            assert not processing_mock.called
