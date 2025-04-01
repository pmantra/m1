import datetime
import uuid

import factory
import factory.fuzzy

from direct_payment.billing import models


class BillFactory(factory.Factory):
    class Meta:
        model = models.Bill

    uuid = factory.Faker("uuid4")
    amount = factory.Faker("random_int", min=1)
    last_calculated_fee = 0
    label = factory.Faker("word")
    payor_type = models.PayorType.MEMBER
    payor_id = factory.Faker("random_int", min=1)
    procedure_id = factory.Faker("random_int", min=1)
    cost_breakdown_id = factory.Faker("random_int", min=1)
    payment_method = models.PaymentMethod.PAYMENT_GATEWAY
    payment_method_label = None
    payment_method_id = None
    payment_method_type = None
    status = models.BillStatus.NEW
    error_type = None
    reimbursement_request_created_at = None
    # default fields
    created_at = datetime.datetime.now()
    modified_at = datetime.datetime.now()
    # state tracking
    processing_at = None
    paid_at = None
    refunded_at = None
    failed_at = None
    cancelled_at = None
    processing_scheduled_at_or_after = created_at + datetime.timedelta(days=7)
    is_ephemeral = False


class BillProcessingRecordFactory(factory.Factory):
    class Meta:
        model = models.BillProcessingRecord

    bill_id = factory.Faker("random_int", min=1)
    # non-specified fields: processing_record_type
    body = {}
    bill_status = models.BillStatus.PROCESSING.value
    transaction_id = uuid.uuid4()
    # default fields
    created_at = datetime.datetime.now()
