from traceback import format_exc

from flask import flash, redirect, request, url_for
from flask_admin import actions, expose
from maven import feature_flags

from admin.views.base import (
    AmountDisplayCentsInDollarsField,
    IsFilter,
    cents_to_dollars_formatter,
)
from authn.models.user import User
from authn.resources.admin import BaseClassicalMappedView
from direct_payment.billing import models
from direct_payment.billing.billing_admin import (
    BillingAdminService,
    BillValidationException,
)
from direct_payment.billing.billing_service import (
    BillingService,
    _check_for_pre_existing_clinic_bills,
    _check_validity_of_input_bill,
    _get_treatment_proc_dict,
    create_and_process_clinic_bill,
    from_employer_bill_create_clinic_bill_with_billing_service,
)
from direct_payment.billing.constants import INTERNAL_TRUST_PAYMENT_GATEWAY_URL
from direct_payment.billing.repository import BillRepository
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
)
from storage.connection import db
from utils.log import logger
from utils.payments import convert_dollars_to_cents
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

log = logger(__name__)


class BillUserEmailFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.join(
                ReimbursementWallet,
                ReimbursementWallet.id == BillRepository.model.payor_id,
            )
            .join(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == ReimbursementWallet.id,
            )
            .join(ReimbursementWalletUsers.member)
            .filter(User.email == value)
        )


class BillUserIdFilter(IsFilter):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return query.join(
            TreatmentProcedure,
            TreatmentProcedure.id == BillRepository.model.procedure_id,
        ).filter(TreatmentProcedure.member_id == value)


def get_user_id_for_treatment_procedure(view, context, model, name) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    bill_id = model.id
    query = """
        SELECT tp.member_id
        FROM treatment_procedure tp
        JOIN bill b
        ON tp.id = b.procedure_id
        WHERE b.id = :bill_id
        LIMIT 1;
    """
    result = db.session.execute(query, {"bill_id": bill_id})
    if result:
        return str(next(result)[0])
    return ""


def _is_ephemeral_formatter(view, context, model, name) -> str:  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
    bill_id = model.id
    query = """ 
    SELECT bill.is_ephemeral 
    FROM bill 
    WHERE bill.id = :bill_id 
    LIMIT 1; """
    result = db.session.execute(query, {"bill_id": bill_id})
    if result:
        res = next(result)[0]
        return "True" if res else "False"
    return "False"


class BillView(BaseClassicalMappedView):
    def __init__(self, model, *args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        super().__init__(model, *args, **kwargs)
        self.svc = BillingService(
            session=db.session,
            # configured for internal trust
            payment_gateway_base_url=INTERNAL_TRUST_PAYMENT_GATEWAY_URL,
        )
        self.admin_svc = BillingAdminService()

    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    read_permission = "read:direct-payment-bills"
    create_permission = "create:direct-payment-bills"
    delete_permission = "delete:direct-payment-bills"

    repo = BillRepository  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Type[BillRepository]", base class "BaseClassicalMappedView" defined the type as "BaseRepository[Any]")

    list_template = "list.html"
    details_template = "bill_detail_template.html"

    form_create_rules = (
        "label",
        "amount",
        "status",
        "payor_type",
        "payor_id",
        "payment_method",
        "procedure_id",
        "cost_breakdown_id",
    )
    column_formatters = {
        "amount": cents_to_dollars_formatter,
        "member_id": get_user_id_for_treatment_procedure,
        "is_ephemeral": _is_ephemeral_formatter,
    }
    form_overrides = {
        "amount": AmountDisplayCentsInDollarsField,
    }
    form_args = {"amount": {"allow_negative": True}}

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        try:
            try:
                # convert form data to enum values where necessary
                payor_type = models.PayorType(form.data["payor_type"])
                payment_method = models.PaymentMethod(form.data["payment_method"])
                requested_status = models.BillStatus(form.data["status"])

                # validate form data
                self.admin_svc.validate_bill_view_form_data(
                    payor_type=payor_type,
                    payor_id=form.data["payor_id"],
                    procedure_id=form.data["procedure_id"],
                    cost_breakdown_id=form.data["cost_breakdown_id"],
                    payment_method=payment_method,
                    requested_status=requested_status,
                )
            except BillValidationException as e:
                flash(str(e), "error")
                return False

            # create bill
            bill = self.svc.create_bill(
                amount=(
                    convert_dollars_to_cents(form.data["amount"])
                    if form.data["amount"] is not None
                    else 0
                ),
                label=form.data["label"],
                payor_type=payor_type,
                payor_id=form.data["payor_id"],
                treatment_procedure_id=form.data["procedure_id"],
                cost_breakdown_id=form.data["cost_breakdown_id"],
                payment_method=payment_method,
                # This label will be updated inside create_bill.
                payment_method_label=None,  # type: ignore[arg-type] # Argument "payment_method_label" to "create_bill" of "BillingService" has incompatible type "None"; expected "str"
            )
            self.svc.session.commit()
            bill = self.svc.get_bill_by_uuid(str(bill.uuid))  # type: ignore[assignment] # Incompatible types in assignment (expression has type "Optional[Bill]", variable has type "Bill")
            log.info("Created and committed bill and reloaded it.", bill_uuid=bill.uuid)

            # Update the bill to a new status if necessary.
            if requested_status.value == "CANCELLED":
                self.svc._update_bill_add_bpr_and_commit(  # type: ignore[call-arg] # Missing positional argument "transaction_id" in call to "_update_bill_add_bpr_and_commit" of "BillingService"
                    bill,
                    new_bill_status=models.BillStatus.CANCELLED,
                    record_type="billing_service_workflow",
                    record_body={},
                )

            if requested_status.value in ["PROCESSING", "PAID", "REFUNDED"]:
                self.svc._update_bill_add_bpr_and_commit(  # type: ignore[call-arg] # Missing positional argument "transaction_id" in call to "_update_bill_add_bpr_and_commit" of "BillingService"
                    bill,
                    new_bill_status=models.BillStatus.PROCESSING,
                    record_type="billing_service_workflow",
                    record_body={},
                )

                if requested_status.value in ["PAID", "REFUNDED"]:
                    self.svc._update_bill_add_bpr_and_commit(  # type: ignore[call-arg] # Missing positional argument "transaction_id" in call to "_update_bill_add_bpr_and_commit" of "BillingService"
                        bill,
                        new_bill_status=models.BillStatus(requested_status),
                        record_type="billing_service_workflow",
                        record_body={},
                    )
        except (
            Exception
        ) as e:  # broad try/catch exception to match existing flask admin code
            flash(f"Failed to create record: {str(e)}", "error")
            return False
        return form.data

    can_view_details = True
    column_default_sort = ("created_at", True)
    column_list = [
        "id",
        "uuid",
        "member_id",
        "label",
        "amount",
        "status",
        "last_calculated_fee",
        "payor_type",
        "payor_id",
        "payment_method",
        "payment_method_label",
        "payment_method_type",
        "card_funding",
        "procedure_id",
        "cost_breakdown_id",
        "error_type",
        "created_at",
        "processing_scheduled_at_or_after",
        "is_ephemeral",
    ]
    column_filters = [
        BillUserEmailFilter(None, "Member Email"),
        BillUserIdFilter(None, "User ID"),
        "id",
        "uuid",
        "payor_type",
        "payor_id",
        "procedure_id",
        "cost_breakdown_id",
        "status",
        "payment_method_type",
        "card_funding",
    ]
    column_details_list = (
        "id",
        "uuid",
        "label",
        "amount",
        "status",
        "last_calculated_fee",
        "payor_type",
        "payor_id",
        "payment_method",
        "payment_method_label",
        "payment_method_type",
        "card_funding",
        "procedure_id",
        "cost_breakdown_id",
        "error_type",
        "created_at",
        "processing_at",
        "failed_at",
        "paid_at",
        "refunded_at",
        "cancelled_at",
        "modified_at",
        "processing_scheduled_at_or_after",
        "is_ephemeral",
    )
    column_exclude_list = [
        "payor_id",
    ]

    @actions.action(
        name="mass_process_bills",
        text="Process Bills",
        confirmation="Are you sure you want to move all these bills to PROCESSING? "
        "This only works on NEW and FAILED bills. "
        "Statuses may take some time to update.",
    )
    def mass_process_bills(self, ids):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Inefficient but direct batch processing action."""
        bills = self.svc.get_bills_by_ids(ids)
        invalid_bills = []
        for bill in bills:
            try:
                self.admin_svc.process_bill_in_admin(self.svc, bill)
            except Exception as e:
                log.error(
                    "Failure to process a bill as part of the mass_process_bills bulk action",
                    exception=str(e),
                    bill_id=bill.id,
                    bill_status=bill.status.value,
                )
                invalid_bills.append(str(bill.id))
                continue
        if len(invalid_bills) == 0:
            flash(
                "Selected bills set to processing. Statuses may take some time to update.",
                "success",
            )
        else:
            flash(
                f"The following bills failed to process: {', '.join(invalid_bills)}",
                "error",
            )

    @actions.action(
        name="mass_create_clinic_bills",
        text="Create Clinic Bills",
        confirmation="Are you sure you want to create clinic bills from all these employer bills? "
        "This will NOT check for EMPLOYER Bill Status. "
        "Bills may take some time to be fully created.",
    )
    def mass_create_clinic_bills(self, ids: list) -> None:
        enabled = feature_flags.bool_variation(
            flag_key="enable-admin-mass-create-clinic-bills", default=False
        )
        log.info("mass_create_clinic_bills feature enabled?", enabled=enabled)
        if not enabled:
            flash(
                "This feature is currently disabled. Please contact engineering/product to have it enabled",
                "warning",
            )
            return
        input_ids = sorted(int(id_) for id_ in ids)  # just so the sort is nice
        bills = self.svc.get_bills_by_ids(input_ids)
        employer_bills = [
            b
            for b in bills
            if b
            and b.payor_type == models.PayorType.EMPLOYER
            and b.status != models.BillStatus.CANCELLED
        ]
        employer_bill_ids = sorted(b.id for b in employer_bills)  # type: ignore[type-var]
        invalid_ids = sorted(set(input_ids) - set(employer_bill_ids))
        log.info(
            "Starting batch clinic bill create.",
            input_ids=", ".join(map(str, input_ids)),
            employer_bill_ids=", ".join(map(str, employer_bill_ids)),
            invalid_ids=", ".join(map(str, invalid_ids)),
            employer_bill_cnt=len(employer_bills),
        )

        clinic_bill_ids = []
        failed_employer_bill_ids = []
        for i, employer_bill in enumerate(employer_bills):
            log.info(
                "starting employer bill -> clinic bill creation.",
                employer_bill_index=i,
                employer_bills_cnt=len(employer_bills),
                employer_bill_id=str(employer_bill.id),
            )
            clinic_bill = from_employer_bill_create_clinic_bill_with_billing_service(
                input_employer_bill=employer_bill, billing_service=self.svc
            )

            clinic_bill_ids.append(
                clinic_bill.id
            ) if clinic_bill else failed_employer_bill_ids.append(employer_bill.id)
            log.info(
                "Completed employer bill -> clinic bill creation.",
                employer_bill_index=i,
                employer_bills_cnt=len(employer_bills),
                employer_bill_id=str(employer_bill.id),
                clinic_bill_id=str(clinic_bill.id) if clinic_bill else "N/A",
            )
        failed_employer_bill_ids_str = ", ".join(map(str, failed_employer_bill_ids))
        msg = (
            f"Created {len(clinic_bill_ids)} clinic bills from {len(input_ids)} bills ids of which "
            f"{len(employer_bill_ids)} ids were employer bill ids. "
            f"Clinic bills  could not be created for the following employer bill ids: {failed_employer_bill_ids_str}"
        )

        log.info(
            "Completed batch clinic bill create.",
            clinic_bill_id_cnt=len(clinic_bill_ids),
            clinic_bill_ids=", ".join(map(str, clinic_bill_ids)),
            failed_employer_bill_id_cnt=len(failed_employer_bill_ids),
            failed_employer_bill_ids=failed_employer_bill_ids_str,
            msg=msg,
        )
        flash(msg, "warning" if failed_employer_bill_ids else "success")

    @expose("/process_bill", methods=["POST"])
    def process_bill(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        bill_id = request.form.get("bill_id")
        bill = self.svc.get_bill_by_id(bill_id)  # type: ignore[arg-type] # Argument 1 to "get_bill_by_id" of "BillingService" has incompatible type "Optional[Any]"; expected "int"
        if bill is None:
            flash(f"Bill <{bill_id}> not found. Processing failed.", "error")
        elif bill.is_ephemeral:
            flash(f"Bill <{bill_id}> is ephemeral. Processing blocked.", "error")
        else:
            try:
                self.admin_svc.process_bill_in_admin(self.svc, bill)
            except Exception as e:
                log.error(
                    "Failure to perform the process_bill action.",
                    exception=str(e),
                    bill_id=bill.id,
                    bill_status=bill.status.value,
                )
                flash(f"Failed to process bill. Error: {str(e)}", "error")
        return redirect(url_for("bill.details_view", id=bill_id))

    @expose("/new_clinic", methods=["POST"])
    def create_new_clinic_bill_from_employer_bill(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        bill_id = request.form.get("bill_id")
        try:
            bill = self.svc.get_bill_by_id(bill_id)  # type: ignore[arg-type] # Argument 1 to "get_bill_by_id" of "BillingService" has incompatible type "Optional[Any]"; expected "int"
            if bill is None:
                flash(
                    f"Bill <{bill_id}> not found. Employer->Clinic action failed.",
                    "error",
                )
            elif bill.is_ephemeral:
                flash(f"Bill <{bill_id}> is ephemeral. Processing blocked.", "error")
            else:
                # Give clear feedback to admin users.
                if not _check_validity_of_input_bill(bill):
                    flash(
                        "EMPLOYER Bill must be in a PAID or FAILED state to create a CLINIC bill.",
                        "error",
                    )
                    pass
                if not _check_for_pre_existing_clinic_bills(self.svc, bill):
                    flash(
                        "There is already a CLINIC bill for this EMPLOYER bill.",
                        "error",
                    )
                    pass
                if not (treatment_proc_dict := _get_treatment_proc_dict(bill)):
                    flash(
                        "Either cost or fertility_clinic_id is missing from the treatment_procedure data.",
                        "error",
                    )
                    pass
                else:
                    clinic_bill = create_and_process_clinic_bill(
                        self.svc, bill, treatment_proc_dict
                    )
                    if clinic_bill:
                        flash(
                            f"Created and processed a new CLINIC Bill for the EMPLOYER bill {bill_id}."
                        )
                    else:
                        flash(
                            f"No CLINIC bill created since pre-existing clinic bills and delta with sum(pre-existing bills) is 0 for EMPLOYER bill {bill_id}."
                        )
                    # Since we're creating the clinic bill via POST instead of RQ, we can redirect to the result
                    # Downside is the creation process will be slow.
                    return redirect(url_for("bill.details_view", id=clinic_bill.id))  # type: ignore[union-attr] # Item "None" of "Optional[Bill]" has no attribute "id"
        except Exception as e:
            log.error(
                "Failure to perform the create_new_clinic_bill_from_employer_bill action.",
                exception=str(e),
            )
            flash(f"Failed to process bill. Error: {str(e)}", "error")
        return redirect(url_for("bill.details_view", id=bill_id))

    @expose("/cancel_bill", methods=["POST"])
    def cancel_bill(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        bill_id = request.form.get("bill_id")
        bill = self.svc.get_bill_by_id(bill_id)  # type: ignore[arg-type] # Argument 1 to "get_bill_by_id" of "BillingService" has incompatible type "Optional[Any]"; expected "int"
        if bill is None:
            flash(f"Bill <{bill_id}> not found. Cancel failed.", "error")
        else:
            try:
                res = self.admin_svc.cancel_bill_in_admin(self.svc, bill)
                if res.id == bill_id and res.status != models.BillStatus.CANCELLED:
                    flash(
                        f"Cancellation of bill <{bill_id}> has been blocked. "
                        "This can happen if this bill is linked to an invoicing organization",
                        "warning",
                    )
            except Exception as e:
                log.error(
                    "Failure to perform the cancel_bill action.",
                    exception=str(e),
                    bill_id=bill.id,
                    bill_status=bill.status.value,
                )
                flash(f"Failed to cancel bill. Error: {str(e)}", "error")
        return redirect(url_for("bill.details_view", id=bill_id))

    @expose("/create_refund_from_paid_bill", methods=["POST"])
    def create_refund_from_paid_bill(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        bill_id = request.form.get("bill_id")
        bill = self.svc.get_bill_by_id(bill_id)  # type: ignore[arg-type] # Argument 1 to "get_bill_by_id" of "BillingService" has incompatible type "Optional[Any]"; expected "int"
        redirect_bill_id = bill_id
        if bill is None:
            flash(f"Bill <{bill_id}> not found. Cancel failed.", "error")
        elif bill.is_ephemeral:
            flash(f"Bill <{bill_id}> is ephemeral. Processing blocked.", "error")
        else:
            try:
                refund_bill = self.admin_svc.create_refund_from_paid_bill(
                    self.svc, bill
                )
                if not refund_bill:
                    flash(
                        f"{bill_id} was previously fully refunded. Nothing was done here.",
                        "info",
                    )
                else:
                    redirect_bill_id = refund_bill.id
                    flash(
                        f"{refund_bill.id} has been created.",
                        "info",
                    )
            except Exception as e:
                log.error(
                    "Failure to create refund from paid_bill.",
                    exception=str(e),
                    exception_args=e.args,
                    bill_id=str(bill.id),
                    bill_status=bill.status.value,
                    reason=format_exc(),
                )
                flash(f"Failed to cancel bill. Error: {str(e)}", "error")
            return redirect(url_for("bill.details_view", id=redirect_bill_id))

    @expose("/update_payment_method_on_bill", methods=["POST"])
    def update_payment_method_on_bill(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        bill_id = request.form.get("bill_id")
        log.info("Attempting payment method update:", bill_id=bill_id)
        bill = self.svc.get_bill_by_id(int(bill_id))  # type: ignore[arg-type] # Argument 1 to "int" has incompatible type "Optional[Any]"; expected "Union[str, Buffer, SupportsInt, SupportsIndex, SupportsTrunc]"
        redirect_bill_id = bill_id
        if bill is None:
            flash(f"Bill <{bill_id}> not found.", "error")
        else:
            try:
                res = self.admin_svc.update_payment_method_on_bill(self.svc, bill)
                flash(res, "info")
            except Exception as e:
                log.error(
                    "Unable to update payment method on bill.",
                    exception=str(e),
                    exception_args=e.args,
                    bill_id=str(bill.id),
                    bill_status=bill.status.value,
                    reason=format_exc(),
                )
                flash(
                    f"Unable to update payment method on bill <{bill_id}>.",
                    "error",
                )
            return redirect(url_for("bill.details_view", id=redirect_bill_id))
