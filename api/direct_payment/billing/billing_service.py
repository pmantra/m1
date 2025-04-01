from __future__ import annotations

import copy
import dataclasses
import datetime
import uuid
from collections import defaultdict
from traceback import format_exc
from typing import List, Mapping

from sqlalchemy.orm.scoping import scoped_session

from common import stats
from common.payments_gateway import (
    EventTypeT,
    PaymentGatewayEventMessage,
    PaymentsGatewayException,
    Transaction,
    TransactionPayload,
    TransactionStatusT,
    get_client,
)
from cost_breakdown.constants import IS_INTEGRATIONS_K8S_CLUSTER
from direct_payment.billing import errors, models
from direct_payment.billing.constants import (
    DECLINE_CODE_MAPPING,
    DEFAULT_GATEWAY_ERROR_RESPONSE,
    GATEWAY_EXCEPTION_CODE_MAPPING,
    INTERNAL_TRUST_PAYMENT_GATEWAY_URL,
    OTHER_MAVEN,
)
from direct_payment.billing.errors import (
    BillingServicePGMessageProcessingError,
    InvalidBillTreatmentProcedureCancelledError,
    InvalidEphemeralBillOperationError,
    InvalidRefundBillCreationError,
    PaymentsGatewaySetupError,
)
from direct_payment.billing.lib.bill_creation_helpers import (
    calculate_fee,
    compute_processing_scheduled_at_or_after,
)
from direct_payment.billing.lib.legacy_mono import (
    get_benefit_id,
    get_benefit_id_from_wallet_id,
    get_cost_breakdown_as_dict_from_id,
    get_first_and_last_name_from_user_id,
    get_payor_id_from_payments_customer_or_recipient_id,
    get_treatment_procedure_as_dict_from_id,
    get_treatment_procedures_as_dicts_from_ids,
    payments_customer_id,
)
from direct_payment.billing.models import (
    Bill,
    BillErrorTypes,
    BillMetadataKeys,
    BillProcessingRecord,
    BillStateMachine,
    BillStatus,
    CardFunding,
    MemberBillEstimateInfo,
    PaymentMethodInformation,
    PaymentMethodType,
    PayorType,
    ProcessingRecordTypeT,
)
from direct_payment.billing.repository import (
    BillProcessingRecordRepository,
    BillRepository,
)
from direct_payment.billing.tasks.lib.employer_bill_processing_functions import (
    can_employer_bill_be_processed,
)
from direct_payment.billing.utils import (
    get_auto_process_max_amount,
    is_amount_too_small_for_payment_gateway,
)
from direct_payment.notification.lib.tasks.rq_send_notification import (
    send_notification_event,
)
from direct_payment.pharmacy.tasks.libs.common import (
    UNAUTHENTICATED_PAYMENT_SERVICE_URL,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
)
from storage import connection
from tasks.queues import job
from utils.log import logger

OFFSET_BILL = "offset_bill"
REFUND_BILL = "refund_bill"
TO_REFUND_BILL = "to_refund_bill"

log = logger(__name__)


class BillingService:
    """
    Handles bills for Treatment Plans as a part of Maven Managed Benefits.
    Possible paths:
    New -> Processing <-> Failed. (requires failure message) -> Paid, Refunded, or Cancelled
    New -> Cancelled.
    Full state machine here: direct_payment.billing.models.BillStateMachine
    """

    def __init__(
        self,
        session: scoped_session = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "scoped_session")
        payment_gateway_base_url: str | None = None,
        is_in_uow: bool = True,
    ):
        self.session = session or connection.db.session
        self.bill_repo = BillRepository(session=self.session, is_in_uow=is_in_uow)
        self.bill_processing_record_repo = BillProcessingRecordRepository(
            session=self.session, is_in_uow=is_in_uow
        )
        self.payment_gateway_client = get_client(payment_gateway_base_url)  # type: ignore[arg-type] # Argument 1 to "get_client" has incompatible type "Optional[str]"; expected "str"
        # store the _auto_process_max_amount so that it is consistent across this instance of the service.
        self._auto_process_max_amount = get_auto_process_max_amount()

    def create_bill(
        self,
        payor_type: models.PayorType,
        amount: int,
        label: str,
        payor_id: int,
        treatment_procedure_id: int,
        cost_breakdown_id: int,
        payment_method: models.PaymentMethod = models.PaymentMethod.PAYMENT_GATEWAY,
        payment_method_label: str = None,  # type: ignore[assignment] # Incompatible default for argument "payment_method_label" (default has type "None", argument has type "str")
        is_ephemeral: bool = False,
        headers: Mapping[str, str] = None,  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
    ) -> models.Bill:
        """
        Method to create the bill object and insert it in memory only. Call commit separately to persist to db.
        This does not submit a bill to the payment gateway.
        """
        log.info(
            "Starting direct payment bill creation...",
            bill_payor_type=payor_type,
            bill_payor_id=str(payor_id),
            bill_amount=amount,
            bill_treatment_procedure_id=treatment_procedure_id,
            bill_cost_breakdown_id=cost_breakdown_id,
        )
        now = datetime.datetime.now(datetime.timezone.utc)

        payment_method_type, payment_method_id, payment_method_last4, card_funding = (
            None,
            None,
            None,
            None,
        )

        if amount:
            payment_method_information = self._get_payment_method_type_and_id(
                payor_id, payor_type, headers
            )

            if payment_method_information:
                (
                    payment_method_type,
                    payment_method_id,
                    payment_method_last4,
                    card_funding,
                ) = dataclasses.astuple(payment_method_information)

        # add a fee to the new bill
        calculated_fee = calculate_fee(
            payment_method, payment_method_type, amount, card_funding  # type: ignore[arg-type] # Argument 2 to "calculate_fee" has incompatible type "Optional[Any]"; expected "PaymentMethodType"
        )
        log.info("Fee calculated for bill:", calculated_fee=calculated_fee)

        processing_scheduled_at_or_after = compute_processing_scheduled_at_or_after(
            payor_type, amount, now, treatment_procedure_id, payor_id=payor_id
        )
        bill = models.Bill(
            uuid=uuid.uuid4(),
            amount=amount,
            last_calculated_fee=calculated_fee,
            label=label,
            payor_type=payor_type,
            payor_id=payor_id,
            payment_method=payment_method,  # E.g. Payment Gateway
            payment_method_label=payment_method_label
            or payment_method_last4,  # admin passes this in, so respect that
            procedure_id=treatment_procedure_id,
            cost_breakdown_id=cost_breakdown_id,
            status=BillStatus.NEW,
            created_at=now,  # todo: find out why this isn't automatically updating via the db
            modified_at=now,  # todo: find out why this isn't automatically updating via the db
            payment_method_id=payment_method_id,
            payment_method_type=payment_method_type,
            card_funding=card_funding,
            processing_scheduled_at_or_after=processing_scheduled_at_or_after,
            is_ephemeral=is_ephemeral,
        )
        bill = self.bill_repo.create(instance=bill)
        log.info(
            "Direct payment bill created",
            bill_uuid=str(bill.uuid),
            bill_payor_type=bill.payor_type.value,
            bill_payor_id=str(bill.payor_id),
            bill_payment_method=bill.payment_method,
            bill_procedure_id=bill.procedure_id,
            bill_cost_breakdown_id=bill.cost_breakdown_id,
            bill_amount=bill.amount,
            bill_last_calculated_fee=bill.last_calculated_fee,
            card_funding=card_funding,
            processing_scheduled_at_or_after=processing_scheduled_at_or_after,
        )
        return bill

    def _get_payment_method_type_and_id(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, payor_id, payor_type, headers: Mapping[str, str] = None  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
    ) -> PaymentMethodInformation | None:
        if payor_type == PayorType.CLINIC:
            # clinics do not need this, we allow creation of a clinic bill even without setup in PG - though actual
            # money transfers are blocked.
            return None
        payor_id_str = str(payor_id)
        log.info(
            "Getting payment method info",
            payor_id=payor_id_str,
            payor_type=payor_type.value,
        )
        customer_id = payments_customer_id(payor_id, payor_type)
        if customer_id is None:
            # log used in monitors - do not change.
            log.error(
                "Bill creation failure: Payor has not been set up with a payment gateway customer id.",
                payor_id=payor_id_str,
                payor_type=payor_type.value,
            )
            raise PaymentsGatewaySetupError(
                f"{payor_id} of type: {payor_type.value} has not been setup with a payment gateway id.",
            )
        try:
            customer = self.payment_gateway_client.get_customer(
                str(customer_id), headers
            )
            if not customer.payment_methods:
                # log used in monitors - do not change.
                log.warning(
                    "Payor is not set up with payment methods in payment gateway. Defaulting to none.",
                    payor_id=payor_id_str,
                    payor_type=payor_type.value,
                    customer_id=customer_id,
                )
                return None
            else:
                payment_method_id = customer.payment_methods[0].payment_method_id
                payment_method_type = PaymentMethodType(
                    customer.payment_methods[0].payment_method_type.lower()
                )
                payment_method_label = customer.payment_methods[0].last4

                # TODO - remove after hotfix MR is merged and validated
                # https://gitlab.com/maven-clinic/maven/maven/-/merge_requests/10348
                card_funding = None
                try:
                    card_funding = (
                        CardFunding(customer.payment_methods[0].card_funding)
                        if customer.payment_methods[0].card_funding
                        and hasattr(
                            CardFunding, customer.payment_methods[0].card_funding
                        )
                        else None
                    )
                except Exception:
                    log.warn("Failed to get card funding info", reason=format_exc())
                log.info(
                    "Got payment method info",
                    payor_id=payor_id_str,
                    payor_type=payor_type.value,
                    payment_method_type=payment_method_type,
                    payment_method_id=payment_method_id,
                    payment_method_label=payment_method_label,
                    card_funding=card_funding,
                )
                return PaymentMethodInformation(
                    payment_method_type,
                    payment_method_id,
                    payment_method_label,
                    card_funding,
                )
        except Exception:
            # log used in monitors - do not change.
            log.error(
                "Unable to pull payment information from payment gateway. Defaulting to none.",
                payor_id=payor_id_str,
                payor_type=payor_type.value,
                reason=format_exc(),
            )
            return None

    def create_full_refund_bill_from_bill(
        self, bill: Bill, bill_processing_record: BillProcessingRecord | None
    ) -> Bill | None:
        """
        Method to create the full refund bill object and insert it in the repo in memory. A full refund means that the
        entire fee and amount are being refunded.
        This does NOT submit a bill to the payment gateway.
        This does NOT commit to the DB.
        """
        if not (
            bill.status in {BillStatus.PAID, BillStatus.NEW, BillStatus.FAILED}
            and (bill.amount > 0 or bill.is_ephemeral)
            and (
                bill_processing_record is None  # New Bills
                or bill_processing_record.bill_status
                in {
                    BillStatus.PAID.value,
                    BillStatus.FAILED.value,
                }  # Paid or failed bills
            )
        ):
            log.error(
                "Refund bills can only be created from NEW, FAILED or PAID(non refunded) Member or Employer bills with "
                "positive amounts.",
                bill_payor_type=bill.payor_type,
                bill_status=bill.status,
                bill_amount=bill.amount,
                bill_id=str(bill.id),
                bill_uuid=str(bill.uuid),
            )
            raise InvalidRefundBillCreationError(
                "Refund bills can only be created from NEW, FAILED or PAID(non refunded) Member or Employer bills with "
                "positive amounts."
            )

        now = datetime.datetime.now()  # noqa

        amount_to_refund = bill.amount * -1
        refund_bill = models.Bill(
            uuid=uuid.uuid4(),
            amount=amount_to_refund,
            last_calculated_fee=bill.last_calculated_fee * -1,
            label=bill.label,
            payor_type=bill.payor_type,
            payor_id=bill.payor_id,
            payment_method=bill.payment_method,
            payment_method_label=bill.payment_method_label,
            procedure_id=bill.procedure_id,
            cost_breakdown_id=bill.cost_breakdown_id,
            status=BillStatus.NEW,
            created_at=now,  # another todo: find out why this isn't automatically updating via the db
            modified_at=now,  # another todo: find out why this isn't automatically updating via the db
            payment_method_id=bill.payment_method_id,
            payment_method_type=bill.payment_method_type,
            is_ephemeral=bill.is_ephemeral,
            processing_scheduled_at_or_after=compute_processing_scheduled_at_or_after(
                bill.payor_type,
                amount_to_refund,
                now,
                bill.procedure_id,
                payor_id=bill.payor_id,
            ),
        )

        to_return = self.bill_repo.create(instance=refund_bill)
        return to_return

    def create_full_refund_bills_for_payor(
        self, procedure_id: int, payor_type: PayorType
    ) -> List[Bill]:
        """
        Method to create full refund bills for certain payor, this will target all bills with money movement,
        if payor has multiple charge or transfer bills, then create refund bills for each of them,
        if payor has bill and linked refunded bill, then create bill with offset amount.
        """
        to_return = []
        past_bills = self.get_money_movement_bills_by_procedure_id_payor_type(
            procedure_id=procedure_id, payor_type=payor_type
        )
        bill_to_amount_left = defaultdict(int)
        bill_id_to_bill = {bill.id: bill for bill in past_bills}
        for bill in past_bills:
            if bill.amount > 0:
                bill_to_amount_left[bill.id] += bill.amount
            elif bill.amount < 0:
                linked_bill, _ = self._compute_linked_bill_and_bpr(bill)
                bill_to_amount_left[linked_bill.id] += bill.amount  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "id"
        for bill_id, amount_left in bill_to_amount_left.items():
            if amount_left > 0:
                linked_bill = bill_id_to_bill[bill_id]
                refund_bill = self.create_bill(
                    payor_type=payor_type,
                    amount=-amount_left,
                    label=linked_bill.label,  # type: ignore[arg-type] # Argument "label" to "create_bill" of "BillingService" has incompatible type "Optional[str]"; expected "str"
                    payor_id=linked_bill.payor_id,
                    treatment_procedure_id=procedure_id,
                    cost_breakdown_id=linked_bill.cost_breakdown_id,
                    payment_method=models.PaymentMethod.PAYMENT_GATEWAY,
                    payment_method_label=None,  # type: ignore[arg-type] # Argument "payment_method_label" to "create_bill" of "BillingService" has incompatible type "None"; expected "str"
                    headers=None,  # type: ignore[arg-type] # Argument "headers" to "create_bill" of "BillingService" has incompatible type "None"; expected "Mapping[str, str]"
                )
                to_return.append(refund_bill)
                log.info(
                    "Creating refund bill",
                    linked_bill_id=bill_id,
                    amount=amount_left,
                    procedure_id=procedure_id,
                )
        return to_return

    def _create_remainder_refund_bill_from_partially_refunded_bill(
        self, bill: Bill, refunded_bpr: BillProcessingRecord
    ) -> Bill | None:
        refunded_bill_id = refunded_bpr.body.get(REFUND_BILL, None)
        if refunded_bill_id is None:
            log.error(
                "Unable to find refunded bill linked to bpr body..",
                bill_id=str(bill.id),
                bpr_id=refunded_bpr.id,
            )
            raise InvalidRefundBillCreationError(
                f"Unable to find refunded bill linked to {bill.id} in bpr body."
            )
        loaded_refunded_bills = self.bill_repo.get_by_ids([refunded_bill_id])
        if not loaded_refunded_bills:
            log.critical(
                "Unable to load refunded bill. This should never happen.",
                refunded_bill_id=str(refunded_bill_id),
                bpr_id=refunded_bpr.id,
            )
            raise InvalidRefundBillCreationError(
                f"Unable to load refunded bill with id: {refunded_bill_id} linked to {bill.id}."
            )
        loaded_refunded_bill = loaded_refunded_bills[0]
        log.info(
            "Loaded previously refunded bill.",
            loaded_refunded_bill_id=str(loaded_refunded_bill.id),
            loaded_refunded_bill_uuid=str(loaded_refunded_bill.uuid),
            loaded_refunded_bill_amount=loaded_refunded_bill.amount,
            loaded_refunded_bill_status=str(loaded_refunded_bill.status),
        )
        # A cancelled refund should be ignored.
        already_refunded_amt, already_refunded_fee = (
            (0, 0)
            if loaded_refunded_bill.status == BillStatus.CANCELLED
            else (
                abs(loaded_refunded_bill.amount),
                abs(loaded_refunded_bill.last_calculated_fee),  # type: ignore[arg-type] # Argument 1 to "abs" has incompatible type "Optional[int]"; expected "SupportsAbs[int]"
            )
        )
        amount_to_refund = (bill.amount - already_refunded_amt) * -1
        fee_to_refund = (bill.last_calculated_fee - already_refunded_fee) * -1
        if amount_to_refund == 0:
            log.info(
                "This bill has already been fully refunded. Nothing to do here.",
                bill_id=str(bill.id),
            )
            to_return = None
        else:
            log.info(
                "Creating refund bill for bill.",
                bill_id=str(bill.id),
                amount_to_refund=amount_to_refund,
                fee_to_refund=fee_to_refund,
            )
            now = datetime.datetime.now()  # noqa
            new_refund_bill = models.Bill(
                uuid=uuid.uuid4(),
                amount=amount_to_refund,
                last_calculated_fee=fee_to_refund,
                label=bill.label,
                payor_type=bill.payor_type,
                payor_id=bill.payor_id,
                payment_method=bill.payment_method,
                payment_method_label=bill.payment_method_label,
                procedure_id=bill.procedure_id,
                cost_breakdown_id=bill.cost_breakdown_id,
                status=BillStatus.NEW,
                created_at=now,
                modified_at=now,
                payment_method_id=bill.payment_method_id,
                payment_method_type=bill.payment_method_type,
                processing_scheduled_at_or_after=compute_processing_scheduled_at_or_after(
                    bill.payor_type,
                    amount_to_refund,
                    now,
                    bill.procedure_id,
                    payor_id=bill.payor_id,
                ),
            )
            to_return = self.bill_repo.create(instance=new_refund_bill)
        return to_return

    def get_bill_by_id(self, bill_id: int) -> models.Bill | None:
        return self.bill_repo.get(id=bill_id)

    def get_bills_by_ids(self, bill_ids: list[int]) -> list[models.Bill]:
        return self.bill_repo.get_by_ids(ids=bill_ids)

    def get_bill_by_uuid(self, bill_uuid: str) -> models.Bill | None:
        return self.bill_repo.get_by_uuid(uuid=bill_uuid)

    def get_latest_records_with_specified_statuses_for_bill_ids(
        self, bill_ids: list[int], statuses: list[models.BillStatus]
    ) -> dict[int, models.BillProcessingRecord]:
        """
        Passthrough function: Returns a dict of the bill ids to the last bill processing record if the record is one of
        the specified statuses. Bills that don't have a match will not have entries in the dict.
        :param bill_ids: Bill ids in scope
        :param statuses: Any of these bill statuses is acceptable as the head record on a bill
        :return: a dict of the bill ids to the last bill processing record
        """
        return self.bill_processing_record_repo.get_latest_records_with_specified_statuses_for_bill_ids(
            bill_ids, statuses
        )

    def get_money_movement_bills_by_procedure_id_payor_type(
        self, procedure_id: int, payor_type: PayorType
    ) -> list[models.Bill]:
        """
        Given a procedure id and a payor type, returns all the bills that had or could have money movement. This includes
        all PAID, NEW, PROCESSING, and FAILED bills. This also includes REFUNDED bills that were sent to the payment
        gateway. This excludes all CANCELLED bills and the REFUND bills that cancelled them.
        REFUND bills that initiated cancellations do not have transaction ids because there was no payment gateway
        interaction
        """
        to_return = self.bill_repo.get_money_movement_bills_by_procedure_id_payor_type(
            procedure_id,
            payor_type=payor_type,
            bpr_table=self.bill_processing_record_repo.table,
        )
        return to_return

    def get_money_movement_bills_by_procedure_ids_payor_type_ytd(
        self, procedure_ids: list[int], payor_type: PayorType
    ) -> list[models.Bill]:
        """
        Given a list of procedure ids and a payor type, returns all the bills that had or could have money movement for
        the current year. This includes all PAID, NEW, PROCESSING, and FAILED bills. This also includes REFUNDED
        bills that were sent to the payment gateway. This excludes all CANCELLED bills and the REFUND bills that
        cancelled them. REFUND bills that initiated cancellations do not have transaction ids because there was no
         payment gateway interaction.
        """
        to_return = (
            self.bill_repo.get_money_movement_bills_by_procedure_ids_payor_type_ytd(
                procedure_ids,
                payor_type=payor_type,
                bpr_table=self.bill_processing_record_repo.table,
            )
        )
        return to_return

    def get_processable_new_member_bills_y(
        self, *, processing_time_threshold: datetime  # type: ignore[valid-type] # Module "datetime" is not valid as a type
    ) -> list[models.Bill]:
        """
        Returns all new member bills with processing_scheduled_at_or_after before the processing_time_threshold.
        :param processing_time_threshold:
        :return: A possibly empty list of bills
        """
        return self.bill_repo.get_processable_new_member_bills(
            processing_time_threshhold=processing_time_threshold
        )

    def get_new_employer_bills_for_payor_ids_in_datetime_range(
        self,
        payor_ids: list[int],
        start_datetime: datetime.datetime,
        end_datetime: datetime.datetime,
    ) -> list[Bill]:
        return self.bill_repo.get_new_bills_by_payor_ids_and_type_in_date_time_range(
            payor_ids=payor_ids,
            payor_type=PayorType.EMPLOYER,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
        )

    def get_by_payor_types_statuses(
        self,
        payor_types: list[models.PayorType] | None,
        statuses: list[models.BillStatus] | None,
    ) -> list[models.Bill]:
        """
        Gets bills of specified payor types and statuses
        @param payor_types: The payor types to filter by.
        @param statuses: The status types to filter by.
        @return: list of models.Bill objects
        """
        to_return = self.bill_repo.get_by_payor_types_statuses_date_range(
            payor_types, statuses
        )
        return to_return

    def set_new_bill_to_processing(
        self, input_bill: models.Bill, headers: Mapping[str, str] = None  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
    ) -> models.Bill:
        if input_bill.status != models.BillStatus.NEW:
            raise errors.InvalidInputBillStatus(
                "Only NEW bills may be processed through this function."
            )
        if is_amount_too_small_for_payment_gateway(
            input_bill.amount, self._auto_process_max_amount
        ):
            updated_bill = self._process_amount_too_small_for_pg_bill(input_bill)
        else:
            updated_bill = self._charge_transfer_or_refund_bill(
                input_bill, 1, "", headers  # TODO stop setting this as blank.
            )

        return updated_bill

    def _charge_transfer_or_refund_bill(
        self,
        input_bill: Bill,
        attempt_count: int,
        initiated_by: str,
        headers: Mapping[str, str] | None = None,
    ) -> Bill:
        auto_process_max_amount = self._auto_process_max_amount
        if input_bill.amount > auto_process_max_amount:
            updated_bill = self._charge_or_transfer_bill(
                bill=input_bill,
                attempt_count=attempt_count,
                initiated_by=initiated_by,
                headers=headers,  # type: ignore[arg-type] # Argument "headers" to "_charge_or_transfer_bill" of "BillingService" has incompatible type "Optional[Mapping[str, str]]"; expected "Mapping[str, str]"
            )
        elif input_bill.amount < -auto_process_max_amount:
            updated_bill = self._refund_or_reverse_transfer_bill(
                refund_or_reverse_transfer_bill=input_bill,
                attempt_count=attempt_count,
                initiated_by=initiated_by,
                headers=headers,
            )
        else:
            raise ValueError(
                "This bill is too small (abs(bill.amount)) to be processed by this method."
            )
        return updated_bill

    def _process_amount_too_small_for_pg_bill(self, input_bill: Bill) -> Bill:
        log.info(
            "Processing too-small amount bill",
            input_bill_id=str(input_bill.id),
            input_bill_uuid=str(input_bill.uuid),
            input_bill_status=input_bill.status.value,
            input_bill_amount=input_bill.amount,
        )
        processed_bill = self._update_bill_add_bpr_and_commit(
            bill=input_bill,
            new_bill_status=models.BillStatus.PROCESSING,
            record_type="billing_service_workflow",
            record_body={},
            transaction_id=None,
        )

        updated_bill = self._update_bill_add_bpr_and_commit(
            bill=processed_bill,
            new_bill_status=models.BillStatus.PAID,
            record_type="billing_service_workflow",
            record_body={},
            transaction_id=None,
        )
        log.info(
            "Processed too-small amount bill",
            updated_bill_id=str(updated_bill.id),
            updated_bill_uuid=str(updated_bill.uuid),
            updated_bill_status=updated_bill.status.value,
            updated_bill_amount=updated_bill.amount,
        )
        return updated_bill

    def _process_amount_too_small_for_pg_bill_without_commit(
        self, input_bill: Bill
    ) -> Bill:
        log.info(
            "Processing too-small amount bill without commit.",
            input_bill_id=str(input_bill.id),
            input_bill_uuid=str(input_bill.uuid),
            input_bill_status=input_bill.status.value,
            input_bill_amount=input_bill.amount,
        )
        processed_bill = self._update_bill_and_add_bpr_without_commit(
            bill=input_bill,
            new_bill_status=models.BillStatus.PROCESSING,
            record_type="billing_service_workflow",
            record_body={},
            transaction_id=None,
        )

        updated_bill = self._update_bill_and_add_bpr_without_commit(
            bill=processed_bill,
            new_bill_status=models.BillStatus.PAID,
            record_type="billing_service_workflow",
            record_body={},
            transaction_id=None,
        )
        log.info(
            "Processed too-small amount bill without commit.",
            updated_bill_id=str(updated_bill.id),
            updated_bill_uuid=str(updated_bill.uuid),
            updated_bill_status=updated_bill.status.value,
            updated_bill_amount=updated_bill.amount,
        )
        return updated_bill

    def cancel_bill(
        self,
        input_bill: Bill,
        refund_bill: Bill,
        delta_bill: Bill,
        record_type: ProcessingRecordTypeT,
    ) -> Bill:
        """
        Cancels a bill, transitioning it to cancelled without payment gateway involvement. Transitions the refund bill
        that initiated the cancel to PAID ensuring that the position remains flat.
        All these happen in a single transaction
        :param input_bill: The bill to be cancelled.
        :param refund_bill: The refund bill that is driving the cancellation
        :param delta_bill: The bill to represent the delta between input bill and refund bill. amt >= 0
        :param record_type: To track the source of this event
        :return: the cancelled bill

        """
        can_process_cancellation = (
            input_bill.payor_type != PayorType.EMPLOYER
            or can_employer_bill_be_processed(input_bill)
        )
        log.info(
            "Can bill cancellation be processed?",
            input_bill_id=str(input_bill.id),
            refund_bill_id=str(refund_bill.id),
            delta_bill_id=str(delta_bill.id),
            can_process_cancellation=can_process_cancellation,
            input_bill_payor_type=str(input_bill.payor_type),
            message=(
                "Bill cancellation attempted."
                if can_process_cancellation
                else "Bill cancellation skipped."
            ),
        )
        if can_process_cancellation:
            to_return = self._cancel_bill_without_commit(
                input_bill, refund_bill, record_type
            )
            self.session.commit()
            if delta_bill.amount <= self._auto_process_max_amount:
                self._process_amount_too_small_for_pg_bill(delta_bill)
            return to_return
        return input_bill

    def _cancel_bill_without_commit(
        self,
        input_bill: Bill,
        refund_bill: Bill,
        record_type: ProcessingRecordTypeT,
    ) -> Bill:
        cancelled_bill_record_body = {
            REFUND_BILL: refund_bill.id,
            OFFSET_BILL: input_bill.id,
        }
        to_return = self._update_bill_and_add_bpr_without_commit(
            bill=input_bill,
            new_bill_status=BillStatus.CANCELLED,
            record_type=record_type,
            record_body=cancelled_bill_record_body,
            transaction_id=None,
        )
        refund_bill = self._update_bill_and_add_bpr_without_commit(
            bill=refund_bill,
            new_bill_status=BillStatus.PROCESSING,
            record_type="billing_service_workflow",
            record_body=cancelled_bill_record_body,
            transaction_id=None,
        )
        _ = self._update_bill_and_add_bpr_without_commit(
            bill=refund_bill,
            new_bill_status=BillStatus.REFUNDED,
            record_type="billing_service_workflow",
            record_body=cancelled_bill_record_body,
            transaction_id=None,
        )
        return to_return

    def cancel_bill_with_offsetting_refund(
        self, bill: Bill, record_type: ProcessingRecordTypeT, initiated_by: str
    ) -> Bill:
        if bill.status != BillStatus.NEW and bill.status != BillStatus.FAILED:
            raise errors.InvalidInputBillStatus(
                f"Bill {bill.id} cannot be cancelled with status: {bill.status}"
            )

        refund_bill = self.create_full_refund_bill_from_bill(bill, None)
        self.session.commit()
        refund_bill = self.get_bill_by_uuid(str(refund_bill.uuid))  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "uuid"
        _ = self.set_new_refund_or_reverse_bill_to_processing(
            refund_or_reverse_transfer_bill=refund_bill,  # type: ignore[arg-type] # Argument "refund_or_reverse_transfer_bill" to "set_new_refund_or_reverse_bill_to_processing" of "BillingService" has incompatible type "Optional[Bill]"; expected "Bill"
            linked_bill=bill,
            linked_bill_pr=None,
            attempt_count=1,
            record_type=record_type,
            initiated_by=initiated_by,
            headers=None,
        )
        # load the possibly cancelled bill
        to_return = self.bill_repo.get_by_ids([bill.id])[0]  # type: ignore[list-item] # List item 0 has incompatible type "Optional[int]"; expected "int"
        if to_return.status == BillStatus.CANCELLED:
            log.info("Cancelled Bill", bill_id=str(bill.id), bill_uuid=str(bill.uuid))
        else:
            log.info(
                "Cancellation of Bill deferred (probaly invoiced)",
                bill_id=str(bill.id),
                bill_uuid=str(bill.uuid),
            )
        return to_return

    def _cancel_estimate_without_commit(self, estimate: Bill):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        refund_estimate = self.create_full_refund_bill_from_bill(estimate, None)
        self._cancel_bill_without_commit(
            estimate, refund_estimate, "billing_service_workflow"  # type: ignore[arg-type] # Argument 2 to "_cancel_bill_without_commit" of "BillingService" has incompatible type "Optional[Bill]"; expected "Bill"
        )

    def create_full_refund_bill_from_potentially_partially_refunded_paid_bill(
        self, bill: Bill, record_type: ProcessingRecordTypeT
    ) -> Bill:
        log.info(
            "Attempting to refund paid bill.",
            bill_id=str(bill.id),
            bill_uuid=str(bill.uuid),
            bill_payor_type=bill.payor_type.value if bill.payor_type else "",
            bill_status=bill.status.value if bill.status else "",
            bill_amount=bill.amount,
        )
        if bill.status not in {BillStatus.PAID}:
            raise errors.InvalidInputBillStatus(
                f"Bill {bill.id} with status: {bill.status} cannot be processed through this flow."
            )
        if not (bill.status == BillStatus.PAID and bill.amount > 0):
            log.error(
                "This flow only supports PAID bills with positive amounts.",
                bill_id=str(bill.id),
                bill_uuid=str(bill.uuid),
            )
            raise InvalidRefundBillCreationError(
                "This flow only supports PAID bills with positive amounts."
            )

        # check if this bill already had refunds,
        bil_bpr_map = self.bill_processing_record_repo.get_all_records_with_specified_statuses_for_bill_ids(
            [bill.id], [BillStatus.REFUNDED]  # type: ignore[list-item] # List item 0 has incompatible type "Optional[int]"; expected "int"
        )
        bprs = bil_bpr_map.get(bill.id, [])  # type: ignore[arg-type] # Argument 1 to "get" of "dict" has incompatible type "Optional[int]"; expected "int"

        # TODO extend to support multiple refunds
        if len(bprs) > 1:
            log.error(
                "Multiple refunds already linked to input bill.",
                bill_id=str(bill.id),
            )
            raise InvalidRefundBillCreationError(
                "Only PAID Member or Employer bills with +ve amounts and with at most 1 previous refund are supported."
            )

        to_return = None
        if len(bprs) == 0:
            # get the other bprs linked to this bill.
            latest_bpr = self.bill_processing_record_repo.get_latest_bill_processing_record_if_paid(
                [bill.id]  # type: ignore[list-item] # List item 0 has incompatible type "Optional[int]"; expected "int"
            )
            refund_bill = self.create_full_refund_bill_from_bill(bill, latest_bpr)
        else:
            latest_bpr = bprs.pop()
            refund_bill = (
                self._create_remainder_refund_bill_from_partially_refunded_bill(
                    bill=bill, refunded_bpr=latest_bpr
                )
            )
        if refund_bill:
            # Using the convenient function to create a bpr with linkage.
            to_return = self._update_bill_add_bpr_and_commit(
                bill=refund_bill,
                new_bill_status=refund_bill.status,
                record_type=record_type,
                record_body={TO_REFUND_BILL: bill.id},
                transaction_id=latest_bpr.transaction_id,  # type: ignore[union-attr] # Item "None" of "Optional[BillProcessingRecord]" has no attribute "transaction_id"
            )
        else:
            log.info(
                "Refund bill was not created.",
                bill_id=bill.id,
                bill_uuid=str(bill.uuid),
            )
        return to_return  # type: ignore[return-value] # Incompatible return value type (got "Optional[Bill]", expected "Bill")

    def update_payment_method_on_bill(
        self, bill: Bill, record_type: ProcessingRecordTypeT
    ) -> str:
        log.info(
            "Attempting to update payment method on bill:",
            bill_id=str(bill.id),
            bill_uuid=str(bill.uuid),
            bill_status=bill.status.value,
            bill_payor_type=bill.payor_type.value,
        )
        if bill.status not in {models.BillStatus.NEW, models.BillStatus.FAILED}:
            return f"Bill <{bill.id}> is not in status NEW or FAILED. Update payment method failed."
        if bill.payor_type not in {
            models.PayorType.EMPLOYER,
            models.PayorType.MEMBER,
        }:
            return f"Bill <{bill.id}> is not an EMPLOYER or MEMBER bill. Update payment method failed."

        payment_method_information = self._get_payment_method_type_and_id(
            bill.payor_id, bill.payor_type
        )
        log.info(
            "Pulled payment method info for bill.",
            bill_id=str(bill.id),
            bill_uuid=str(bill.uuid),
            bill_status=bill.status.value,
            bill_payor_type=bill.payor_type.value,
            payment_method_information=str(payment_method_information),
        )
        if not payment_method_information:
            log.info(
                "Null payment method info pulled for bill.",
                bill_id=str(bill.id),
                bill_uuid=str(bill.uuid),
            )
            return f"The payment method pulled from payment gateway for bill {bill.id} was null."

        payment_method_package = {
            "last4": payment_method_information.payment_method_last4,
            "card_funding": (
                payment_method_information.card_funding.value
                if payment_method_information.card_funding
                else None
            ),
            "payment_method_id": payment_method_information.payment_method_id,
            "payment_method_type": (
                payment_method_information.payment_method_type.value
                if payment_method_information.payment_method_type
                else None
            ),
        }

        updated_bill_ids = self._update_payment_data_on_bills_add_bprs_in_memory(
            payment_method_package,  # type: ignore[arg-type] # Argument 1 to "_update_payment_data_on_bills_add_bprs_in_memory" of "BillingService" has incompatible type "Dict[str, Optional[str]]"; expected "Dict[str, str]"
            [bill],
            message=None,
            record_type=record_type,
        )
        # commit here - in the calling function only if there were updates to commit
        if updated_bill_ids:
            self.session.commit()
            res = f"Payment method update on bill: {bill.id} succeeded."
            log.info(
                "Successfully updated payment method info on bill and committed to DB.",
                bill_id=bill.id,
            )
        else:
            res = f"Payment method info update unnecessary on {bill.id}."
            log.info(
                "Payment method info update unnecessary on the bill",
                bill_id=bill.id,
            )
        return res

    def get_bills_by_procedure_ids(
        self,
        procedure_ids: list[int],
        payor_type: models.PayorType | None = None,
        payor_id: int | None = None,
        exclude_payor_types: list[models.PayorType] | None = None,
        status: list[models.BillStatus] | None = None,
    ) -> list[models.Bill]:
        """
        Retrieve bills by a combination of search parameters. Note that payor_type is required if payor_id is provided.
        """
        return self.bill_repo.get_by_procedure(
            procedure_ids=procedure_ids,
            payor_id=payor_id,
            payor_type=payor_type,
            exclude_payor_types=exclude_payor_types,
            status=status,
            is_ephemeral=False,
        )

    def get_estimates_by_procedure_ids(
        self,
        procedure_ids: list[int],
        payor_type: models.PayorType | None = None,
        payor_id: int | None = None,
        exclude_payor_types: list[models.PayorType] | None = None,
        status: list[models.BillStatus] | None = None,
    ) -> list[models.Bill]:
        """
        Retrieve estimates by a combination of search parameters. Note that payor_type is required if payor_id is
        provided.
        """
        return self.bill_repo.get_by_procedure(
            procedure_ids=procedure_ids,
            payor_id=payor_id,
            payor_type=payor_type,
            exclude_payor_types=exclude_payor_types,
            status=status,
            is_ephemeral=True,
        )

    def get_count_bills_by_payor_with_historic(
        self,
        payor_type: models.PayorType,
        payor_id: int,
    ) -> int:
        return self.bill_repo.count_by_payor_with_historic(
            payor_id=payor_id, payor_type=payor_type
        )

    def get_upcoming_bills_by_payor(
        self,
        payor_type: models.PayorType,
        payor_id: int,
    ) -> list[models.Bill]:
        return self.bill_repo.get_by_payor(
            payor_id=payor_id, payor_type=payor_type, status=models.UPCOMING_STATUS
        )

    def get_estimates_by_payor(
        self,
        payor_type: models.PayorType,
        payor_id: int,
    ) -> list[models.Bill]:
        return self.bill_repo.get_estimates_by_payor(
            payor_id=payor_id, payor_type=payor_type
        )

    def get_member_estimate_by_procedure(self, procedure_id: int) -> Bill or None:  # type: ignore[valid-type] # Invalid type comment or annotation
        estimates = self.get_member_estimates_by_procedures(
            procedure_ids=[procedure_id]
        )
        if len(estimates) > 1:
            log.error(
                "Multiple esitmates found for procedure", procedure_id=procedure_id
            )
            raise ValueError
        return estimates[0] if estimates else None

    def get_member_estimates_by_procedures(
        self,
        procedure_ids: list[int],
    ) -> list[models.Bill]:
        return self.bill_repo.get_member_estimates_by_procedures(
            procedure_ids=procedure_ids
        )

    def get_bills_by_payor_with_historic(
        self,
        payor_type: models.PayorType,
        payor_id: int,
        historic_limit: int,
        historic_offset: int = 0,
    ) -> list[models.Bill]:
        return self.bill_repo.get_by_payor_with_historic(
            payor_id=payor_id,
            payor_type=payor_type,
            historic_limit=historic_limit,
            historic_offset=historic_offset,
        )

    def retry_bill(
        self, bill: models.Bill, initiated_by: str, headers: Mapping[str, str] = None  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
    ) -> models.Bill:
        if bill.status != models.BillStatus.FAILED:
            raise errors.InvalidBillStatusChange("Only FAILED bills may be retried.")
        # TODO: get idempotency key + lock from bill processing records here PAY-4281
        # An attempt = a bill processing record with the `payment_gateway_request` record_type.
        attempt_count = 1 + (
            self.bill_processing_record_repo.get_bill_processing_attempt_count(
                bill=bill
            )
        )
        updated_bill = self._charge_transfer_or_refund_bill(
            bill, attempt_count, initiated_by, headers
        )
        return updated_bill

    def calculate_new_and_past_bill_amount_from_new_responsibility(
        self,
        new_responsibility: int,
        procedure_id: int,
        payor_id: int,
        payor_type: PayorType,
    ) -> tuple[int | None, int]:
        """
         returns None, previous_resp if there has been no change since a past bill
         returns 0, 0 if the responsibility is 0 and there are no past bills
        :param new_responsibility: New responsibility amount
        :param procedure_id: The procedure id.
        :param payor_id: The payor id
        :param payor_type: MEMBER or EMPLOYER - clinics cannot be payor
        :return: Tuple of new and past responsibility.
        :rtype:
        """
        past_bills = self.get_money_movement_bills_by_procedure_id_payor_type(
            procedure_id, payor_type
        )
        past_amount = sum([bill.amount for bill in past_bills], start=0)
        past_bill_uuids = ", ".join([str(pb_.uuid) for pb_ in past_bills])
        log.info(
            "Past bill amt calcs:",
            new_responsibility=new_responsibility,
            past_amount=past_amount,
            past_bills_cnt=len(past_bills),
            past_bill_uuids=past_bill_uuids,
            procedure_id=procedure_id,
            payor_id=str(payor_id),
            payor_type=payor_type.value,
        )
        if len(past_bills) > 0 and past_amount == new_responsibility:
            # No new bill is needed
            return None, past_amount
        new_amount = new_responsibility - past_amount
        log.info("new_amount calcs", new_amount=new_amount)
        return new_amount, past_amount

    def calculate_past_bill_fees_for_procedure(
        self, current_bill: models.Bill
    ) -> int | None:
        procedure_bills = self.get_money_movement_bills_by_procedure_id_payor_type(
            current_bill.procedure_id, current_bill.payor_type
        )
        # Return None to reflect the fact that there are no previous bills
        if not procedure_bills:
            return None
        fees = sum(
            [
                bill.last_calculated_fee
                for bill in procedure_bills
                if bill.id != current_bill.id
            ],
            start=0,
        )

        procedure_bills_uuids = ", ".join(str(pb_.uuid) for pb_ in procedure_bills)
        log.info(
            "Past bill fee calcs",
            past_fees=fees,
            past_bills_cnt=len(procedure_bills),
            current_bill_uuid=str(current_bill.uuid),
            procedure_bills_uuids=procedure_bills_uuids,
            procedure_id=current_bill.procedure_id,
            payor_id=str(current_bill.payor_id),
            payor_type=current_bill.payor_type.value,
        )

        return fees

    def handle_member_billing_for_procedure(
        self,
        delta: int,
        payor_id: int,
        procedure_id: int,
        procedure_name: str,
        cost_breakdown_id: int,
        treatment_procedure_status: str,
    ) -> MemberBillEstimateInfo:
        scheduled_tp_state = treatment_procedure_status == "SCHEDULED"
        if delta is None:
            self.cancel_member_estimates_for_procedures_without_commit(
                procedure_ids=[procedure_id]
            )
            return MemberBillEstimateInfo(
                estimate=None,
                bill=None,
                should_caller_commit=True,
                should_caller_notify_of_bill=False,
            )
        elif delta == 0:
            """
            Handling case where there the member does not owe any more for the treatment procedure.
            If the TP is SCHEDULED and there isn't already an estimate that == the delta in member responsibility (0), we
            want to generate another estimate.
            If the TP is not in a SCHEDULED state we want to cancel any existing estimates.
            """
            if scheduled_tp_state:
                if self._has_estimate_covering_delta_or_cancels(
                    procedure_id=procedure_id, delta=0
                ):
                    # There is already an estimate covering the amount and we do not need to do anything
                    return MemberBillEstimateInfo(
                        estimate=None,
                        bill=None,
                        should_caller_commit=False,
                        should_caller_notify_of_bill=False,
                    )
                else:
                    estimate = self.create_bill(
                        label=procedure_name,
                        amount=0,
                        payor_type=PayorType.MEMBER,
                        payor_id=payor_id,
                        treatment_procedure_id=procedure_id,
                        cost_breakdown_id=cost_breakdown_id,
                        is_ephemeral=True,
                    )
                    return MemberBillEstimateInfo(
                        estimate=estimate,
                        bill=None,
                        should_caller_commit=True,
                        should_caller_notify_of_bill=False,
                    )
            else:
                self.cancel_member_estimates_for_procedures_without_commit(
                    procedure_ids=[procedure_id]
                )
                bill = self.create_bill(
                    label=procedure_name,
                    amount=0,
                    payor_type=PayorType.MEMBER,
                    payor_id=payor_id,
                    treatment_procedure_id=procedure_id,
                    cost_breakdown_id=cost_breakdown_id,
                    payment_method=models.PaymentMethod.PAYMENT_GATEWAY,
                )
                log.info(
                    "The cancellation of an estimate has spawned a paid 0 member bill.",
                    bill_id=str(bill.id),
                    bill_amount=bill.amount,
                    bill_status=bill.status.value,
                )
                bill = self._process_amount_too_small_for_pg_bill_without_commit(bill)
                return MemberBillEstimateInfo(
                    estimate=None,
                    bill=bill,
                    should_caller_commit=True,
                    should_caller_notify_of_bill=False,
                )
        elif delta > 0:
            """
            Handling case where there was an INCREASE in member responsibility.
            If the TP is SCHEDULED and there isn't already an estimate that == the delta in member responsibility, we
            want to generate another estimate.
            If the TP is not in a SCHEDULED state we want to cancel any existing estimates and generate a bill for the delta.
            """
            if scheduled_tp_state:
                # There is already an estimate covering the amount and we do not need to do anything
                if self._has_estimate_covering_delta_or_cancels(
                    procedure_id=procedure_id, delta=delta
                ):
                    return MemberBillEstimateInfo(
                        estimate=None,
                        bill=None,
                        should_caller_commit=False,
                        should_caller_notify_of_bill=False,
                    )
                else:
                    estimate = self.create_bill(
                        label=procedure_name,
                        amount=delta,
                        payor_type=PayorType.MEMBER,
                        payor_id=payor_id,
                        treatment_procedure_id=procedure_id,
                        cost_breakdown_id=cost_breakdown_id,
                        is_ephemeral=True,
                    )
                return MemberBillEstimateInfo(
                    estimate=estimate,
                    bill=None,
                    should_caller_commit=True,
                    should_caller_notify_of_bill=False,
                )
            else:
                self.cancel_member_estimates_for_procedures_without_commit(
                    procedure_ids=[procedure_id]
                )
                bill = self.create_bill(
                    label=procedure_name,
                    amount=delta,
                    payor_type=PayorType.MEMBER,
                    payor_id=payor_id,
                    treatment_procedure_id=procedure_id,
                    cost_breakdown_id=cost_breakdown_id,
                    payment_method=models.PaymentMethod.PAYMENT_GATEWAY,
                )
                should_caller_notify = True
                if delta <= self._auto_process_max_amount:
                    bill = self._process_amount_too_small_for_pg_bill_without_commit(
                        bill
                    )
                    should_caller_notify = False

                return MemberBillEstimateInfo(
                    estimate=None,
                    bill=bill,
                    should_caller_commit=True,
                    should_caller_notify_of_bill=should_caller_notify,
                )
        """
        Handling case where there was a DECREASE in member responsibility.
        We want to cancel any existing estimates and handle the refund. If a delta bill is generated and the TP is
        in a scheduled state, the flow triggered in _refund_or_reverse_transfer_bill will make it an estimate.
        """
        self.cancel_member_estimates_for_procedures_without_commit(
            procedure_ids=[procedure_id]
        )
        bill = self.create_bill(
            label=procedure_name,
            amount=delta,
            payor_type=PayorType.MEMBER,
            payor_id=payor_id,
            treatment_procedure_id=procedure_id,
            cost_breakdown_id=cost_breakdown_id,
            payment_method=models.PaymentMethod.PAYMENT_GATEWAY,
        )
        # depending on what happens downstream, the updated_bill will either be a delta estimate (if the previous
        # bill was in a NEW status and be cancelled), it will be the cancelled bill (if there is no delta bill), OR
        # if the previous bill was already PROCESSING or PAID, the bill returned is the refund bill that is now
        # in processing
        updated_bill = self._refund_or_reverse_transfer_bill(
            refund_or_reverse_transfer_bill=bill,
            attempt_count=1,
        )
        estimate, returned_bill = (
            (updated_bill, None) if updated_bill.is_ephemeral else (None, updated_bill)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[Bill]", variable has type "Bill")
        )

        return MemberBillEstimateInfo(
            estimate=estimate,
            bill=returned_bill,
            should_caller_commit=True,
            should_caller_notify_of_bill=False,  # refund notifications happen within billing
        )

    def _has_estimate_covering_delta_or_cancels(
        self, procedure_id: int, delta: int
    ) -> bool:
        estimate = self.get_member_estimate_by_procedure(procedure_id=procedure_id)
        if estimate:
            if estimate.amount == delta:
                return True
            else:
                log.info(
                    "Cancelling estimate not matching delta for procedure",
                    procedure_id=procedure_id,
                    bill_uuid=estimate.uuid,
                )
                self._cancel_estimate_without_commit(estimate=estimate)
        return False

    def cancel_member_estimates_for_procedures_without_commit(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        procedure_ids: list[int],
    ):
        estimates_for_procedures = self.get_member_estimates_by_procedures(
            procedure_ids=procedure_ids
        )
        estimate_ids = [estimate.id for estimate in estimates_for_procedures]
        log.info(
            "Attempting to cancel estimates for treatment procedures",
            procedure_ids=procedure_ids,
            bill_ids=estimate_ids,
        )
        for estimate in estimates_for_procedures:
            self._cancel_estimate_without_commit(estimate=estimate)

    @staticmethod
    def _update_bill_status(
        bill: models.Bill,
        new_bill_status: models.BillStatus,
        error_type: str | None = None,
        record_body: dict | None = None,
    ) -> models.Bill:
        if not BillStateMachine.is_valid_transition(bill.status, new_bill_status):
            raise errors.InvalidBillStatusChange(
                f"Invalid state transition from {bill.status} to {new_bill_status}."
            )

        status_field_dict = {
            BillStatus.NEW: "created_at",
            BillStatus.PROCESSING: "processing_at",
            BillStatus.PAID: "paid_at",
            BillStatus.REFUNDED: "refunded_at",
            BillStatus.CANCELLED: "cancelled_at",
            BillStatus.FAILED: "failed_at",
        }
        replacement_data = {
            "status": new_bill_status,
            "error_type": None,  # have the error type default to blank (to clear a bill coming out of failed)
            status_field_dict[new_bill_status]: datetime.datetime.now(),  # noqa
            "display_date": status_field_dict[new_bill_status],
        }

        # additional handling for failed bills
        if new_bill_status == models.BillStatus.FAILED:
            # don't allow blank strings
            if error_type is not None:
                error_type = error_type.strip() or None
            # can inherit previous error state
            if not (rep_error_type := error_type or bill.error_type):
                raise errors.InvalidBillStatusChange(
                    "An error_type is required to mark a bill as FAILED."
                )
            replacement_data["error_type"] = rep_error_type

        # description can have PII on clinic bills and needs to be removed.
        record_body_to_log = copy.deepcopy(record_body)
        if bill.payor_type == PayorType.CLINIC:
            if "transaction_data" in record_body_to_log and isinstance(
                record_body_to_log["transaction_data"], Mapping  # type: ignore[index] # Value of type "Optional[Dict[Any, Any]]" is not indexable
            ):

                record_body_to_log["transaction_data"]["description"] = "__REDACTED__"  # type: ignore[index] # Value of type "Optional[Dict[Any, Any]]" is not indexable #type: ignore[index] # Unsupported target for indexed assignment ("Mapping[Any, Any]")
            elif (
                "message_payload" in record_body_to_log
                and isinstance(record_body_to_log["message_payload"], Mapping)  # type: ignore[index] # Value of type "Optional[Dict[Any, Any]]" is not indexable
                and "transaction_data" in record_body_to_log["message_payload"]  # type: ignore[index] # Value of type "Optional[Dict[Any, Any]]" is not indexable
                and isinstance(
                    record_body_to_log["message_payload"]["transaction_data"], Mapping  # type: ignore[index] # Value of type "Optional[Dict[Any, Any]]" is not indexable
                )
            ):
                record_body_to_log["message_payload"]["transaction_data"][  # type: ignore[index] # Value of type "Optional[Dict[Any, Any]]" is not indexable #type: ignore[index] # Unsupported target for indexed assignment ("Mapping[Any, Any]")
                    "description"
                ] = "__REDACTED__"

        # apply change by creating new (frozen) data model
        log.info(
            "Bill Status Update",  # used as an event in DD. do not change lightly.
            bill_id=str(bill.id),
            bill_uuid=str(bill.uuid),
            bill_payor_id=str(bill.payor_id),
            bill_payor_type=bill.payor_type,
            bill_amount=bill.amount,
            replacement_data=replacement_data,
            bill_updated_bill_status=bill.status,
            error_type=error_type,
            record_body=record_body_to_log,
        )
        return dataclasses.replace(bill, **replacement_data)  # type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, Union[str, datetime, BillStatus, None]]"; expected "UUID" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, Union[str, datetime, BillStatus, None]]"; expected "int" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, Union[str, datetime, BillStatus, None]]"; expected "Optional[int]" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, Union[str, datetime, BillStatus, None]]"; expected "Optional[str]" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, Union[str, datetime, BillStatus, None]]"; expected "PayorType" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, Union[str, datetime, BillStatus, None]]"; expected "BillStatus" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, Union[str, datetime, BillStatus, None]]"; expected "PaymentMethod" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, Union[str, datetime, BillStatus, None]]"; expected "Optional[PaymentMethodType]" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, Union[str, datetime, BillStatus, None]]"; expected "Optional[datetime]" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, Union[str, datetime, BillStatus, None]]"; expected "Optional[CardFunding]" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, Union[str, datetime, BillStatus, None]]"; expected "str" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, Union[str, datetime, BillStatus, None]]"; expected "bool"

    def _charge_or_transfer_bill(
        self,
        bill: models.Bill,
        attempt_count: int,
        initiated_by: str = None,  # type: ignore[assignment] # Incompatible default for argument "initiated_by" (default has type "None", argument has type "str")
        headers: Mapping[str, str] = None,  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
    ) -> Bill:
        customer_id = payments_customer_id(bill.payor_id, bill.payor_type)
        if customer_id is None:
            # make sure the bill is in processing before you fail it
            bill = self._update_bill_status(bill, BillStatus.PROCESSING)
            self._update_bill_add_bpr_and_commit(
                bill=bill,
                new_bill_status=BillStatus.FAILED,
                record_type="billing_service_workflow",
                record_body={
                    "error": f"User: {bill.payor_id} not configured for direct payments"
                },
                transaction_id=None,
                error_type=OTHER_MAVEN,
            )
            raise errors.MissingPaymentGatewayInformation
        transaction_payload = self._create_transaction_payload(
            bill, attempt_count, initiated_by, customer_id  # type: ignore[arg-type] # Argument 3 to "_create_transaction_payload" of "BillingService" has incompatible type "Optional[str]"; expected "str"
        )
        processing_bill = self._process_bill_gateway_transaction(
            bill, transaction_payload, headers=headers
        )
        return processing_bill

    def _create_transaction_payload(
        self,
        bill: Bill,
        attempt_count: int,
        initiated_by: str,
        customer_id: uuid.UUID,
    ) -> TransactionPayload:
        metadata_payload = self._create_transaction_meta_data_payload(
            attempt_count, bill, initiated_by
        )
        if bill.payor_type == PayorType.CLINIC:
            transaction_payload = self.payment_gateway_client.create_transfer_payload(
                amount=bill.amount,
                recipient_id=customer_id,
                metadata=metadata_payload,
                description=self._create_transaction_description(bill),
            )
        else:
            transaction_payload = self.payment_gateway_client.create_charge_payload(
                amount=bill.amount + bill.last_calculated_fee,
                customer_id=customer_id,
                metadata=metadata_payload,
                payment_method_id=bill.payment_method_id or "",
            )
        return transaction_payload

    def _refund_or_reverse_transfer_bill(
        self,
        refund_or_reverse_transfer_bill: Bill,
        attempt_count: int,
        initiated_by: str = None,  # type: ignore[assignment] # Incompatible default for argument "initiated_by" (default has type "None", argument has type "str")
        headers: Mapping[str, str] | None = None,
    ) -> Bill:
        # first check if we stashed the linkage on the BPR:
        (
            linked_bill,
            linked_trans,
        ) = self._compute_linked_bill_and_bpr(refund_or_reverse_transfer_bill)
        # If we did not, then try to figure it out otherwise.
        if not linked_bill:
            (
                linked_bill,
                linked_trans,
            ) = self.compute_linked_paid_or_new_bill_and_trans_for_refund_or_transfer_reverse(
                refund_or_reverse_transfer_bill
            )

        to_return = self.set_new_refund_or_reverse_bill_to_processing(
            refund_or_reverse_transfer_bill=refund_or_reverse_transfer_bill,
            linked_bill=linked_bill,  # type: ignore[arg-type] # Argument "linked_bill" to "set_new_refund_or_reverse_bill_to_processing" of "BillingService" has incompatible type "Optional[Bill]"; expected "Bill"
            linked_bill_pr=linked_trans,
            attempt_count=attempt_count,
            initiated_by=initiated_by,  # type: ignore[arg-type] # Argument "initiated_by" to "set_new_refund_or_reverse_bill_to_processing" of "BillingService" has incompatible type "Optional[str]"; expected "str"
            headers=headers,
        )
        return to_return

    def set_new_refund_or_reverse_bill_to_processing(
        self,
        refund_or_reverse_transfer_bill: Bill,
        linked_bill: Bill,
        linked_bill_pr: BillProcessingRecord | None,
        attempt_count: int,
        initiated_by: str = "",
        record_type: ProcessingRecordTypeT = "billing_service_workflow",
        headers: Mapping[str, str] | None = None,
    ) -> Bill:
        if not linked_bill:
            refund_or_reverse_transfer_bill = self._update_bill_status(
                refund_or_reverse_transfer_bill, BillStatus.PROCESSING
            )
            self._update_bill_add_bpr_and_commit(
                bill=refund_or_reverse_transfer_bill,
                new_bill_status=BillStatus.FAILED,
                record_type=record_type,
                record_body={
                    "error": f"Unable to find linked bill for {refund_or_reverse_transfer_bill.uuid}"
                },
                transaction_id=None,
                error_type=OTHER_MAVEN,
            )
            log.warning(
                "Attempted a refund or reverse transfer but unable to find a bill.",
                bill_id=str(refund_or_reverse_transfer_bill.id),
                bill_uuid=str(refund_or_reverse_transfer_bill.uuid),
                bill_amount=refund_or_reverse_transfer_bill.amount,
                bill_procedure_id=str(refund_or_reverse_transfer_bill.procedure_id),
                bill_cost_breakdown_id=str(
                    refund_or_reverse_transfer_bill.cost_breakdown_id
                ),
                record_type=record_type,
            )
            raise errors.MissingLinkedChargeInformation

        log.info(
            "Attempted a refund or reverse transfer.",
            linked_bill_id=str(linked_bill.id),
            linked_bill_uuid=str(linked_bill.uuid),
            linked_bill_amount=linked_bill.amount,
            linked_bpr_id=str(linked_bill_pr.id) if linked_bill_pr else "",
            linked_bpr_transaction_id=(
                str(linked_bill_pr.transaction_id) if linked_bill_pr else ""
            ),
            linked_bpr_status=linked_bill_pr.bill_status if linked_bill_pr else "",
            bill_id=str(refund_or_reverse_transfer_bill.id),
            bill_uuid=str(refund_or_reverse_transfer_bill.uuid),
            bill_amount=refund_or_reverse_transfer_bill.amount,
            bill_procedure_id=str(refund_or_reverse_transfer_bill.procedure_id),
            bill_cost_breakdown_id=str(
                refund_or_reverse_transfer_bill.cost_breakdown_id
            ),
            record_type=record_type,
        )

        if linked_bill.status in {BillStatus.NEW, BillStatus.FAILED}:
            to_return = self._handle_refund_as_bill_cancellation(
                linked_bill, refund_or_reverse_transfer_bill, record_type, headers
            )
            log.info(
                "Cancellation/Rebook Bill",
                to_return_bill_id=str(to_return.id),
                to_return_bill_uuid=str(to_return.uuid),
            )
        else:
            # and this
            to_return = self._handle_refund_or_reverse_transfer_bill(
                attempt_count=attempt_count,
                initiated_by=initiated_by,
                linked_bill=linked_bill,
                linked_charge_trans=linked_bill_pr,  # type: ignore[arg-type] # Argument "linked_charge_trans" to "_handle_refund_or_reverse_transfer_bill" of "BillingService" has incompatible type "Optional[BillProcessingRecord]"; expected "BillProcessingRecord"
                refund_or_reverse_transfer_bill=refund_or_reverse_transfer_bill,
                headers=headers,
                record_type=record_type,
            )
            log.info("Refund or reverse transfer Bill", bill_id=to_return.id)
        log.info(
            "Refund/Reverse Transfer Bill Processed.",
            bill_id=str(refund_or_reverse_transfer_bill.id),
            bill_uuid=str(refund_or_reverse_transfer_bill.uuid),
            bill_amount=refund_or_reverse_transfer_bill.amount,
            bill_procedure_id=str(refund_or_reverse_transfer_bill.procedure_id),
            bill_cost_breakdown_id=str(
                refund_or_reverse_transfer_bill.cost_breakdown_id
            ),
            returned_bill_id=str(to_return.id),
            returned_bill_uuid=str(to_return.uuid),
            returned_bill_status=str(to_return.status),
            record_type=record_type,
        )
        return to_return

    def compute_all_linked_paid_or_new_bill_and_trans_for_procedure(
        self, procedure_id: int
    ) -> list[tuple[models.Bill, models.BillProcessingRecord | None]]:
        # first get the paid bills linked to this bill in  order of creation date
        paid_and_new_bills = self.bill_repo.get_by_procedure(
            procedure_ids=[procedure_id],
            status=[BillStatus.PAID, BillStatus.NEW],
        )

        to_return = [
            (bill, None) for bill in paid_and_new_bills if bill.status == BillStatus.NEW
        ]
        paid_bill_ids_dict = {
            bill.id: bill
            for bill in paid_and_new_bills
            if bill.status == BillStatus.PAID
        }
        # this will filter out paid bills with REFUNDED bprs
        paid_bill_id_and_bprs = self.bill_processing_record_repo.get_latest_records_with_specified_statuses_for_bill_ids(
            list(paid_bill_ids_dict.keys()), [BillStatus.PAID]  # type: ignore[arg-type] # Argument 1 to "list" has incompatible type "dict_keys[Optional[int], Bill]"; expected "Iterable[int]"
        )
        paid_bill_and_bprs = [
            (paid_bill_ids_dict[bill_id], bpr)
            for bill_id, bpr in paid_bill_id_and_bprs.items()
        ]
        to_return = to_return + paid_bill_and_bprs

        return to_return  # type: ignore[return-value] # Incompatible return value type (got "List[Tuple[Bill, None]]", expected "List[Tuple[Bill, Optional[BillProcessingRecord]]]")

    def _handle_refund_as_bill_cancellation(
        self,
        linked_bill: Bill,
        refund_bill: Bill,
        record_type: ProcessingRecordTypeT,
        headers: Mapping[str, str] | None = None,
    ) -> Bill:
        log.info(
            "Handling refund as bill cancellation",
            linked_bill_id=str(linked_bill.id),
            linked_bill_uuid=str(linked_bill.uuid),
            refund_bill_id=str(refund_bill.id),
            refund_bill_uuid=str(refund_bill.uuid),
            linked_bill_amt=linked_bill.amount,
            refund_bill_amt=refund_bill.amount,
        )
        is_estimate = (
            True
            if refund_bill.payor_type == PayorType.MEMBER
            and _get_treatment_proc_dict(input_bill=refund_bill)["status"].value  # type: ignore[index] # Value of type "Optional[Dict[Any, Any]]" is not indexable
            == "SCHEDULED"
            else False
        )
        delta_bill = self.create_bill(
            payor_type=linked_bill.payor_type,
            amount=(linked_bill.amount - abs(refund_bill.amount)),
            label=linked_bill.label,  # type: ignore[arg-type] # Argument "label" to "create_bill" of "BillingService" has incompatible type "Optional[str]"; expected "str"
            payor_id=linked_bill.payor_id,
            treatment_procedure_id=linked_bill.procedure_id,
            cost_breakdown_id=refund_bill.cost_breakdown_id,
            payment_method=linked_bill.payment_method,
            payment_method_label=linked_bill.payment_method_label,  # type: ignore[arg-type] # Argument "payment_method_label" to "create_bill" of "BillingService" has incompatible type "Optional[str]"; expected "str"
            headers=headers,  # type: ignore[arg-type] # Argument "headers" to "create_bill" of "BillingService" has incompatible type "Optional[Mapping[str, str]]"; expected "Mapping[str, str]"
            is_ephemeral=is_estimate,
        )
        final_cancelled_bill = self.cancel_bill(
            linked_bill, refund_bill, delta_bill, record_type
        )
        to_return = delta_bill if delta_bill.amount else final_cancelled_bill
        log.info(
            "Bill cancelled",
            final_cancelled_bill_id=str(final_cancelled_bill.id),
            final_cancelled_bill_uuid=str(final_cancelled_bill.uuid),
            refund_bill_id=str(refund_bill.id),
            refund_bill_uuid=str(refund_bill.uuid),
            delta_bill_id=str(delta_bill.id),
            delta_bill_uuid=str(delta_bill.uuid),
            delta_bill_amt=delta_bill.amount,
            to_return_bill_id=str(to_return.id),
        )
        return to_return

    def _handle_refund_or_reverse_transfer_bill(
        self,
        attempt_count: int,
        initiated_by: str,
        linked_bill: Bill,
        linked_charge_trans: BillProcessingRecord,
        refund_or_reverse_transfer_bill: Bill,
        headers: Mapping[str, str] | None = None,
        record_type: ProcessingRecordTypeT = "billing_service_workflow",
    ) -> Bill:
        can_process_refund = (
            refund_or_reverse_transfer_bill.payor_type != PayorType.EMPLOYER
            or can_employer_bill_be_processed(refund_or_reverse_transfer_bill)
        )
        log.info(
            "Can bill refund be processed?",
            linked_bill_id=str(linked_bill.id),
            refund_or_reverse_transfer_bill_id=str(refund_or_reverse_transfer_bill.id),
            can_process_refund=can_process_refund,
            linked_bill_payor_type=str(linked_bill.payor_type),
            message=(
                "Bill refund attempted."
                if can_process_refund
                else "Bill refund skipped."
            ),
        )
        if not can_process_refund:
            return refund_or_reverse_transfer_bill

        metadata_payload = self._create_transaction_meta_data_payload(
            attempt_count=attempt_count,
            bill=refund_or_reverse_transfer_bill,
            initiated_by=initiated_by,
        )
        if refund_or_reverse_transfer_bill.payor_type in {
            PayorType.MEMBER,
            PayorType.EMPLOYER,
        }:
            transaction_payload = self.payment_gateway_client.create_refund_payload(
                amount=abs(
                    refund_or_reverse_transfer_bill.amount
                    + refund_or_reverse_transfer_bill.last_calculated_fee
                ),
                transaction_id=linked_charge_trans.transaction_id,  # type: ignore[arg-type] # Argument "transaction_id" to "create_refund_payload" of "PaymentsGatewayClient" has incompatible type "Optional[UUID]"; expected "UUID"
                metadata=metadata_payload,
            )
        elif refund_or_reverse_transfer_bill.payor_type == PayorType.CLINIC:
            transaction_payload = self.payment_gateway_client.create_transfer_reverse_payload(
                amount=abs(
                    refund_or_reverse_transfer_bill.amount
                    + refund_or_reverse_transfer_bill.last_calculated_fee
                ),
                transaction_id=linked_charge_trans.transaction_id,  # type: ignore[arg-type] # Argument "transaction_id" to "create_transfer_reverse_payload" of "PaymentsGatewayClient" has incompatible type "Optional[UUID]"; expected "UUID"
                metadata=metadata_payload,
            )
        else:
            log.error(
                "Invalid refund payer type, must be either member, employer, or clinic.",
                bill_id=refund_or_reverse_transfer_bill.id,
                bill_payer_type=refund_or_reverse_transfer_bill.payor_type,
            )
            raise errors.InvalidRefundBillPayerType(
                "Invalid refund payer type, must be either member, employer or clinic."
            )
        self._add_bill_processing_record(
            record_type=record_type,
            bill=linked_bill,
            body={REFUND_BILL: refund_or_reverse_transfer_bill.id},
            transaction_id=linked_charge_trans.transaction_id,
            bill_status_override=BillStatus.REFUNDED,
        )
        self.session.commit()
        self._handle_refund_notification(linked_bill, refund_or_reverse_transfer_bill)
        processing_bill = self._process_bill_gateway_transaction(
            bill=refund_or_reverse_transfer_bill,
            transaction_payload=transaction_payload,
            headers=headers,  # type: ignore[arg-type] # Argument "headers" to "_process_bill_gateway_transaction" of "BillingService" has incompatible type "Optional[Mapping[str, str]]"; expected "Mapping[str, str]"
        )
        return processing_bill

    def _handle_refund_notification(self, linked_bill: Bill, refund_bill: Bill) -> None:
        try:
            if linked_bill.payor_type != PayorType.MEMBER:
                log.info(
                    "Not sending refund notification for non member.",
                    payor_id=str(linked_bill.payor_id),
                    payor_type=f"{linked_bill.payor_type}",
                )
                return
            if is_amount_too_small_for_payment_gateway(
                refund_bill.amount, self._auto_process_max_amount
            ):
                log.info(
                    "Not sending refund notification for a bill that is too small to be processed by the payment "
                    "gateway.",
                    refund_bill_id=str(refund_bill.id),
                    refund_bill_uuid=str(refund_bill.uuid),
                    refund_bill_payor_id=str(refund_bill.payor_id),
                    refund_bill_payor_type=f"{refund_bill.payor_type}",
                    refund_bill_amount=f"{refund_bill.amount}",
                )
                return
            event_name = "mmb_payment_adjusted_refund"
            cb = get_cost_breakdown_as_dict_from_id(linked_bill.cost_breakdown_id)
            event_properties = {
                "benefit_id": get_benefit_id_from_wallet_id(refund_bill.payor_id),
                "payment_amount": f"${cb.get('total_member_responsibility', 0) / 100:,.2f}",
                "payment_method_type": (
                    refund_bill.payment_method_type.value
                    if refund_bill.payment_method_type
                    else ""
                ),
                "payment_method_last4": (
                    refund_bill.payment_method_label
                    if refund_bill.payment_method_label
                    else ""
                ),
                "original_payment_amount": f"${(linked_bill.amount + linked_bill.last_calculated_fee) / 100:,.2f}",
                "refund_amount": f"${abs(refund_bill.amount + refund_bill.last_calculated_fee) / 100:,.2f}",
                "refund_date": refund_bill.created_at.isoformat(  # type: ignore[union-attr] # Item "None" of "Optional[datetime]" has no attribute "isoformat"
                    "T", "milliseconds"
                ).replace(
                    ".000", ":000Z"
                ),
            }
            send_notification_event(
                user_id=str(refund_bill.payor_id),
                user_id_type="PAYOR_ID",
                user_type="MEMBER",
                event_source_system="BILLING",
                event_name=event_name,
                event_properties=event_properties,
            )
        except Exception:
            # dont let notification failures break bill processing.
            log.error(
                "Unable to send notification for:",
                refund_bill_uuid=str(refund_bill.uuid),
                linked_bill_uuid=str(linked_bill.uuid),
                reason=format_exc(),
            )

    @staticmethod
    def _create_transaction_meta_data_payload(attempt_count, bill, initiated_by):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        metadata_payload = {
            # payments_id metadata will be added by payments gateway service, indicates transaction id
            BillMetadataKeys.SOURCE_TYPE.value: "TreatmentProcedure",
            BillMetadataKeys.SOURCE_ID.value: str(bill.procedure_id),
            BillMetadataKeys.BILL_UUID.value: str(bill.uuid),
            BillMetadataKeys.COPAY_PASSTHROUGH.value: f"{bill.amount / 100:.2f}",
            BillMetadataKeys.RECOUPED_FEE.value: f"{bill.last_calculated_fee / 100:.2f}",
            BillMetadataKeys.INITIATED_BY.value: initiated_by
            or "direct_payment.billing.billing_service",
            BillMetadataKeys.BILL_ATTEMPT.value: attempt_count,
            BillMetadataKeys.PAYER_TYPE.value: bill.payor_type.value.lower(),
        }
        return metadata_payload

    @staticmethod
    def _create_transaction_description(bill: Bill) -> str:
        to_return = ""
        if bill.payor_type == PayorType.CLINIC:
            treatment_proc = get_treatment_procedure_as_dict_from_id(bill.procedure_id)
            uuid_ = treatment_proc.get("uuid", "")
            wallet_id = treatment_proc["reimbursement_wallet_id"]
            member_id = treatment_proc["member_id"]
            benefit_id = get_benefit_id(member_id=member_id)
            end_date = treatment_proc.get("end_date")
            end_date_str = end_date.strftime("%b %d, %Y") if end_date else ""
            member_names = get_first_and_last_name_from_user_id(member_id)
            member_name = f"{member_names[0]} {member_names[1]}"
            to_return = (
                f"Payment from Maven Clinic for Member: {member_name}, Benefit ID: {benefit_id}, Procedure ID: "
                f"{uuid_}, Procedure End Date: {end_date_str}"
            )
            log.info(
                "Created transfer transaction description.",
                bill_uuid=str(bill.uuid),
                wallet_id=str(wallet_id),
            )
        return to_return

    def _process_bill_gateway_transaction(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self, bill: Bill, transaction_payload, headers: Mapping[str, str] = None  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
    ):
        if bill.is_ephemeral:
            log.warning(
                "Blocking ephemeral bill from payment gateway submission.",
                bill_id=str(bill.id),
                bill_payor_id=str(bill.payor_id),
                bill_payor_type=f"{bill.payor_type}",
                bill_amount=bill.amount,
            )
            raise InvalidEphemeralBillOperationError(
                "Ephemeral bills can never be submitted to the payment gateway."
            )

        if bill.amount > self._auto_process_max_amount:
            tp_list = list(
                get_treatment_procedures_as_dicts_from_ids([bill.procedure_id]).values()
            )
            treatment_procedure = tp_list[0] if tp_list else None
            if treatment_procedure and treatment_procedure["status"].value not in [
                TreatmentProcedureStatus.COMPLETED.value,
                TreatmentProcedureStatus.PARTIALLY_COMPLETED.value,
                TreatmentProcedureStatus.SCHEDULED.value,
            ]:
                log.warning(
                    "Only bills with completed, partially completed, or scheduled treatment procedure status can be submitted to the payment gateway.",
                    bill_id=str(bill.id),
                    bill_payor_id=str(bill.payor_id),
                    bill_payor_type=f"{bill.payor_type}",
                    bill_amount=bill.amount,
                    treatment_procedure_id=bill.procedure_id,
                    treatment_procedure_user_id=str(treatment_procedure["member_id"]),
                    treatment_procedure_status=treatment_procedure["status"].value,
                )
                raise InvalidBillTreatmentProcedureCancelledError(
                    "Only bills with completed, partially completed, or scheduled treatment procedure status can be submitted to the payment gateway."
                )

        processing_bill = self._update_bill_add_bpr_and_commit(
            bill=bill,
            new_bill_status=models.BillStatus.PROCESSING,
            record_type="payment_gateway_request",
            record_body=transaction_payload.as_dict(),
            transaction_id=None,
        )
        trans_type = (
            transaction_payload.transaction_data.transaction_type
            if transaction_payload and transaction_payload.transaction_data
            else ""
        )
        try:
            log.info(
                f"{trans_type} Transaction Initiated",
                bill_id=str(processing_bill.id),
                bill_uuid=str(processing_bill.uuid),
                bill_payor_id=str(bill.payor_id),
                transaction_type=trans_type,
            )
            transaction = self.payment_gateway_client.create_transaction(
                transaction_payload=transaction_payload, headers=headers
            )
            self._add_bill_processing_record(
                record_type="payment_gateway_response",
                bill=processing_bill,
                body=dataclasses.asdict(transaction),
                transaction_id=transaction.transaction_id,
            )
            self.session.commit()
        except PaymentsGatewayException as e:
            gateway_error = self.payment_gateway_exception_to_gateway_error_type(e)
            log.error(
                f"{trans_type} Transaction Failed",
                bill_id=str(processing_bill.id),
                bill_uuid=str(processing_bill.uuid),
                bill_payor_id=str(bill.payor_id),
                gateway_error=gateway_error,
                transaction_type=trans_type,
            )
            content = (
                e.response.content.decode("utf-8", errors="ignore")
                if e.response is not None and e.response.content is not None
                else ""
            )
            _ = self._update_bill_add_bpr_and_commit(
                bill=processing_bill,
                new_bill_status=models.BillStatus.FAILED,
                record_type="payment_gateway_response",
                record_body={
                    "gateway_error": gateway_error,
                    "gateway_response": content,
                },
                transaction_id=None,
                error_type=OTHER_MAVEN,
            )
            raise e
        log.info(
            f"{trans_type} Transaction Completed",
            bill_id=str(processing_bill.id),
            bill_uuid=str(processing_bill.uuid),
            bill_payor_id=str(bill.payor_id),
            transaction_type=trans_type,
        )
        return processing_bill

    def _update_bill_add_bpr_and_commit(
        self,
        bill: Bill,
        new_bill_status: BillStatus,
        record_type: models.ProcessingRecordTypeT,
        record_body: dict,
        transaction_id: uuid.UUID | None,
        error_type: str | None = None,
    ) -> Bill:
        to_return = self._update_bill_and_add_bpr_without_commit(
            bill, new_bill_status, record_type, record_body, transaction_id, error_type
        )
        self.session.commit()
        return to_return

    def _update_bill_and_add_bpr_without_commit(
        self,
        bill: Bill,
        new_bill_status: BillStatus,
        record_type: models.ProcessingRecordTypeT,
        record_body: dict,
        transaction_id: uuid.UUID | None,
        error_type: str | None = None,
    ) -> Bill:
        updated_bill = self._update_bill_status(
            bill, new_bill_status, error_type, record_body
        )
        to_return = self.bill_repo.update(instance=updated_bill)
        self._add_bill_processing_record(
            record_type=record_type,
            bill=to_return,
            body=record_body,
            transaction_id=transaction_id,
        )
        return to_return

    def _add_bill_processing_record(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        record_type: ProcessingRecordTypeT,
        bill: models.Bill,
        body: dict,
        transaction_id: uuid.UUID | None,
        bill_status_override: BillStatus | None = None,  # added to support safe refunds
    ):
        record = models.BillProcessingRecord(
            processing_record_type=record_type,
            body=body,
            bill_id=bill.id,  # type: ignore[arg-type] # Argument "bill_id" to "BillProcessingRecord" has incompatible type "Optional[int]"; expected "int"
            bill_status=(
                bill_status_override.value  # type: ignore[arg-type] # Argument "bill_status" to "BillProcessingRecord" has incompatible type "Union[str, str, str, str, str, str]"; expected "BillStatus"
                if bill_status_override
                else bill.status.value
            ),
            transaction_id=transaction_id,
            created_at=datetime.datetime.now(),  # noqa
        )
        to_return = self.bill_processing_record_repo.create(instance=record)
        return to_return

    @staticmethod
    def payment_gateway_exception_to_gateway_error_type(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        gateway_exception: PaymentsGatewayException,
    ):
        return GATEWAY_EXCEPTION_CODE_MAPPING.get(
            gateway_exception.code, DEFAULT_GATEWAY_ERROR_RESPONSE
        )

    def compute_new_member_bills_to_process(
        self,
        start_date: datetime.date | None,
        end_date: datetime.date | None,
    ) -> list[Bill]:
        to_return = self._compute_new_member_bills_in_date_range(
            start_date, end_date, False
        )
        return to_return

    def compute_new_member_bills(
        self,
        start_date: datetime.date | None,
        end_date: datetime.date | None,
    ) -> list[Bill]:
        to_return = self._compute_new_member_bills_in_date_range(
            start_date, end_date, True
        )
        return to_return

    def _compute_new_member_bills_in_date_range(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        start_date: datetime.date | None,
        end_date: datetime.date | None,
        ignore_refunds: bool,
    ):
        bills = self.bill_repo.get_by_payor_types_statuses_date_range(
            [PayorType.MEMBER],
            [BillStatus.NEW],
            start_date,
            end_date,
        )
        log.info("Found bill(s) in NEW status.", bill_cnt=len(bills))
        if ignore_refunds:
            log.info("Ignoring refunds.")
            to_return = bills
        else:
            refund_payor_ids = self.bill_repo.get_all_payor_ids_with_active_refunds()
            log.info(
                "Found distinct payor_ids with pending refunds",
                payor_id_cnt=len(refund_payor_ids),
            )
            to_return = [
                bill
                for bill in bills
                if bill.amount <= 0 or bill.payor_id not in refund_payor_ids
            ]
        start_date_str = start_date.strftime("%Y-%m-%d") if start_date else "<None>"
        end_date_str = end_date.strftime("%Y-%m-%d") if end_date else "<None>"
        log.info(
            "After excluding payor_ids with pending refunds, NEW bills are:",
            bills_in_range_cnt=(len(to_return)),
            start_date=start_date_str,
            end_date=end_date_str,
        )

        return to_return

    def compute_linked_paid_or_new_bill_and_trans_for_refund_or_transfer_reverse(
        self, input_bill: Bill
    ) -> tuple[models.Bill | None, models.BillProcessingRecord | None]:
        log.info(
            "Looking for refund candidate for the input bill",
            input_bill_id=str(input_bill.id),
            input_bill_uuid=str(input_bill.uuid),
            input_bill_amount=input_bill.amount,
            input_bill_payor_id=str(input_bill.payor_id),
            input_bill_payor_type=input_bill.payor_type.value,
        )
        # first get the paid bills linked to this bill in  order of creation date
        candidate_bills = self.bill_repo.get_bills_by_procedure_id_payor_type_status(
            procedure_id=input_bill.procedure_id,
            payor_type=input_bill.payor_type,
            statuses=[BillStatus.NEW, BillStatus.PAID, BillStatus.FAILED],
        )
        # bills that are large enough to refund
        bill_dict = {
            bill.id: bill
            for bill in candidate_bills
            if bill.amount >= abs(input_bill.amount)
        }

        # Bias towards picking a NEW/FAILED bill as a cancellation candidate to avoid fees.
        if new_bills := [
            b
            for b in bill_dict.values()
            if b.status in {BillStatus.NEW, BillStatus.FAILED}
        ]:
            # pick the latest NEW bill. New bills do not have BPRs
            to_return = (new_bills[-1], None)
        else:
            latest_record = self.bill_processing_record_repo.get_latest_bill_processing_record_if_paid(
                list(bill_dict.keys())  # type: ignore[arg-type] # Argument 1 to "list" has incompatible type "dict_keys[Optional[int], Bill]"; expected "Iterable[int]"
            )
            to_return = (
                ((bill_dict[latest_record.bill_id]), latest_record)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Tuple[Optional[Bill], Optional[BillProcessingRecord]]", variable has type "Tuple[Bill, None]")
                if latest_record
                else (None, None)
            )

        if candidate_bill := to_return[0]:
            log.info(
                "Found a refund candidate for the input bill",
                input_bill_id=str(input_bill.id),
                candidate_bill_id=str(candidate_bill.id),
                candidate_bill_uuid=str(candidate_bill.uuid),
                candidate_bill_amount=candidate_bill.amount,
                candidate_bill_payor_id=str(candidate_bill.payor_id),
                candidate_bill_payor_type=candidate_bill.payor_type.value,
                candidate_bill_payor_status=candidate_bill.status.value,
            )
        else:
            log.info(
                "Unable to find a refund candidate for the input bill",
                input_bill_id=str(input_bill.id),
            )
        return to_return

    def _compute_linked_bill_and_bpr(
        self, input_bill: Bill
    ) -> tuple[models.Bill | None, models.BillProcessingRecord | None]:
        # first, check if this bill already had a linked bill and transaction tagged.
        to_return = None, None
        bprs = self.bill_processing_record_repo.get_bill_processing_records(
            [input_bill.id]  # type: ignore[list-item] # List item 0 has incompatible type "Optional[int]"; expected "int"
        )
        for bpr in bprs:
            if not bpr:
                continue

            linked_bill_id = None
            if bpr.bill_status == BillStatus.NEW.value:
                linked_bill_id = bpr.body.get(TO_REFUND_BILL)
            elif bpr.bill_status == BillStatus.REFUNDED.value:
                linked_bill_id = bpr.body.get(REFUND_BILL)

            if linked_bill_id:
                linked_bill = self.bill_repo.get_by_ids([linked_bill_id])[0]
                linked_bpr = (
                    self.bill_processing_record_repo.get_bill_processing_records(
                        [linked_bill_id]
                    )
                )[-1]
                to_return = linked_bill, linked_bpr
        return to_return

    def process_payment_gateway_event_message(self, message_dict: dict) -> None:
        """
        This function will handle the messages sent from the payment gateway to the billing service.As callers of this
        function(or its exposed i/f) are expected to be fire and forget, it will return None. Will be exposed via REST
        or used by the subscription client
        Unknown message types Errors will be logged for external handling and thrown.
        :param message_dict: Dictionary
        :type Dict that can be converted into a PaymentGatewayEventMessage object
        :return: None
        :rtype: None
        """
        try:
            message = PaymentGatewayEventMessage.create_from_dict(message_dict)
            event_type = message.event_type
            self._safe_log(message_dict, event_type)
            log.info("Processing payment gateway event.", event_type=event_type)
            if event_type == "billing_event":
                self._process_payment_gateway_billing_event(message)
            elif event_type == "payment_method_attach_event":
                self._process_payment_method_attach_event(message)
        except BillingServicePGMessageProcessingError as ex:
            log.error(
                "Unable to process payment gateway event message", reasons=ex.message
            )
            raise ex

    @staticmethod
    def _safe_log(message_dict: dict, event_type: EventTypeT):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            if event_type == "billing_event":
                # PII in billing_event events.
                if (
                    "message_payload" in message_dict
                    and isinstance(message_dict["message_payload"], Mapping)
                    and "transaction_data" in message_dict["message_payload"]
                    and isinstance(
                        message_dict["message_payload"]["transaction_data"],
                        Mapping,
                    )
                    and "description"
                    in message_dict["message_payload"]["transaction_data"]
                ):
                    message_dict_to_log = copy.deepcopy(message_dict)
                    message_dict_to_log["message_payload"]["transaction_data"][
                        "description"
                    ] = "__REDACTED__"
                else:
                    message_dict_to_log = message_dict
                log.info(
                    "Received billing_event from payment gateway.",
                    message=message_dict_to_log,
                )
            elif event_type == "payment_method_attach_event":
                # no PII in attach events
                log.info(
                    "Received payment_method_attach_event from payment gateway.",
                    message=message_dict,
                )
        except Exception:
            log.warning(
                "Unable to safely log payment gateway message.", reason=format_exc()
            )

    def _process_payment_gateway_billing_event(
        self, message: PaymentGatewayEventMessage
    ) -> None:
        """
        :param message: Message object containing the transaction associated with the bill on the payment side.
        The transaction UUID will be used to tie this message to a bill in the Bill table. If this tie up fails, the
        metadata will be examined to find a possible candidate. If this also fails, an error will be logged and thrown.
        :type PaymentGatewayEventMessage
        :return: None
        :rtype: None
        """

        transaction = self._get_transaction_from_message(message)
        decline_code, error_details = self._get_decline_code_and_detail(
            message, transaction.status
        )
        matching_bill = self._pick_bill_from_transaction(transaction)
        status = self._translate_transaction_status_to_bill_status(
            transaction.status, matching_bill  # type: ignore[arg-type] # Argument 2 to "_translate_transaction_status_to_bill_status" of "BillingService" has incompatible type "Optional[Bill]"; expected "Bill"
        )
        error_type = self._translate_decline_code_to_error_type(decline_code)  # type: ignore[arg-type] # Argument 1 to "_translate_decline_code_to_error_type" of "BillingService" has incompatible type "Optional[str]"; expected "str"
        updated_bill = self._update_bill_on_payment_gateway_event(
            matching_bill, status, message, transaction, error_type  # type: ignore[arg-type] # Argument 1 to "_update_bill_on_payment_gateway_event" of "BillingService" has incompatible type "Optional[Bill]"; expected "Bill"
        )
        self._perform_post_event_update_actions(updated_bill)
        self._perform_post_event_update_notifications(updated_bill)

    @staticmethod
    def _get_decline_code_and_detail(
        message: PaymentGatewayEventMessage, transaction_status: TransactionStatusT
    ) -> tuple[str | None, dict | None]:
        error_payload = message.error_payload
        error_msgs = []
        to_return = (None, None)
        if transaction_status == "failed":
            if error_payload:
                if not (decline_code := error_payload.get("decline_code", "").strip()):
                    error_msgs.append(
                        "Blank or missing decline_code in error_payload. Defaulting to unknown."
                    )
                    decline_code = "unknown"
                if not (error_details := error_payload.get("error_detail")):
                    error_msgs.append(
                        "Empty or missing error_details in error_payload. Defaulting to None."
                    )
                    error_details = None
                to_return = (decline_code, error_details)
            else:
                error_msgs.append(
                    "Empty or missing in error_payload in message. Defaulting to (unknown, None)."
                )
                to_return = ("unknown", None)  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Tuple[str, None]", variable has type "Tuple[None, None]")

        log.info(
            "Returning decline code and error details.",
            message_error_payload=message.error_payload,
            decline_code=to_return[0],
            error_details=to_return[1],
        )
        return to_return

    @staticmethod
    def _get_transaction_from_message(
        message: PaymentGatewayEventMessage,
    ) -> Transaction:
        message_payload = message.message_payload
        error_payload = message.error_payload
        try:
            to_return = Transaction.create_from_dict(message_payload)
        except (KeyError, TypeError) as ex:
            log.error(
                "Cannot create transaction object from message_payload.",
                reasons=ex.args,
            )
            raise errors.BillingServicePGMessageProcessingError(ex.args)
        if (to_return.status == "failed") ^ bool(error_payload):
            log.warning(
                "Status incompatible with error payload. ",
                transaction_id=to_return.transaction_id,
                transaction_status=to_return.status,
                error_payload=str(error_payload),
            )
        return to_return

    def _pick_bill_from_transaction(self, transaction: Transaction) -> Bill | None:
        transaction_id = transaction.transaction_id
        bill_ids = self.bill_processing_record_repo.get_bill_ids_from_transaction_id(
            transaction_id  # type: ignore[arg-type] # Argument 1 to "get_bill_ids_from_transaction_id" of "BillProcessingRecordRepository" has incompatible type "uuid.UUID"; expected "direct_payment.billing.repository.common.UUID"
        )
        error_msgs = []
        metadata = transaction.metadata

        if len(bill_ids) == 0:
            metadata_bill_uuid = metadata.get(BillMetadataKeys.BILL_UUID.value)
            log.warning(
                "Found 0 matching bills for transaction_id. Falling back to metadata bill uuid.",
                transaction_id=str(transaction_id),
                metadata_bill_uuid=metadata_bill_uuid,
            )
            to_return = self.get_bill_by_uuid(metadata_bill_uuid)  # type: ignore[arg-type] # Argument 1 to "get_bill_by_uuid" of "BillingService" has incompatible type "Optional[Any]"; expected "str"
            if not to_return:
                log.error(
                    "Unable to find a matching bill from metadata",
                    transaction_id=str(transaction_id),
                    metadata_bill_uuid=metadata_bill_uuid,
                )
                raise BillingServicePGMessageProcessingError(
                    [
                        f"Unable to find matching bill from metadata transaction_id={str(transaction_id)}, "
                        f"{metadata_bill_uuid=}"
                    ]
                )
        elif len(bill_ids) == 1:
            to_return = self.get_bill_by_id(bill_ids[0])
        else:
            log.error(
                "Found multiple bills for the transaction_id, this should never happen!",
                transaction_id=str(transaction_id),
                bill_ids=bill_ids,
            )
            raise BillingServicePGMessageProcessingError(
                [
                    f"Found multiple bills for transaction_id={str(transaction_id)}. This should never happen. "
                ]
            )
        if error_string := self._sanity_check_uuid(to_return, metadata):  # type: ignore[arg-type] # Argument 1 to "_sanity_check_uuid" of "BillingService" has incompatible type "Optional[Bill]"; expected "Bill"
            error_msgs.append(error_string)
        if error_string := self._sanity_check_amount(
            to_return, transaction.transaction_data  # type: ignore[arg-type] # Argument 1 to "_sanity_check_amount" of "BillingService" has incompatible type "Optional[Bill]"; expected "Bill"
        ):
            error_msgs.append(error_string)
        if error_msgs:
            raise BillingServicePGMessageProcessingError(error_msgs)

        log.info(
            "Found the bill corresponding to the supplied transaction_id.",
            transaction_id=str(transaction_id),
            bill_ids=str(to_return),
        )

        return to_return

    @staticmethod
    def _sanity_check_amount(bill: Bill, transaction_data: dict):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        to_return = ""
        bill_amount = abs(bill.amount) + abs(
            bill.last_calculated_fee  # type: ignore[arg-type] # Argument 1 to "abs" has incompatible type "Optional[int]"; expected "SupportsAbs[int]"
        )  # could be a refund
        transaction_amount = transaction_data.get("amount")
        if bill_amount != transaction_amount:
            log.error(
                "Sanity check failure - bill amount  mismatch",
                bill_amount=bill_amount,
                transaction_amount=transaction_amount,
            )
            to_return = f"Sanity check failure - amount mismatch {bill_amount=}, {transaction_amount=}"
        return to_return

    @staticmethod
    def _sanity_check_uuid(bill: Bill, metadata: dict):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        bill_uuid = str(bill.uuid)
        metadata_bill_uuid = metadata.get(BillMetadataKeys.BILL_UUID.value)
        to_return = ""
        if bill_uuid != metadata_bill_uuid:
            # or bill_amount != metadata_amount:
            log.error(
                "Sanity check failure - uuid mismatch",
                bill_uuid=bill_uuid,
                metadata_bill_uuid=metadata_bill_uuid,
            )
            to_return = f"Sanity check failure - bill uuid mismatch {bill_uuid=}, {metadata_bill_uuid=}"
        return to_return

    @staticmethod
    def _translate_transaction_status_to_bill_status(
        transaction_status: TransactionStatusT, bill: Bill
    ) -> BillStatus:
        if transaction_status == "completed":
            return BillStatus.PAID if bill.amount >= 0 else BillStatus.REFUNDED
        if transaction_status == "failed":
            return BillStatus.FAILED
        if transaction_status in ["pending", "processing"]:
            return BillStatus.PROCESSING
        raise BillingServicePGMessageProcessingError(
            f"Unrecognized transaction status: {transaction_status}"
        )

    @staticmethod
    def _translate_decline_code_to_error_type(decline_code: str) -> str | None:
        return (
            DECLINE_CODE_MAPPING.get(decline_code, OTHER_MAVEN)
            if decline_code
            else None
        )

    def _update_bill_on_payment_gateway_event(
        self,
        matching_bill: Bill,
        status: BillStatus,
        message: PaymentGatewayEventMessage,
        transaction: Transaction,
        error_type: str | None,
    ) -> Bill:
        try:
            to_return = self._update_bill_add_bpr_and_commit(
                bill=matching_bill,
                new_bill_status=status,
                record_type="payment_gateway_event",
                record_body={
                    "message_payload": message.message_payload,
                    "error_payload": message.error_payload,
                },
                transaction_id=transaction.transaction_id,
                error_type=error_type,
            )
            return to_return
        except errors.InvalidBillStatusChange as ex:
            log.error("Bill update failed.", reasons=ex.args[0])
            raise errors.BillingServicePGMessageProcessingError(ex.args)

    def _perform_post_event_update_actions(self, updated_bill: Bill) -> None:
        if (
            updated_bill.payor_type == PayorType.EMPLOYER
            and updated_bill.status == BillStatus.PAID
        ):
            from_employer_bill_create_clinic_bill_and_process.delay(
                emp_bill_id=updated_bill.id
            )

        if (
            updated_bill.payor_type == PayorType.CLINIC
            and updated_bill.status == BillStatus.REFUNDED
        ):
            self._process_clinic_reverse_transfer_event(updated_bill)

    def _process_clinic_reverse_transfer_event(self, clinic_bill):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # avoid circular import
        from direct_payment.billing.tasks.rq_job_create_bill import (
            from_clinic_reverse_transfer_bill_create_member_employer_bill_and_process,
        )

        clinic_bills = self.get_money_movement_bills_by_procedure_id_payor_type(
            procedure_id=clinic_bill.procedure_id,
            payor_type=PayorType.CLINIC,
        )
        clinic_bills = [
            bill
            for bill in clinic_bills
            if bill.status in {BillStatus.PAID, BillStatus.REFUNDED}
        ]
        # all clinic bills are already reverse transferred, then trigger refund for member and employer
        if sum(bill.amount for bill in clinic_bills) == 0:
            from_clinic_reverse_transfer_bill_create_member_employer_bill_and_process.delay(
                clinic_bill_id=clinic_bill.id
            )

    @staticmethod
    def _perform_post_event_update_notifications(bill: Bill) -> None:
        if bill.payor_type == PayorType.MEMBER and bill.status in {
            BillStatus.PAID,
            BillStatus.REFUNDED,
            BillStatus.FAILED,
        }:
            bill_amt_str = f"${abs(bill.amount + bill.last_calculated_fee) / 100:,.2f}"
            if bill.status == BillStatus.PAID:
                event_name = "mmb_payment_confirmed"
                event_properties = {
                    "benefit_id": get_benefit_id_from_wallet_id(bill.payor_id),
                    "payment_amount": bill_amt_str,
                    "payment_details_link": str(bill.uuid),
                    "payment_date": bill.paid_at.isoformat("T", "milliseconds").replace(  # type: ignore[union-attr] # Item "None" of "Optional[datetime]" has no attribute "isoformat"
                        ".000", ":000Z"
                    ),
                }
            elif bill.status == BillStatus.REFUNDED:
                event_name = "mmb_refund_confirmation"
                event_properties = {
                    "payment_details_link": str(bill.uuid),
                    "refund_amount": bill_amt_str,
                    "refund_date": bill.refunded_at.isoformat(  # type: ignore[union-attr] # Item "None" of "Optional[datetime]" has no attribute "isoformat"
                        "T", "milliseconds"
                    ).replace(
                        ".000", ":000Z"
                    ),
                }
            else:
                event_name = "mmb_payment_processing_error"
                event_properties = {
                    "payment_amount": bill_amt_str,
                    "payment_date": bill.failed_at.isoformat(  # type: ignore[union-attr] # Item "None" of "Optional[datetime]" has no attribute "isoformat"
                        "T", "milliseconds"
                    ).replace(
                        ".000", ":000Z"
                    ),
                }
            event_properties["payment_method_last4"] = bill.payment_method_label or ""
            event_properties["payment_method_type"] = (
                bill.payment_method_type.value if bill.payment_method_type else ""
            )

            send_notification_event.delay(
                user_id=str(bill.payor_id),
                user_id_type="PAYOR_ID",
                user_type="MEMBER",
                event_source_system="BILLING",
                event_name=event_name,
                event_properties=event_properties,
            )

    def _process_payment_method_attach_event(
        self, message: PaymentGatewayEventMessage
    ) -> None:
        error_msgs = []
        # This is a little funky; trying to log all parts of the message that are malformed.
        payor_id = None
        payor_type = None
        payment_method_package = None
        try:
            payments_id = self._get_payments_customer_id_from_message(message)
            log.info("Derived payments_id.", payments_id=payments_id)
            payor_id, payor_type = self._get_payor_id_and_type_from_payments_id(
                payments_id
            )
            log.info(
                "Derived payor_id and payor_type.",
                payor_id=payor_id,
                payor_type=payor_type,
            )
        except BillingServicePGMessageProcessingError as e:
            error_msgs.append(e.message)
        try:
            payment_method_package = self._get_payment_method_package(message)
            log.info(
                "Loaded payment_method_package.",
                payment_method_package=payment_method_package,
            )
        except BillingServicePGMessageProcessingError as e:
            error_msgs.append(e.message)
        if error_msgs:
            raise BillingServicePGMessageProcessingError(error_msgs)

        all_failed_bills = self._get_failed_bills_by_payor_id_and_type_for_auto_retry(
            payor_id,  # type: ignore[arg-type] # Argument 1 to "_get_failed_bills_by_payor_id_and_type" of "BillingService" has incompatible type "Optional[int]"; expected "int"
            payor_type,  # type: ignore[arg-type] # Argument 1 to "_get_failed_bills_by_payor_id_and_type" of "BillingService" has incompatible type "Optional[int]"; expected "int" #type: ignore[arg-type] # Argument 2 to "_get_failed_bills_by_payor_id_and_type" of "BillingService" has incompatible type "Optional[PayorType]"; expected "PayorType"
            [
                BillErrorTypes.INSUFFICIENT_FUNDS,
                BillErrorTypes.PAYMENT_METHOD_HAS_EXPIRED,
                BillErrorTypes.OTHER_MAVEN,
            ],
        )

        other_failed_bills = [
            b
            for b in all_failed_bills
            if b.error_type == BillErrorTypes.OTHER_MAVEN.value
        ]
        failed_bills = [
            b
            for b in all_failed_bills
            if b.error_type != BillErrorTypes.OTHER_MAVEN.value
        ]
        new_bills = self._get_new_bills_by_payor_id_and_type(payor_id, payor_type)  # type: ignore[arg-type] # Argument 1 to "_get_new_bills_by_payor_id_and_type" of "BillingService" has incompatible type "Optional[int]"; expected "int" #type: ignore[arg-type] # Argument 2 to "_get_new_bills_by_payor_id_and_type" of "BillingService" has incompatible type "Optional[PayorType]"; expected "PayorType"
        log.info(
            "Queried for new bills.",
            new_bills_cnt=(len(new_bills) if new_bills else 0),
        )
        updated_bill_ids = self._update_payment_data_on_bills_add_bprs_in_memory(
            payment_method_package or {},
            new_bills + failed_bills + other_failed_bills,
            message,
            "payment_gateway_event",
        )
        # commit here - in the calling function only if there were updates to commit
        if updated_bill_ids:
            self.session.commit()
            log.info(
                "Updated payment method info on bills and committed to DB.",
                payor_id=str(payor_id),
                payor_type=payor_type,
                failed_bills_cnt=len(failed_bills),
                other_failed_bills_cnt=len(other_failed_bills),
                new_bills_cnt=len(new_bills),
                updated_bill_ids=updated_bill_ids,
            )
            stats.increment(
                metric_name="direct_payment.billing.billing_service.BillingService.update_payment_method_on_bill",
                pod_name=stats.PodNames.BENEFITS_EXP,
                metric_value=len(updated_bill_ids),
            )

        # spawn out the job to actually retry the bills
        self._async_retry_bills([bill.id for bill in failed_bills])

    @staticmethod
    def _get_payments_customer_id_from_message(
        message: PaymentGatewayEventMessage,
    ) -> str:
        message_payload = message.message_payload
        if "customer_id" not in message_payload:
            raise BillingServicePGMessageProcessingError(
                ["customer_id not found in message message_payload."]
            )
        customer_id = message_payload["customer_id"]
        if customer_id is None or not customer_id.strip():
            raise BillingServicePGMessageProcessingError(
                ["customer_id is blank or missing in message_payload."]
            )
        try:
            _ = uuid.UUID(customer_id)  # to check if its a good uuid
            return customer_id
        except ValueError:
            raise BillingServicePGMessageProcessingError(
                [f"{customer_id=} is badly formed hexadecimal UUID string."]
            )

    @staticmethod
    def _get_payor_id_and_type_from_payments_id(
        payments_id: str,
    ) -> tuple[int, PayorType]:
        try:
            # TODO this is a dependency that should be excised on microservice migration
            return get_payor_id_from_payments_customer_or_recipient_id(payments_id)
        except ValueError as ve:
            raise BillingServicePGMessageProcessingError(ve.args)

    @staticmethod
    def _get_payment_method_package(
        message: PaymentGatewayEventMessage,
    ) -> dict[str, str]:
        message_payload = message.message_payload
        if "payment_method" not in message_payload:
            raise BillingServicePGMessageProcessingError(
                ["payment_method not found in the message_payload."]
            )
        payment_method = message_payload["payment_method"]
        if payment_method is None:
            raise BillingServicePGMessageProcessingError(
                ["payment_method was None in the message_payload."]
            )
        if not isinstance(payment_method, Mapping):
            raise BillingServicePGMessageProcessingError(
                ["payment_method does not implement Mapping."]
            )

        error_msgs = []
        to_return = {}
        required = ["payment_method_type", "last4", "payment_method_id"]
        optional = ["card_funding"]
        for key in required:
            if key not in payment_method:
                error_msgs.append(f"payment_method is missing key: {key}.")
            else:
                if (val := payment_method[key]) is None or not val.strip():
                    error_msgs.append(
                        f"value mapped to : {key} in payment_method is blank or None."
                    )
                else:
                    # TODO check if last4 has to be an int (leading 0's allowed)
                    if key == "last4" and len(last_4 := val.strip()) != 4:
                        error_msgs.append(
                            f"payment_method has {last_4=} which is not exactly 4 characters long."
                        )
                    else:
                        to_return[key] = val.strip()
        for key in optional:
            if key in payment_method.keys() and payment_method[key]:
                to_return[key] = payment_method.get(key, "").strip()
        if error_msgs:
            raise BillingServicePGMessageProcessingError(error_msgs)

        return to_return

    def _get_failed_bills_by_payor_id_and_type_for_auto_retry(
        self, payor_id: int, payor_type: PayorType, error_types: list[BillErrorTypes]
    ) -> list[Bill]:
        filtered_failed_bills = []
        if payor_type == PayorType.MEMBER:
            failed_bills = (
                self.bill_repo.get_failed_bills_by_payor_id_type_and_error_types(
                    payor_id=payor_id,
                    payor_type=payor_type,
                    exclude_refunds=True,
                    error_types=error_types,
                )
            )

            tp_ids = {b.procedure_id for b in failed_bills}
            tps = list(get_treatment_procedures_as_dicts_from_ids(tp_ids).values())
            canc_tp_ids = {tp["id"] for tp in tps if tp["status"].value == "CANCELLED"}
            log.info("Cancelled TPS are:", cancelled_tp_ids=str(canc_tp_ids))
            filtered_failed_bills = [
                b for b in failed_bills if b.procedure_id not in canc_tp_ids
            ]
            log.info(
                "Queried for failed bills with specified error_types. Filtered out those with cancelled TPs.",
                filtered_failed_bills=str([b.id for b in filtered_failed_bills]),
                failed_bills=str([b.id for b in failed_bills]),
                error_types=error_types,
            )

        else:
            log.info(
                "Failed Employer and Clinic bills are not auto-retried through this flow."
            )
        return filtered_failed_bills

    def _get_new_bills_by_payor_id_and_type(
        self, payor_id: int, payor_type: PayorType
    ) -> list[Bill]:
        to_return = self.bill_repo.get_new_bills_by_payor_id_and_type(
            payor_id=payor_id,
            payor_type=payor_type,
            exclude_refunds=True,
        )
        return to_return

    def _update_payment_data_on_bills_add_bprs_in_memory(
        self,
        payment_method_package: dict[str, str],
        bills_to_update: list[Bill],
        message: PaymentGatewayEventMessage | None,
        record_type: ProcessingRecordTypeT,
    ) -> list[str]:
        replacement_data = {
            "payment_method_label": payment_method_package["last4"],
            "payment_method_type": payment_method_package["payment_method_type"],
            "payment_method_id": payment_method_package["payment_method_id"],
        }

        card_funding = None
        try:
            if hasattr(CardFunding, payment_method_package.get("card_funding") or ""):
                card_funding = CardFunding(payment_method_package["card_funding"])

            replacement_data["card_funding"] = (
                card_funding.value if card_funding else None  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Union[str, str, str, str, None]", target has type "str")
            )
        except Exception:
            log.warn(
                "Unable to parse card funding. Setting to none.",
                payment_method_package=payment_method_package,
                reason=format_exc(),
            )

        bill_id_bpr_dict = {
            bill_to_update.id: self.bill_processing_record_repo.get_latest_row_with_specified_statuses(
                [bill_to_update.id], [BillStatus.FAILED]  # type: ignore[list-item] # List item 0 has incompatible type "Optional[int]"; expected "int"
            )
            for bill_to_update in bills_to_update
        }
        to_return = []
        for bill_to_update in bills_to_update:
            log.info(
                "Updating payment method in memory on bill.", bill_id=bill_to_update.id
            )
            original_payment_method_data = {
                "payment_method_label": bill_to_update.payment_method_label,
                "payment_method_type": (
                    bill_to_update.payment_method_type.value
                    if bill_to_update.payment_method_type
                    else ""
                ),
                "payment_method_id": bill_to_update.payment_method_id,
                "last_calculated_fee": bill_to_update.last_calculated_fee,
            }

            new_fee = calculate_fee(
                bill_to_update.payment_method,
                PaymentMethodType(payment_method_package["payment_method_type"]),
                bill_to_update.amount,
                card_funding,  # type: ignore[arg-type] # Argument 4 to "calculate_fee" has incompatible type "Optional[CardFunding]"; expected "CardFunding"
            )

            updated_bill = dataclasses.replace(
                bill_to_update,
                **{**replacement_data, **{"last_calculated_fee": new_fee}},  # type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, object]"; expected "UUID" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, object]"; expected "int" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, object]"; expected "Optional[int]" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, object]"; expected "Optional[str]" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, object]"; expected "PayorType" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, object]"; expected "BillStatus" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, object]"; expected "PaymentMethod" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, object]"; expected "Optional[PaymentMethodType]" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, object]"; expected "Optional[datetime]" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, object]"; expected "Optional[CardFunding]" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, object]"; expected "str" #type: ignore[arg-type] # Argument 2 to "replace" of "Bill" has incompatible type "**Dict[str, object]"; expected "bool"
            )
            updated_bill = self.bill_repo.update(instance=updated_bill)
            to_return.append(updated_bill.id)
            body = {
                "delta": {
                    "original_payment_method_data": original_payment_method_data,
                    "replacement_payment_method_data": {
                        **{**replacement_data, **{"last_calculated_fee": new_fee}}
                    },
                },
            }
            if message:
                body["message_payload"] = message.message_payload
            self._add_bill_processing_record(
                record_type=record_type,
                bill=updated_bill,
                body=body,
                transaction_id=(
                    bill_id_bpr_dict[updated_bill.id].transaction_id  # type: ignore[union-attr] # Item "None" of "Optional[BillProcessingRecord]" has no attribute "transaction_id"
                    if bill_id_bpr_dict.get(updated_bill.id)
                    else None
                ),
            )
            log.info(
                "Updated payment method in memory on bill and bpr.",
                bill_id=bill_to_update.id,
                card_funding=card_funding,
            )
        return to_return  # type: ignore[return-value] # Incompatible return value type (got "List[Optional[int]]", expected "List[str]")

    def _async_retry_bills(self, failed_bill_ids: [int]) -> None:  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
        if failed_bill_ids:
            try:
                log.info(
                    "Spawning job to process failed bills.",
                    failed_bill_ids_cnt=len(failed_bill_ids),
                    failed_bill_ids=failed_bill_ids,
                )
                retry_failed_bills.delay(failed_bill_ids=failed_bill_ids)
            except Exception:
                log.error(
                    "Error spawning job to process failed bills.", reason=format_exc()
                )
        else:
            log.info("No failed bills to retry.")

    def get_member_paid_by_procedure_ids(
        self,
        procedure_ids: list[int],
    ) -> dict[int, list[models.Bill]]:
        bills = self.bill_repo.get_by_procedure(
            procedure_ids=procedure_ids,
            status=[BillStatus.PAID, BillStatus.REFUNDED],
            exclude_payor_types=[PayorType.CLINIC, PayorType.EMPLOYER],
        )
        bill_ids = []
        bill_ids_to_bills = {}
        for bill in bills:
            bill_ids.append(bill.id)
            bill_ids_to_bills[bill.id] = bill
        bill_ids_with_money_movement = self.bill_processing_record_repo.filter_bill_ids_for_money_movement(
            bill_ids=bill_ids  # type: ignore[arg-type] # Argument "bill_ids" to "filter_bill_ids_for_money_movement" of "BillProcessingRecordRepository" has incompatible type "List[Optional[int]]"; expected "List[int]"
        )
        tp_to_bills = defaultdict(list)
        if bill_ids_with_money_movement:
            for bill_id in bill_ids_with_money_movement:
                bill = bill_ids_to_bills[bill_id]
                tp_to_bills[bill.procedure_id].append(bill)
        return tp_to_bills

    def get_procedure_ids_with_estimates_or_bills(
        self, procedure_ids: list[int], is_ephemeral: bool
    ) -> list[int]:
        if is_ephemeral:
            return self.bill_repo.get_procedure_ids_with_ephemeral_bills(
                procedure_ids=procedure_ids
            )
        else:
            return self.bill_repo.get_procedure_ids_with_non_ephemeral_bills(
                procedure_ids=procedure_ids
            )


@job(service_ns="billing", team_ns="benefits_experience")
def retry_failed_bills(failed_bill_ids: [int]) -> None:  # type: ignore[valid-type] # Bracketed expression "[...]" is not valid as a type
    """
    Temporary RQ job to retry bills as a background process. Will be replaced with pubsub.
    """
    billing_service = BillingService(
        session=connection.db.session,
        payment_gateway_base_url=INTERNAL_TRUST_PAYMENT_GATEWAY_URL,
    )
    failed_bill_cnt = len(failed_bill_ids)
    log.info("Retrying failed bills.", failed_bill_cnt=failed_bill_cnt)
    for i, failed_bill_id in enumerate(failed_bill_ids):
        log.info(
            "Retrying failed bill.",
            bill_id=failed_bill_id,
            bill_idx_1=i + 1,
            failed_bill_cnt=failed_bill_cnt,
        )
        try:
            failed_bill = billing_service.get_bill_by_id(failed_bill_id)
            if not failed_bill:
                log.error("Unable to load bill for retry", bill_id=failed_bill_id)
                raise ValueError(f"Unable to load bill {failed_bill_id}")

            log.info(
                "Loaded bill for retry.",
                bill_id=failed_bill_id,
                bill_status=failed_bill.status.value if failed_bill.status else "",
            )

            retried_bill = billing_service.retry_bill(
                bill=failed_bill, initiated_by="rq_job_retry_failed_bills", headers=None  # type: ignore[arg-type] # Argument "headers" to "retry_bill" of "BillingService" has incompatible type "None"; expected "Mapping[str, str]"
            )
            log.info(
                "Bill retry complete.",
                bill_id=retried_bill.id,
                bill_status=retried_bill.status.value if retried_bill.status else "",
            )
        except Exception:
            log.exception(
                "Retry for bill could not complete.",
                stack_info=True,
                bill_d=failed_bill_id,
                reason=format_exc(),
            )


@job(service_ns="billing", team_ns="benefits_experience")
def from_employer_bill_create_clinic_bill_and_process(*, emp_bill_id: int) -> int:
    """
    Temporary RQ job to retry bills as a background process. Will be replaced with pubsub.
    :param emp_bill_id: ID a PAID or FAILED EMPLOYER bill
    :return: 0 on success 1 on failure
    """
    try:
        billing_service = BillingService(
            session=connection.db.session,
            payment_gateway_base_url=(
                UNAUTHENTICATED_PAYMENT_SERVICE_URL
                if IS_INTEGRATIONS_K8S_CLUSTER
                else INTERNAL_TRUST_PAYMENT_GATEWAY_URL
            ),
        )
        return from_employer_bill_create_clinic_bill_and_process_with_billing_service(
            emp_bill_id=emp_bill_id, billing_service=billing_service
        )
    except Exception:
        log.error(
            "Unable to create and/or process clinic bill from Employer Bill",
            input_bill=emp_bill_id,
            reason=format_exc(),
        )
    return 1  # Failure


def from_employer_bill_create_clinic_bill_and_process_with_billing_service(
    *, emp_bill_id: int, billing_service: BillingService
) -> int:
    """
    Retry bills as a background process. Will be replaced with pubsub.
    :param emp_bill_id: ID a PAID or FAILED EMPLOYER bill
    :param billing_service: the BillingService instance for processing bills
    :return: 0 on success 1 on failure
    """
    try:
        input_bill = billing_service.get_bill_by_id(emp_bill_id)
        if (
            _check_validity_of_input_bill(input_bill)  # type: ignore[arg-type] # Argument 1 to "_check_validity_of_input_bill" has incompatible type "Optional[Bill]"; expected "Bill"
            and _check_for_pre_existing_clinic_bills(billing_service, input_bill)  # type: ignore[arg-type] # Argument 2 to "_check_for_pre_existing_clinic_bills" has incompatible type "Optional[Bill]"; expected "Bill"
            and (treatment_proc_dict := _get_treatment_proc_dict(input_bill))  # type: ignore[arg-type] # Argument 1 to "_get_treatment_proc_dict" has incompatible type "Optional[Bill]"; expected "Bill"
        ):
            create_and_process_clinic_bill(
                billing_service=billing_service,
                input_bill=input_bill,  # type: ignore[arg-type] # Argument "input_bill" to "create_and_process_clinic_bill" has incompatible type "Optional[Bill]"; expected "Bill"
                treatment_proc_dict=treatment_proc_dict,
            )
            return 0
    except Exception:
        log.error(
            "Unable to create and/or process clinic bill from Employer Bill",
            input_bill=emp_bill_id,
            reason=format_exc(),
        )
    return 1  # Failure


def from_employer_bill_create_clinic_bill_with_billing_service(
    *, input_employer_bill: Bill, billing_service: BillingService
) -> Bill | None:
    """
    Retry bills as a background process. Will be replaced with pubsub.
    :param input_employer_bill: An employer bill
    :param billing_service: the BillingService instance for processing bills
    :return: True on success False on failure
    """
    if (
        not input_employer_bill
        or input_employer_bill.payor_type != PayorType.EMPLOYER
        or input_employer_bill.status == BillStatus.CANCELLED
    ):
        log.warn(
            "Null or non-Employer Bill",
            input_bill_id=str(input_employer_bill.id) if input_employer_bill else "N/A",
            input_employer_bill_payor_type=str(input_employer_bill.payor_type)
            if input_employer_bill
            else "N/A",
            input_employer_bill_status=str(input_employer_bill.status)
            if input_employer_bill
            else "N/A",
        )
        return None

    try:
        if _check_for_pre_existing_clinic_bills(
            billing_service, input_employer_bill
        ) and (  # type: ignore[arg-type] # Argument 2 to "_check_for_pre_existing_clinic_bills" has incompatible type "Optional[Bill]"; expected "Bill"
            treatment_proc_dict := _get_treatment_proc_dict(input_employer_bill)
        ):  # type: ignore[arg-type] # Argument 1 to "_get_treatment_proc_dict" has incompatible type "Optional[Bill]"; expected "Bill"
            clinic_bill = _create_and_persist_clinic_bill(
                billing_service=billing_service,
                input_bill=input_employer_bill,
                treatment_proc_dict=treatment_proc_dict,
            )
            return clinic_bill
    except Exception:
        log.error(
            "Unable to create clinic bill from Employer Bill",
            input_bill=str(input_employer_bill.id),
            reason=format_exc(),
        )
    return None


def _create_and_persist_clinic_bill(
    billing_service: BillingService, input_bill: Bill, treatment_proc_dict: dict
) -> Bill | None:
    (
        amount,
        _,
    ) = billing_service.calculate_new_and_past_bill_amount_from_new_responsibility(
        payor_id=input_bill.payor_id,
        payor_type=PayorType.CLINIC,
        procedure_id=input_bill.procedure_id,
        new_responsibility=treatment_proc_dict["cost"],
    )
    if amount is not None:
        # create a clinic bill
        clinic_bill = billing_service.create_bill(
            payor_type=PayorType.CLINIC,
            amount=amount,
            label=input_bill.label,  # type: ignore[arg-type] # Argument "label" to "create_bill" of "BillingService" has incompatible type "Optional[str]"; expected "str"
            payor_id=treatment_proc_dict["fertility_clinic_id"],
            treatment_procedure_id=input_bill.procedure_id,
            cost_breakdown_id=input_bill.cost_breakdown_id,
            payment_method=models.PaymentMethod.PAYMENT_GATEWAY,
            payment_method_label=None,  # type: ignore[arg-type] # Argument "payment_method_label" to "create_bill" of "BillingService" has incompatible type "None"; expected "str"
            headers=None,  # type: ignore[arg-type] # Argument "headers" to "create_bill" of "BillingService" has incompatible type "None"; expected "Mapping[str, str]"
        )
        billing_service.session.commit()
        log.info(
            "Clinic bill created from input bill.",
            input_bill_id=str(input_bill.id),
            clinic_bill_id=str(clinic_bill.id),
            clinic_bill_amount=clinic_bill.amount,
            payor_id=str(clinic_bill.payor_id),
            treatment_procedure_id=str(clinic_bill.procedure_id),
            cost_breakdown_id=str(clinic_bill.cost_breakdown_id),
        )
        stats.increment(
            metric_name="direct_payment.billing.billing_service.clinic_bill",
            pod_name=stats.PodNames.BENEFITS_EXP,
        )
        return clinic_bill
    log.info(
        "Clinic bill not created - pre-existing clinic bills and delta with sum(pre-existing bills) is 0.",
        input_bill_id=input_bill.id,
        payor_id=str(treatment_proc_dict["fertility_clinic_id"]),
        treatment_procedure_id=str(input_bill.procedure_id),
        cost_breakdown_id=str(input_bill.cost_breakdown_id),
    )
    return None


def create_and_process_clinic_bill(
    billing_service: BillingService,
    input_bill: Bill,
    treatment_proc_dict: dict,
) -> Bill | None:
    clinic_bill = _create_and_persist_clinic_bill(
        billing_service, input_bill, treatment_proc_dict
    )
    if clinic_bill:
        log.info(
            "Created clinic bill from input bill - submitting for processing.",
            input_bill_id=input_bill.id,
            clinic_bill_id=clinic_bill.id,
        )

        submitted_clinic_bill = billing_service.set_new_bill_to_processing(clinic_bill)
        log.info(
            "Clinic bill from input bill - submitted for processing.",
            clinic_bill_id=submitted_clinic_bill.id,
            clinic_bill_status=submitted_clinic_bill.status,
        )
        return clinic_bill
    return None


def _get_treatment_proc_dict(input_bill: Bill) -> dict | None:
    if not (
        treatment_proc := get_treatment_procedure_as_dict_from_id(
            input_bill.procedure_id
        )
    ):
        log.error(
            "Unable to find treatment id from bill. This should never happen.",
            input_bill_id=input_bill.id,
            procedure_id=input_bill.procedure_id,
        )
        return None
    cost = treatment_proc.get("cost", None)
    fertility_clinic_id = treatment_proc.get("fertility_clinic_id", 0)
    if cost is None or not fertility_clinic_id:
        log.error(
            "Either cost or fertility_clinic_id is blank or missing from the treatment_proc data.",
            input_bill_id=input_bill.id,
            procedure_id=input_bill.procedure_id,
            cost=cost,
            fertility_clinic_id=fertility_clinic_id,
            treatment_proc=treatment_proc,
        )
        return None
    return treatment_proc


def _check_validity_of_input_bill(input_bill: Bill) -> bool:
    """Validation for from_employer_bill_create_clinic_bill_and_process"""
    if not (
        to_return := (
            input_bill.payor_type == PayorType.EMPLOYER
            and input_bill.status
            in {BillStatus.PAID, BillStatus.FAILED, BillStatus.REFUNDED}
        )
    ):
        log.error(
            "Input bill is not a PAID or FAILED EMPLOYER bill.",
            input_bill_id=input_bill.id,
            input_bill_status=input_bill.status,
            input_bill_payor_type=input_bill.payor_type,
        )
    return to_return


def _check_for_pre_existing_clinic_bills(
    billing_service: BillingService, input_bill: Bill
) -> bool:
    # have to protect against double payments here - the check below will suffice for now, and once a proper
    # pubsub is implemented, we can handle this more gracefully
    # TODO add a custom query for this
    clinic_bills = billing_service.get_bills_by_procedure_ids(
        [input_bill.procedure_id],
        exclude_payor_types=[PayorType.EMPLOYER, PayorType.MEMBER],
        status=[
            BillStatus.PAID,
            BillStatus.NEW,
            BillStatus.PROCESSING,
            BillStatus.FAILED,
        ],
    )
    og_clinic_bill_cnt = len(clinic_bills)

    if og_clinic_bill_cnt >= 1:
        log.error(
            f"{og_clinic_bill_cnt} pre-existing clinic bill(s) linked to input bill",
            input_bill_id=input_bill.id,
            procedure_id=input_bill.procedure_id,
            clinic_bills=[bill.id for bill in clinic_bills],
        )
        return False
    return True
