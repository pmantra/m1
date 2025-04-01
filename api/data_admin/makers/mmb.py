import datetime

from flask import flash, request

from authn.models.user import User
from cost_breakdown.models.cost_breakdown import CostBreakdown
from data_admin.maker_base import _MakerBase
from data_admin.makers.fertility_clinic import FertilityClinicMaker
from data_admin.makers.payer_accumulation import AccumulationMappingMaker
from direct_payment.billing import models as billing_models
from direct_payment.billing.billing_service import BillingService
from direct_payment.billing.constants import INTERNAL_TRUST_PAYMENT_GATEWAY_URL
from direct_payment.clinic.models.clinic import FertilityClinic
from direct_payment.clinic.models.fee_schedule import (
    FeeSchedule,
    FeeScheduleGlobalProcedures,
)
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.models.treatment_proceedure_needing_questionnaire import (
    TreatmentProceduresNeedingQuestionnaires,
)
from payer_accumulator.accumulation_mapping_service import AccumulationMappingService
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class TreatmentProcedureMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        user = User.query.filter_by(email=spec.get("user")).first()
        if not user:
            raise ValueError(f'No user found for email: {spec.get("user")}.')
        if not user.reimbursement_wallets:
            raise ValueError(f'No wallets found for user: {spec.get("user")}.')
        wallet = user.reimbursement_wallets[0]

        categories = (
            wallet.reimbursement_organization_settings.allowed_reimbursement_categories
        )
        if not categories:
            raise ValueError(
                f"No reimbursement categories found for user & wallet configuration for user {spec.get('user')}"
            )
        category_id = categories[0].reimbursement_request_category_id

        if "fee_schedule" not in spec:
            raise ValueError("No fee_schedule found in fixture")
        start_date = datetime.datetime.fromisoformat(spec.get("start_date"))
        end_date = datetime.datetime.fromisoformat(spec.get("end_date"))

        fee_schedule = FeeSchedule.query.filter_by(
            name=spec["fee_schedule"]["name"]
        ).first()
        if not fee_schedule:
            fee_schedule = FeeScheduleMaker().create_object_and_flush(
                spec["fee_schedule"]
            )

        fs_global_procedure = fee_schedule.fee_schedule_global_procedures[0]
        if "fertility_clinic" not in spec:
            raise ValueError("No fertility_clinic found in fixture")
        fertility_clinic = FertilityClinic.query.filter_by(
            name=spec["fertility_clinic"]["name"]
        ).first()
        if not fertility_clinic:
            clinic_spec = spec["fertility_clinic"]
            clinic_spec["fee_schedule_id"] = fee_schedule.id
            fertility_clinic = FertilityClinicMaker().create_object_and_flush(
                clinic_spec
            )
        fertility_clinic_location = fertility_clinic.locations[0]
        tp = TreatmentProcedure(
            member_id=user.id,
            reimbursement_wallet_id=wallet.id,
            reimbursement_request_category_id=category_id,
            fee_schedule_id=fee_schedule.id,
            global_procedure_id=fs_global_procedure.global_procedure_id,
            fertility_clinic_id=fertility_clinic.id,
            fertility_clinic_location_id=fertility_clinic_location.id,
            start_date=start_date,
            end_date=end_date,
            procedure_name=spec.get("procedure_name"),
            procedure_type=TreatmentProcedureType(
                spec.get("procedure_type", "MEDICAL")
            ),
            cost=spec.get("cost"),
            status=TreatmentProcedureStatus[spec.get("status", "SCHEDULED")],
            cancellation_reason=spec.get("cancellation_reason"),
            cancelled_date=datetime.datetime.strptime(
                spec["cancelled_date"], "%m/%d/%Y %H:%M:%S"
            )
            if "cancelled_date" in spec
            else None,
            completed_date=datetime.datetime.strptime(
                spec["completed_date"], "%m/%d/%Y %H:%M:%S"
            )
            if "completed_date" in spec
            else None,
        )
        db.session.add(tp)
        db.session.flush()
        tpnq = TreatmentProceduresNeedingQuestionnaires(
            treatment_procedure_id=tp.id,
        )
        db.session.add(tpnq)
        if accumulation_mapping_spec := spec.get("accumulation_mapping"):
            payer = AccumulationMappingService(db.session).get_valid_payer(
                reimbursement_wallet_id=wallet.id,
                user_id=user.id,
                procedure_type=TreatmentProcedureType(tp.procedure_type),
                effective_date=datetime.datetime(
                    year=tp.start_date.year,
                    month=tp.start_date.month,
                    day=tp.start_date.day,
                )
                if tp.start_date
                else datetime.datetime.now(datetime.timezone.utc),
            )
            AccumulationMappingMaker().create_object_and_flush(
                spec={
                    "treatment_procedure_uuid": tp.uuid,
                    "treatment_accumulation_status": "PAID",
                    "completed_at": tp.completed_date,
                    "payer_id": payer.id,
                    "deductible": accumulation_mapping_spec.get("deductible"),
                    "oop_applied": accumulation_mapping_spec.get("oop_applied"),
                }
            )

        return tp


class MemberBillMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # input
        email = spec.get("user")
        procedure_id = spec.get("treatment_procedure_id")
        cost_breakdown_id = spec.get("cost_breakdown_id")
        cost_responsibility_type = spec.get("cost_responsibility_type")
        amount = spec.get("amount")
        error_type = spec.get("error_type", None)
        status = spec.get("status", "NEW")
        payment_method = spec.get("payment_method", "OFFLINE")
        payment_method_label = spec.get("payment_method_label", "0000")

        try:
            # input validation
            # user must exist and have a wallet
            user = User.query.filter(User.email == email).first()
            if not user:
                raise ValueError(f"No user found for email: {email}.")
            if not user.reimbursement_wallets:
                raise ValueError(f"No wallets found for user: {email}, id: {user.id}.")
            wallet = user.reimbursement_wallets[0]

            # procedure may exist or may be created
            procedure = TreatmentProcedure.query.get(procedure_id)
            if not procedure:
                TreatmentProcedureMaker().create_object_and_flush(
                    {"user": email, "fertility_clinic": "Test Clinic"}
                )

            # cost breakdown may exist or may be created
            if cost_breakdown_id:
                cost_breakdown = CostBreakdown.query.get(cost_breakdown_id)
                if not cost_breakdown:
                    raise ValueError(
                        f"No cost breakdown found for id: {cost_breakdown_id}."
                    )
            elif cost_responsibility_type:
                if cost_responsibility_type == "shared":
                    member_res = amount / 2
                    employer_res = amount / 2
                elif cost_responsibility_type == "member_only":
                    member_res = amount
                    employer_res = 0
                elif cost_responsibility_type == "employer_only":
                    member_res = 0
                    employer_res = amount
                else:
                    raise ValueError("Invalid cost_responsibility_type.")
                cost_breakdown = CostBreakdown(
                    treatment_procedure_uuid=procedure.uuid,
                    wallet_id=wallet.id,
                    total_member_responsibility=member_res,
                    total_employer_responsibility=employer_res,
                    beginning_wallet_balance=0,
                    ending_wallet_balance=0,
                )
                db.session.add(cost_breakdown)
                db.session.flush()
            else:
                raise ValueError(
                    "Provide either a cost_breakdown_id or a cost_responsibility_type and amount"
                )

            if error_type and status != "FAILED":
                raise ValueError("Only FAILED status bills can have an error_type!")
        except ValueError as e:
            flash(e, "error")
            return
        # Use internal FQDN for billing.
        billing_service = BillingService(
            session=db.session,
            payment_gateway_base_url=INTERNAL_TRUST_PAYMENT_GATEWAY_URL,
        )
        bill = billing_service.create_bill(
            payor_type=billing_models.PayorType.MEMBER,
            payor_id=wallet.id,
            amount=amount,
            label=procedure.procedure_name,
            treatment_procedure_id=procedure.id,
            cost_breakdown_id=cost_breakdown.id,
            payment_method=billing_models.PaymentMethod[payment_method],
            payment_method_label=payment_method_label,
            headers=request.headers,  # type: ignore[arg-type] # Argument "headers" to "create_bill" of "BillingService" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
        )
        # Apply order of operations for status updates.
        log.info("Bill initial status.", bill=bill, status=bill.status, expected=status)
        if status == "CANCELLED":
            bill = billing_service._update_bill_status(
                bill, new_bill_status=billing_models.BillStatus.CANCELLED
            )
            log.info("Bill updated.", bill=bill, status=bill.status, expected=status)
        if status in ["PROCESSING", "FAILED", "PAID", "REFUNDED"]:
            bill = billing_service._update_bill_status(
                bill, new_bill_status=billing_models.BillStatus.PROCESSING
            )
            log.info("Bill updated.", bill=bill, status=bill.status, expected=status)
            if status in ["PAID", "REFUNDED"]:
                bill = billing_service._update_bill_status(
                    bill, new_bill_status=billing_models.BillStatus(status)
                )
                log.info(
                    "Bill updated.", bill=bill, status=bill.status, expected=status
                )
            if status == "FAILED":
                if not error_type:
                    raise ValueError("FAILED bills require an error_type")
                bill = billing_service._update_bill_status(
                    bill,
                    new_bill_status=billing_models.BillStatus(status),
                    error_type=error_type,
                )
                log.info(
                    "Bill updated.", bill=bill, status=bill.status, expected=status
                )
        final_bill = billing_service.bill_repo.update(instance=bill)
        return final_bill


class FeeScheduleMaker(_MakerBase):
    def create_object(self, spec):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        fee_schedule = FeeSchedule(name=spec.get("name"))
        db.session.add(fee_schedule)
        db.session.flush()
        for gp in spec.get("fee_schedule_global_procedures", []):
            fs_global_procedure = FeeScheduleGlobalProcedures(
                fee_schedule_id=fee_schedule.id,
                cost=gp.get("cost"),
            )
            db.session.add(fs_global_procedure)
        return fee_schedule
