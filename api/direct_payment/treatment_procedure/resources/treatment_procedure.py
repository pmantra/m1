from __future__ import annotations

import flask
from flask import request
from flask_restful import abort
from marshmallow import ValidationError

from authn.models.user import User
from common import stats
from direct_payment.clinic.models.clinic import FertilityClinic
from direct_payment.clinic.resources.clinic_auth import ClinicAuthorizedResource
from direct_payment.clinic.schemas.procedures import FertilityClinicProceduresSchema
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureStatus,
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.repository import treatment_procedure
from direct_payment.treatment_procedure.schemas.treatment_procedure import (
    TreatmentProcedurePUTRequestSchema,
    TreatmentProcedureSchema,
    TreatmentProceduresPOSTRequestSchema,
)
from direct_payment.treatment_procedure.utils.procedure_helpers import (
    get_mapped_global_procedures,
    get_member_procedures,
    process_partial_procedure,
    trigger_cost_breakdown,
    validate_edit_procedure,
    validate_fc_user,
    validate_fc_user_new_procedure,
    validate_procedures,
)
from storage.connection import db
from utils.log import logger
from wallet.models.constants import PatientInfertilityDiagnosis
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.services.member_lookup import MemberLookupService

log = logger(__name__)
METRIC_PREFIX = "api.direct_payment.treatment_procedure.resources.treatment_procedure"


class MemberLookupMixin:
    def __init__(self) -> None:
        self.member_lookup_service = MemberLookupService()


class TreatmentProcedureResource(ClinicAuthorizedResource, MemberLookupMixin):
    def __init__(self) -> None:
        super().__init__()
        self.treatment_procedure_repository = (
            treatment_procedure.TreatmentProcedureRepository()
        )

    def get(self, treatment_procedure_id: int) -> dict:
        treatment_procedure_result = self.treatment_procedure_repository.read(
            treatment_procedure_id=treatment_procedure_id
        )
        schema = TreatmentProcedureSchema()
        return schema.dump(treatment_procedure_result)

    def put(self, treatment_procedure_id: int) -> dict:
        fc_user = self.user
        request_schema = TreatmentProcedurePUTRequestSchema()

        try:
            args = request_schema.load(request.json if request.is_json else {})
        except ValidationError as e:
            abort(400, message=str("; ".join(e.messages)))

        try:
            treatment_procedure = self.treatment_procedure_repository.read(
                treatment_procedure_id=treatment_procedure_id
            )
            validate_fc_user(fc_user, {treatment_procedure.fertility_clinic_id})
            validate_edit_procedure(
                args,
                treatment_procedure,
            )
        except ValidationError as e:
            abort(400, message=str("; ".join(e.messages)))

        log.info(
            "Treatment Procedure update initiated",
            updated_by_user_id=str(fc_user.id),
            treatment_procedure_id=str(treatment_procedure.id),
            treatment_procedure_iuud=str(treatment_procedure.uuid),
        )

        if args.get("status") == TreatmentProcedureStatus.PARTIALLY_COMPLETED.value:
            try:
                updated_procedure = process_partial_procedure(
                    treatment_procedure=treatment_procedure,
                    procedure_args=args,
                    repository=self.treatment_procedure_repository,
                    headers=request.headers,  # type: ignore[arg-type] # Argument "headers" to "process_partial_procedure" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
                )
            except ValidationError as e:
                abort(400, message=str("; ".join(e.messages)))
        else:
            status = (
                getattr(TreatmentProcedureStatus, args.get("status"), None)
                if args.get("status")
                else None
            )

            if start_date_arg := args.get("start_date"):
                wallet = ReimbursementWallet.query.get(
                    treatment_procedure.reimbursement_wallet_id
                )
                if self.member_lookup_service.fails_member_health_plan_check(
                    treatment_procedure.member_id,
                    wallet,
                    start_date_arg,
                ):
                    stats.increment(
                        metric_name=f"{METRIC_PREFIX}.put.missing_health_plan_information",
                        pod_name=stats.PodNames.BENEFITS_EXP,
                        tags=[
                            "success:false",
                            "error_cause:resource_post",
                        ],
                    )
                    msg = "Could not find member health plan for procedure start date when updating a procedure."
                    log.info(
                        msg,
                        id_treatment_procedure=str(treatment_procedure_id),
                        user_id=str(
                            treatment_procedure.member_id,
                        ),
                        wallet_id=str(treatment_procedure.reimbursement_wallet_id),
                        effective_date=str(args.get("start_date")),
                    )
                    abort(400, message=msg)
            updated_procedure = self.treatment_procedure_repository.update(
                treatment_procedure_id=treatment_procedure_id,
                start_date=args.get("start_date"),
                end_date=args.get("end_date"),
                status=status,
            )

        # run cost breakdown asynchronously
        success = trigger_cost_breakdown(
            treatment_procedure=updated_procedure, new_procedure=False
        )
        if not success:
            log.error(
                "Cost breakdown on update not successful",
                treatment_procedure_id=updated_procedure.id,
            )

        response_schema = TreatmentProcedureSchema()
        log.info(
            "Treatment Procedure update complete",
            updated_by_user_id=str(fc_user.id),
            treatment_procedure_id=str(updated_procedure.id),
            treatment_procedure_iuud=str(updated_procedure.uuid),
        )
        return response_schema.dump(updated_procedure)


class TreatmentProceduresResource(ClinicAuthorizedResource, MemberLookupMixin):
    def __init__(self) -> None:
        super().__init__()
        self.treatment_procedure_repository = (
            treatment_procedure.TreatmentProcedureRepository()
        )

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        fc_user = self.user
        request_schema = TreatmentProceduresPOSTRequestSchema()

        try:
            args = request_schema.load(request.json if request.is_json else {})
        except ValidationError as e:
            abort(400, message="; ".join(e.messages))

        try:
            validate_fc_user_new_procedure(fc_user, args["procedures"])
            validate_procedures(
                args["procedures"],
                headers=request.headers,  # type: ignore[arg-type] # Argument "headers" to "validate_procedures" has incompatible type "EnvironHeaders"; expected "Optional[Mapping[str, str]]"
            )
        except ValidationError as e:
            abort(400, message="; ".join(e.messages))

        mapped_global_procedures = get_mapped_global_procedures(args["procedures"])
        global_procedures_schema = FertilityClinicProceduresSchema()
        treatment_procedures_schema = TreatmentProcedureSchema(
            exclude=("global_procedure",)
        )
        procedures = []
        wallet_repo = ReimbursementWalletRepository(session=db.session)
        for procedure in args["procedures"]:
            member_id = procedure["member_id"]  # this is user.id
            wallet = wallet_repo.get_current_wallet_by_active_user_id(user_id=member_id)
            if not wallet:
                abort(400, message="Could not find wallet")
                return  # this no-op return handles the type errors for wallet further down
            direct_payment_category = wallet.get_direct_payment_category
            if not direct_payment_category:
                abort(400, message="Could not find wallet direct payment category")
            assert direct_payment_category is not None  # make mypy happy
            # Block treatment procedure creation if no payment method is onfile
            if not (
                self.member_lookup_service.is_payment_method_on_file(
                    payments_customer_id=wallet.payments_customer_id,
                    headers=request.headers,  # type: ignore[arg-type] # Argument "headers" to "is_payment_method_on_file" of "MemberLookupService" has incompatible type "EnvironHeaders"; expected "Mapping[str, str]"
                )
            ):
                log.info(
                    "Treatment procedure creation attempted with no payment method on file",
                    member_id=str(member_id),
                )
                abort(400, message="No payment method is on file")

            fertility_clinic_id = procedure["fertility_clinic_id"]
            clinic = FertilityClinic.query.get(fertility_clinic_id)
            fee_schedule_id = clinic.fee_schedule_id

            global_procedure = mapped_global_procedures.get(
                procedure["global_procedure_id"]
            )
            if not global_procedure:
                stats.increment(
                    metric_name=f"{METRIC_PREFIX}.procedure_service",
                    pod_name=stats.PodNames.BENEFITS_EXP,
                    tags=[
                        "error:true",
                        "error_cause:resource_post",
                    ],
                )
                abort(
                    400, message="Could not find reimbursement wallet global procedure"
                )
            if self.member_lookup_service.fails_member_health_plan_check(
                member_id, wallet, procedure["start_date"]
            ):
                stats.increment(
                    metric_name=f"{METRIC_PREFIX}.post.missing_health_plan_information",
                    pod_name=stats.PodNames.BENEFITS_EXP,
                    tags=[
                        "success:false",
                        "error_cause:resource_post",
                    ],
                )
                msg = "Could not find member health plan for procedure start date."
                log.info(
                    msg,
                    user_id=str(member_id),
                    wallet_id=str(wallet.id),
                    effective_date=str(procedure["start_date"]),
                )
                abort(400, message=msg)

            infertility_diagnosis = (
                getattr(
                    PatientInfertilityDiagnosis,
                    procedure.get("infertility_diagnosis"),
                    None,
                )
                if procedure.get("infertility_diagnosis")
                else None
            )

            new_procedure = self.treatment_procedure_repository.create(
                member_id=procedure["member_id"],
                infertility_diagnosis=infertility_diagnosis,
                reimbursement_wallet_id=wallet.id,
                reimbursement_request_category_id=direct_payment_category.id,
                fee_schedule_id=fee_schedule_id,
                global_procedure_id=global_procedure["id"],  # type: ignore[index] # Value of type "Optional[Any]" is not indexable
                global_procedure_name=global_procedure["name"],  # type: ignore[index] # Value of type "Optional[Any]" is not indexable
                global_procedure_credits=global_procedure["credits"],  # type: ignore[index] # Value of type "Optional[Any]" is not indexable
                fertility_clinic_id=procedure["fertility_clinic_id"],
                fertility_clinic_location_id=procedure["fertility_clinic_location_id"],
                start_date=procedure["start_date"],
                end_date=procedure.get("end_date"),
                status=TreatmentProcedureStatus.SCHEDULED,
                global_procedure_type=TreatmentProcedureType.MEDICAL,
            )

            # run cost breakdown asynchronously
            success = trigger_cost_breakdown(
                treatment_procedure=new_procedure, new_procedure=True
            )
            if not success:
                log.error(
                    "Cost breakdown on create not successful",
                    treatment_procedure_id=new_procedure.id,
                )
            formatted_procedure = treatment_procedures_schema.dump(new_procedure)
            formatted_procedure.update(
                {"global_procedure": global_procedures_schema.dump(global_procedure)}
            )
            procedures.append(formatted_procedure)

        return flask.jsonify({"procedures": procedures})


class TreatmentProcedureMemberResource(ClinicAuthorizedResource):
    def __init__(self) -> None:
        super().__init__()

    def get(self, member_id: int):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        fc_user = self.user
        member = User.query.get(member_id)
        if not member:
            abort(404, message="A member could not be found for the given information.")
        updated_schemas = []
        member_procedures = get_member_procedures(fc_user, member_id)
        if member_procedures:
            mapped_global_procedures = get_mapped_global_procedures(member_procedures)
            if not mapped_global_procedures:
                abort(404, message="Global Procedures not found.")

            treatment_procedures_schema = TreatmentProcedureSchema(
                exclude=("global_procedure", "partial_procedure")
            )
            global_procedures_schema = FertilityClinicProceduresSchema()

            for member_procedure in member_procedures:
                global_procedure = mapped_global_procedures.get(
                    member_procedure.global_procedure_id
                )
                if not global_procedure:
                    abort(
                        404,
                        message="Could not find Global Procedure for Treatment Procedure.",
                    )

                returned_procedure = treatment_procedures_schema.dump(member_procedure)
                returned_procedure.update(
                    {
                        "global_procedure": global_procedures_schema.dump(
                            global_procedure
                        )
                    }
                )
                returned_partial = None
                if member_procedure.partial_procedure:
                    partial_procedure = member_procedure.partial_procedure
                    partial_global_procedure = mapped_global_procedures.get(
                        partial_procedure.global_procedure_id
                    )
                    if not partial_global_procedure:
                        abort(
                            404,
                            message="Could not find Global Procedure for Partial Treatment Procedure.",
                        )

                    returned_partial = treatment_procedures_schema.dump(
                        partial_procedure
                    )
                    returned_partial.update(
                        {
                            "global_procedure": global_procedures_schema.dump(
                                partial_global_procedure
                            )
                        }
                    )

                returned_procedure.update({"partial_procedure": returned_partial})
                updated_schemas.append(returned_procedure)

        return flask.jsonify({"procedures": updated_schemas})
