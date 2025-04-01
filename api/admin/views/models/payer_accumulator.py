from __future__ import annotations

import dataclasses
import difflib
import io
from datetime import datetime
from traceback import format_exc
from typing import Optional, Type, get_args

from flask import Markup, flash, redirect, request, send_file, url_for
from flask_admin import expose
from flask_admin.contrib.sqla.filters import FilterEqual
from flask_admin.form import BaseForm
from flask_admin.model.form import InlineFormAdmin
from maven import feature_flags
from sqlalchemy import or_
from sqlalchemy.orm import aliased
from werkzeug.utils import secure_filename
from wtforms import fields, validators

from admin.views.base import (
    AdminCategory,
    AdminViewT,
    AmountDisplayCentsInDollarsField,
    MavenAuditedView,
)
from audit_log.utils import emit_audit_log_read, emit_audit_log_update
from common.global_procedures.procedure import ProcedureService
from cost_breakdown.constants import AmountType, CostBreakdownType
from cost_breakdown.cost_breakdown_processor import CostBreakdownProcessor
from cost_breakdown.models.cost_breakdown import (
    CalcConfigAudit,
    CostBreakdown,
    CostBreakdownData,
    ReimbursementRequestToCostBreakdown,
)
from cost_breakdown.utils.helpers import get_cycle_based_wallet_balance_from_credit
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureType,
)
from payer_accumulator.accumulation_report_service import AccumulationReportService
from payer_accumulator.common import PayerNameT, TreatmentAccumulationStatus
from payer_accumulator.constants import ACCUMULATION_FILE_BUCKET, PayerName
from payer_accumulator.csv.csv_accumulation_file_generator import (
    CSVAccumulationFileGenerator,
)
from payer_accumulator.errors import (
    AccumulationRegenerationError,
    NoCriticalAccumulationInfoError,
)
from payer_accumulator.file_generators.fixed_width_accumulation_file_generator import (
    FixedWidthAccumulationFileGenerator,
)
from payer_accumulator.file_handler import AccumulationFileHandler
from payer_accumulator.models.accumulation_treatment_mapping import (
    AccumulationTreatmentMapping,
)
from payer_accumulator.models.payer_accumulation_reporting import (
    PayerAccumulationReports,
    PayerReportStatus,
)
from payer_accumulator.models.payer_list import Payer
from payer_accumulator.tasks.rq_payer_accumulation_file_transfer import (
    transfer_payer_accumulation_report_file_to_data_sender,
)
from storage.connection import RoutingSQLAlchemy, db
from utils.log import logger
from utils.payments import convert_cents_to_dollars
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

log = logger(__name__)


class TreatmentRow(InlineFormAdmin):
    # InlineFormAdmin details: https://github.com/flask-admin/flask-admin/blob/master/flask_admin/model/form.py#L54

    form_columns = [
        "id",
        "treatment_procedure_uuid",
        "reimbursement_request_id",
    ]

    def postprocess_form(self, form_class):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form_class.record_type = fields.SelectField(
            description="(Reimbursement Request Creation Only)",
            choices=[enum_value.value for enum_value in TreatmentProcedureType],
        )
        # Note lack of column_formatters in inline forms
        # Not that it matters since we don't load this data from the detail (yet)
        form_class.out_of_pocket_override = AmountDisplayCentsInDollarsField(
            description="(Reimbursement Request Creation or Treatment Procedure Overrides)",
            validators=[validators.Optional()],
            allow_negative=True,
        )
        form_class.deductible_override = AmountDisplayCentsInDollarsField(
            description="(Reimbursement Request Creation or Treatment Procedure Overrides)",
            validators=[validators.Optional()],
            allow_negative=True,
        )
        form_class.hra_override = AmountDisplayCentsInDollarsField(
            description="(Reimbursement Request Creation or Treatment Procedure Overrides)",
            validators=[validators.Optional()],
            allow_negative=True,
        )
        return form_class

    def on_model_change(  # type: ignore[no-untyped-def] # Function is missing a return type annotation #type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        self,
        form,
        model: AccumulationTreatmentMapping,
        is_created=False,
    ):
        super().on_model_change(form, model, is_created)

        if is_created:
            # Prevent changes on already submitted reports.
            # But don't raise an error if we're going from one status to Submitted
            report = model.report
            if report.status == PayerReportStatus.SUBMITTED.value:
                raise ValueError(
                    f"Unable to update report<{report.id}> after file is submitted"
                )

            # Set the payer id from the parent report
            model.payer_id = model.report.payer_id
            # get the file generator for the report
            svc = AccumulationReportService()
            payer_name = svc.get_payer_name_for_report(model.report)
            file_generator = svc.get_generator_class_for_payer_name(payer_name=payer_name, organization_name=None)  # type: ignore[arg-type] # Argument "organization_name" to "get_generator_class_for_payer_name" of "AccumulationReportService" has incompatible type "None"; expected "str"
            row_type = "unknown"
            row_id = None
            try:
                if (
                    model.reimbursement_request_id is not None
                    and model.treatment_procedure_uuid is not None
                ):
                    raise NoCriticalAccumulationInfoError(
                        "Mappings must have a treatment procedure uuid or a reimbursement request id, but cannot have "
                        "both. "
                    )

                if model.reimbursement_request_id is not None:
                    log.info(
                        "Treatment mapping created using reimbursement_request_id",
                        reimbursement_request_id=model.reimbursement_request_id,
                    )
                    if not feature_flags.bool_variation(
                        "accumulation_reimbursement_request_cost_breakdown",
                        default=False,
                    ):
                        if (
                            model.deductible_override is None
                            or model.out_of_pocket_override is None
                        ):
                            raise NoCriticalAccumulationInfoError(
                                "Reimbursement requests must have deductible and oop overrides provided."
                            )

                    row_type = "reimbursement request"
                    row_id = model.reimbursement_request_id

                    # Validate the provided reimbursement request id
                    reimbursement_request: ReimbursementRequest = (
                        ReimbursementRequest.query.get(model.reimbursement_request_id)
                    )
                    if reimbursement_request is None:
                        raise NoCriticalAccumulationInfoError(
                            f"Invalid reimbursement request id {model.reimbursement_request_id} for row generation."
                        )
                    # Get the most recent cost breakdown record
                    reimbursement_cost_breakdown = (
                        CostBreakdown.query.filter_by(
                            reimbursement_request_id=reimbursement_request.id
                        )
                        .order_by(CostBreakdown.id.desc())
                        .first()
                    )
                    if (
                        feature_flags.bool_variation(
                            "accumulation_reimbursement_request_cost_breakdown",
                            default=False,
                        )
                        and reimbursement_cost_breakdown is None
                    ):
                        reimbursement_cost_breakdown = (
                            self._create_reimbursement_cost_breakdown(
                                reimbursement_request
                            )
                        )
                    if model.deductible_override is not None:
                        deductible = model.deductible_override
                    else:
                        if reimbursement_cost_breakdown is not None:
                            deductible = reimbursement_cost_breakdown.deductible
                        else:
                            raise NoCriticalAccumulationInfoError(
                                "No deductible provided in deductible override field and missing cost breakdown record"
                            )
                    if model.out_of_pocket_override is not None:
                        oop_applied = model.out_of_pocket_override
                    else:
                        if reimbursement_cost_breakdown is not None:
                            oop_applied = reimbursement_cost_breakdown.oop_applied
                        else:
                            raise NoCriticalAccumulationInfoError(
                                "No oop provided in oop override field and missing cost breakdown record"
                            )
                    if model.hra_override is not None:
                        hra_applied = model.hra_override
                    else:
                        if reimbursement_cost_breakdown is not None:
                            hra_applied = reimbursement_cost_breakdown.hra_applied
                        else:
                            raise NoCriticalAccumulationInfoError(
                                "No hra applied provided in hra override field and missing cost breakdown record"
                            )
                    # Skipping Cigna oop calculation for reversals which are negative values
                    if oop_applied >= 0:
                        oop_applied = file_generator.get_oop_to_submit(
                            deductible=deductible, oop_applied=oop_applied
                        )
                    log.info(
                        "Report will be fully regenerated rather than edited.",
                        report=report.filename,
                        payer=payer_name,
                    )
                    model.oop_applied = oop_applied
                    model.deductible = deductible
                    model.hra_applied = hra_applied
                    log.info(
                        "Saved oop_applied and deductible values to model for file regeneration.",
                        report=report.filename,
                        payer=payer_name,
                    )
                elif model.treatment_procedure_uuid is not None:
                    log.info(
                        "Treatment mapping changed using treatment_procedure_uuid",
                        treatment_procedure_uuid=model.treatment_procedure_uuid,
                    )
                    row_type = "treatment procedure"
                    row_id = model.treatment_procedure_uuid  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", variable has type "Optional[int]")
                    # Validate the provided treatment procedure uuid
                    procedure = TreatmentProcedure.query.filter(
                        TreatmentProcedure.uuid == model.treatment_procedure_uuid
                    ).one_or_none()
                    if procedure is None:
                        raise NoCriticalAccumulationInfoError(
                            f"Invalid treatment procedure uuid {model.treatment_procedure_uuid} for row generation."
                        )
                    cost_breakdown = file_generator.get_cost_breakdown(
                        treatment_procedure=procedure
                    )
                    deductible = (
                        model.deductible_override
                        if model.deductible_override is not None
                        else cost_breakdown.deductible
                    )
                    oop_applied = (
                        model.out_of_pocket_override
                        if model.out_of_pocket_override is not None
                        else cost_breakdown.oop_applied
                    )
                    hra_applied = (
                        model.hra_override
                        if model.hra_override is not None
                        else cost_breakdown.hra_applied
                    )
                    # Skipping Cigna oop calculation for reversals which are negative values
                    if oop_applied >= 0:
                        oop_applied = file_generator.get_oop_to_submit(
                            deductible=deductible, oop_applied=oop_applied
                        )
                    log.info(
                        "Report will be fully regenerated rather than edited.",
                        report=report.filename,
                        payer=payer_name,
                    )
                    model.oop_applied = oop_applied
                    model.deductible = deductible
                    model.hra_applied = hra_applied
                    log.info(
                        "Saved oop_applied and deductible values to model for file regeneration.",
                        report=report.filename,
                        payer=payer_name,
                    )
                else:
                    raise NoCriticalAccumulationInfoError(
                        "Mappings must have a treatment procedure uuid or a reimbursement request id."
                    )
            except NoCriticalAccumulationInfoError as e:
                log.error(
                    "Could not append a new PayerAccumulationReport row.",
                    model_id=model.id,
                    treatment_procedure_uuid=model.treatment_procedure_uuid,
                    reimbursment_request_id=model.reimbursement_request_id,
                    reason=format_exc(),
                )
                model.treatment_accumulation_status = (
                    TreatmentAccumulationStatus.ROW_ERROR  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TreatmentAccumulationStatus", variable has type "Optional[str]")
                )
                flash(
                    f"Could not append a new row for {row_type} {row_id}: {str(e)}",
                    "error",
                )
                raise e
            else:
                model.treatment_accumulation_status = (
                    TreatmentAccumulationStatus.PROCESSED  # type: ignore[assignment] # Incompatible types in assignment (expression has type "TreatmentAccumulationStatus", variable has type "Optional[str]")
                )

    def _update_reimbursement_request(
        self, reimbursement_request: ReimbursementRequest, cost_breakdown: CostBreakdown
    ) -> ReimbursementRequest:
        existing_description = reimbursement_request.description
        today = datetime.utcnow()
        reimbursement_request.description = (
            existing_description
            + f" Original Amount: ${convert_cents_to_dollars(reimbursement_request.amount)}."
            f" Initial cost breakdown run date via manual payer accumulation: {today}."
        )
        reimbursement_request.amount = cost_breakdown.total_employer_responsibility
        return reimbursement_request

    def _validate_reimbursement_request_required_fields(
        self, reimbursement_request: ReimbursementRequest
    ) -> str | None:
        error_message = None
        user_id = reimbursement_request.person_receiving_service_id
        if user_id is None:
            error_message = (
                "You must assign and save a user_id to the reimbursement request's "
                "person_receiving_service."
            )

        procedure_type = reimbursement_request.procedure_type
        if procedure_type is None:
            error_message = "You must assign and save a procedure_type to the reimbursement request."

        cost_sharing_category = reimbursement_request.cost_sharing_category
        if cost_sharing_category is None:
            error_message = "You must assign and save a cost_sharing_category to the reimbursement request."

        return error_message

    def _get_reimbursement_request_cost_breakdown(
        self,
        reimbursement_request: ReimbursementRequest,
        user_id: int,
        cost_sharing_category: str,
    ) -> CostBreakdown:
        cost_breakdown_processor = CostBreakdownProcessor(
            procedure_service_client=ProcedureService(internal=True)
        )
        wallet_balance_override = get_cycle_based_wallet_balance_from_credit(
            wallet=reimbursement_request.wallet,
            category_id=reimbursement_request.reimbursement_request_category_id,
            cost_credit=reimbursement_request.cost_credit,  # type: ignore[arg-type] # Argument "cost_credit" to "get_cycle_based_wallet_balance_from_credit" has incompatible type "Optional[int]"; expected "int"
            cost=reimbursement_request.amount,
        )
        cost_breakdown = (
            cost_breakdown_processor.get_cost_breakdown_for_reimbursement_request(
                reimbursement_request=reimbursement_request,
                user_id=user_id,
                cost_sharing_category=cost_sharing_category,
                wallet_balance_override=wallet_balance_override,
            )
        )
        return cost_breakdown

    def _create_cost_breakdown_from_reimbursement_request(
        self,
        cost_breakdown_data: CostBreakdownData,
        reimbursement_request: ReimbursementRequest,
        calc_config: CalcConfigAudit,
    ) -> CostBreakdown:
        cost_breakdown = CostBreakdown(
            wallet_id=reimbursement_request.reimbursement_wallet_id,
            member_id=reimbursement_request.person_receiving_service_id,
            reimbursement_request_id=reimbursement_request.id,
            total_member_responsibility=cost_breakdown_data.total_member_responsibility,
            total_employer_responsibility=cost_breakdown_data.total_employer_responsibility,
            beginning_wallet_balance=cost_breakdown_data.beginning_wallet_balance,
            ending_wallet_balance=cost_breakdown_data.ending_wallet_balance,
            deductible=cost_breakdown_data.deductible,
            deductible_remaining=cost_breakdown_data.deductible_remaining,
            family_deductible_remaining=cost_breakdown_data.family_deductible_remaining,
            coinsurance=cost_breakdown_data.coinsurance,
            copay=cost_breakdown_data.copay,
            oop_applied=cost_breakdown_data.oop_applied,
            oop_remaining=cost_breakdown_data.oop_remaining,
            family_oop_remaining=cost_breakdown_data.family_oop_remaining,
            overage_amount=cost_breakdown_data.overage_amount,
            amount_type=AmountType(cost_breakdown_data.amount_type),
            cost_breakdown_type=CostBreakdownType(
                cost_breakdown_data.cost_breakdown_type
            ),
            rte_transaction_id=cost_breakdown_data.rte_transaction_id,
            calc_config=dataclasses.asdict(calc_config) if calc_config else None,
        )
        return cost_breakdown

    def _create_reimbursement_cost_breakdown(
        self,
        reimbursement_request: ReimbursementRequest,
    ) -> CostBreakdown:
        existing_reimbursement_to_cost_breakdown: (
            ReimbursementRequestToCostBreakdown
        ) = ReimbursementRequestToCostBreakdown.query.filter_by(
            reimbursement_request_id=reimbursement_request.id
        ).one_or_none()
        if existing_reimbursement_to_cost_breakdown:
            raise NoCriticalAccumulationInfoError(
                f"Invalid reimbursement request {reimbursement_request.id} for row generation. "
                f"ReimbursementRequestToCostBreakdown "
                f"record exists. Use associated Treatment Procedure instead."
            )

        log.info(
            "No cost breakdown record found. Creating record for payer accumulation values.",
            reimbursement_request_id=str(reimbursement_request.id),
        )

        # Validate input
        error_message = self._validate_reimbursement_request_required_fields(
            reimbursement_request=reimbursement_request
        )
        if error_message:
            raise NoCriticalAccumulationInfoError(error_message)

        # Process valid input
        try:
            reimbursement_cost_breakdown = self._get_reimbursement_request_cost_breakdown(
                reimbursement_request=reimbursement_request,
                user_id=reimbursement_request.person_receiving_service_id,  # type: ignore[arg-type] # Argument "user_id" to "_get_reimbursement_request_cost_breakdown" of "TreatmentRow" has incompatible type "Optional[int]"; expected "int"
                cost_sharing_category=reimbursement_request.cost_sharing_category,  # type: ignore[arg-type] # Argument "cost_sharing_category" to "_get_reimbursement_request_cost_breakdown" of "TreatmentRow" has incompatible type "Optional[str]"; expected "str"
            )

            # Update the reimbursement request amount for Alegeus and record keeping
            reimbursement_request = self._update_reimbursement_request(
                reimbursement_request=reimbursement_request,
                cost_breakdown=reimbursement_cost_breakdown,
            )
        except Exception as e:
            raise NoCriticalAccumulationInfoError(
                f"Failed to calculate a cost breakdown. Error: {e}"
            )
        try:
            log.info(
                "Saving reimbursement_cost_breakdown and reimbursement_request changes to the DB",
                reimbursement_request_id=reimbursement_request.id,
            )
            db.session.add(reimbursement_cost_breakdown)
            db.session.add(reimbursement_request)
            db.session.commit()
            return reimbursement_cost_breakdown
        except Exception as e:
            raise NoCriticalAccumulationInfoError(
                "Failed to persist cost breakdown or reimbursement reqeust into database."
                f" Error: {str(e)}"
            )


class PayerAccumulationReportsView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:payer-accumulation-reports"
    edit_permission = "edit:payer-accumulation-reports"
    delete_permission = "delete:payer-accumulation-reports"
    read_permission = "read:payer-accumulation-reports"

    edit_template = "payer_accumulation_report_edit_template.html"
    column_list = (
        "id",
        "payer_name",
        "filename",
        "report_date",
        "status",
        "created_at",
        "modified_at",
    )
    column_filters = (
        "payer_id",
        "report_date",
        "status",
    )
    form_columns = (
        "payer_id",
        "filename",
        "report_date",
        "status",
    )
    form_edit_rules = (
        "payer_id",
        "filename",
        "report_date",
        "status",
        "treatment_mappings",
    )
    inline_models = [TreatmentRow(AccumulationTreatmentMapping)]

    def on_form_prefill(self, form, id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        svc = AccumulationReportService()
        report = svc.get_report_by_id(id)
        report_dict = svc.get_structured_data_for_report(report)
        report_json = svc.get_json_for_report(report)
        self._template_args["report_json"] = report_json

        # Do a check for each report detail row in luminare, and make sure the network field has a value.
        # Show a message that tells the admin user that we require the tier (1|2) in the network field
        if report.payer_name == PayerName.LUMINARE:
            missing_network_row_ids = []
            for report_row in report_dict:
                if "network" in report_row and not report_row["network"]:
                    missing_network_row_ids.append(
                        report_row["unique_record_identifier"]
                    )

            if missing_network_row_ids:
                flash(
                    f"Luminare accumulation report is missing tier value (1|2) in the network field. Please manually update this value below for rows {missing_network_row_ids}"
                )

    def edit_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        form = super().edit_form(obj=obj)
        return form

    def get_create_form(self, obj=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        class PayerAccumulationReportCreateForm(BaseForm):
            payer = fields.SelectField(
                choices=[(payer, payer) for payer in get_args(PayerNameT)]
            )

        return PayerAccumulationReportCreateForm

    def create_model(self, form):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        # Create and upload report file on report creation
        payer_name = form.payer.data
        svc = AccumulationReportService()
        file_generator = svc.get_generator_class_for_payer_name(payer_name)
        report = file_generator.create_new_accumulation_report(
            payer_id=file_generator.payer_id,
            file_name=file_generator.file_name,
            run_time=file_generator.run_time,
        )
        buffer = io.StringIO()
        buffer.write(file_generator._generate_header())
        buffer.write(file_generator._generate_trailer(0, 0))
        db.session.commit()

        file_handler = AccumulationFileHandler()
        file_handler.upload_file(
            content=buffer,
            filename=report.file_path(),
            bucket=ACCUMULATION_FILE_BUCKET,
        )

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model.status == PayerReportStatus.SUBMITTED.value:
            raise ValueError(
                f"Unable to update report<{model.id}> after file is submitted"
            )

        # first perform any updates we need to the model
        super().on_model_change(form, model, is_created)
        db.session.commit()

        if form.treatment_mappings:
            # then get the refreshed model
            refreshed_model = PayerAccumulationReports.query.get(model.id)
            form_treatment_mapping_ids = set(
                int(treatment_mapping.get("id"))
                for treatment_mapping in form.treatment_mappings.data
                if treatment_mapping.get("id")
            )
            model_treatment_mapping_ids = set(
                treatment_mapping.id
                for treatment_mapping in refreshed_model.treatment_mappings
            )
            # at this point, form_treatment_mapping_ids consists of the mappings before any add/delete changes were made
            # and model_treatment_mapping_ids consists of the mappings after add/delete changes

            if form_treatment_mapping_ids != model_treatment_mapping_ids:
                # report may need regeneration (mapping deleted or added)
                svc = AccumulationReportService()
                payer_name = svc.get_payer_name_for_report(model)
                file_generator = svc.get_generator_class_for_payer_name(
                    payer_name=payer_name
                )
                if (
                    form_treatment_mapping_ids - model_treatment_mapping_ids
                ):  # mapping deleted
                    log_message = "AccumulationTreatmentMapping record was deleted. Regenerating accumulation report with updated DB data."
                    flash_message = "AccumulationTreatmentMapping(s) deleted and Payer Accumulation Report regenerated"
                # this is triggered after the in-line on_model_change so the treatment mapping work is done
                elif (
                    model_treatment_mapping_ids - form_treatment_mapping_ids
                ):  # mapping added
                    log_message = "AccumulationTreatmentMapping record was added. Regenerating accumulation report with updated DB data."
                    flash_message = "AccumulationTreatmentMapping(s) added and Payer Accumulation Report regenerated"
                else:
                    # no changes to mappings, so no regeneration needed
                    return

                log.info(
                    log_message, report=model.filename, payer_name=model.payer_name
                )
                try:
                    svc.regenerate_and_overwrite_report(
                        file_generator=file_generator, report=model
                    )
                    flash(flash_message, "success")
                except Exception as e:
                    raise AccumulationRegenerationError(
                        f"Failed to regenerate accumulation: {e}",
                    )

    @expose("/download", methods=("POST",))
    def download_payer_accumulation_report(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        report_id = request.form.get("payer_accumulation_report_id")
        svc = AccumulationReportService()
        report = svc.get_report_by_id(report_id)
        emit_audit_log_read(report)
        report_data = svc.get_raw_data_for_report(report)

        # Convert report data to bytes to enable the download
        fp = io.BytesIO()
        fp.write(report_data.encode())
        fp.seek(0)

        # send file = the download
        filename = secure_filename(report.file_path())
        return send_file(
            # type: ignore[call-arg] # Unexpected keyword argument "download_name" for "send_file"
            fp,
            mimetype="text/plain",
            as_attachment=True,
            download_name=filename,
        )

    @expose("/submit", methods=("POST",))
    def submit_payer_accumulation_report_to_payer(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        report_id = request.form.get("payer_accumulation_report_id")
        transfer_payer_accumulation_report_file_to_data_sender.delay(
            report_id, team_ns="payments_platform"
        )
        flash(
            f"Submitted report<{report_id}>. "
            f"Please refresh to check the report status for submission success or failure."
        )
        return redirect(
            url_for("payeraccumulationreports.edit_view", id=report_id),
        )

    @expose("/overwrite", methods=("POST",))
    def overwrite_payer_accumulation_report(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        report_id = request.form.get("payer_accumulation_report_id")
        new_report_json = request.form.get("report_json")

        svc = AccumulationReportService()
        report = svc.get_report_by_id(report_id)
        if not report_id or not new_report_json or not report:
            flash("Invalid Request: Missing form values")
            return redirect(url_for("payeraccumulationreports.edit_view", id=report_id))

        if report.status == PayerReportStatus.SUBMITTED:
            flash(f"Unable to update report<{report.id}> after file is submitted")
            return redirect(url_for("payeraccumulationreports.edit_view", id=report_id))

        # validates json and overwrites file
        try:
            emit_audit_log_update(report)
            svc.overwrite_report_with_json(report=report, report_json=new_report_json)
            flash(f"Successfully updated Report<{report_id}>")
        except ValueError as e:
            flash(f"Failed to update report: {str(e)}")
        return redirect(
            url_for("payeraccumulationreports.edit_view", id=report_id),
        )

    @expose("/diff", methods=("POST",))
    def payer_accumulation_report_diff(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        def process_json(raw_json):  # type: ignore[no-untyped-def] # Function is missing a type annotation
            return raw_json.splitlines(keepends=False)

        report_id = request.form.get("payer_accumulation_report_id")
        new_report_json = request.form.get("report_json")
        svc = AccumulationReportService()
        existing_report = svc.get_report_by_id(report_id)

        existing_report_json = svc.get_json_for_report(report=existing_report)
        diff = [
            diff_line
            for diff_line in difflib.Differ().compare(
                a=process_json(existing_report_json),
                b=process_json(new_report_json),
            )
            if diff_line.startswith(("- ", "+ "))
        ]
        return "\n".join(diff)

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            PayerAccumulationReports,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


class MemberIDFilterAccumulationTreatmentMapping(FilterEqual):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        AliasedTreatmentProcedure = aliased(TreatmentProcedure)
        AliasedReimbursementRequest = aliased(ReimbursementRequest)

        return (
            query.outerjoin(
                AliasedTreatmentProcedure,
                AliasedTreatmentProcedure.uuid
                == AccumulationTreatmentMapping.treatment_procedure_uuid,
            )
            .outerjoin(
                AliasedReimbursementRequest,
                AliasedReimbursementRequest.id
                == AccumulationTreatmentMapping.reimbursement_request_id,
            )
            .outerjoin(
                ReimbursementWalletUsers,
                ReimbursementWalletUsers.reimbursement_wallet_id
                == AliasedReimbursementRequest.reimbursement_wallet_id,
            )
            .filter(
                or_(
                    AliasedTreatmentProcedure.member_id == value,
                    ReimbursementWalletUsers.user_id == value,
                )
            )
        )


class WalletIDFilterAccumulationTreatmentMapping(FilterEqual):
    def apply(self, query, value, alias=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        return (
            query.outerjoin(
                TreatmentProcedure,
                TreatmentProcedure.uuid
                == AccumulationTreatmentMapping.treatment_procedure_uuid,
            )
            .outerjoin(
                ReimbursementRequest,
                ReimbursementRequest.id
                == AccumulationTreatmentMapping.reimbursement_request_id,
            )
            .filter(
                or_(
                    TreatmentProcedure.reimbursement_wallet_id == value,
                    ReimbursementRequest.reimbursement_wallet_id == value,
                )
            )
        )


class AccumulationTreatmentMappingView(MavenAuditedView):
    required_capability = "admin_wallet_tools"  # type: ignore[assignment] # Incompatible types in assignment (expression has type "str", base class "AdminAuth" defined the type as "None")

    create_permission = "create:accumulation-treatment-mapping"
    edit_permission = "edit:accumulation-treatment-mapping"
    delete_permission = "delete:accumulation-treatment-mapping"
    read_permission = "read:accumulation-treatment-mapping"

    column_list = (
        "id",
        "accumulation_unique_id",
        "accumulation_transaction_id",
        "treatment_procedure_uuid",
        "reimbursement_request_id",
        "report",
        "treatment_accumulation_status",
        "row_error_reason",
        "response_code",
        "deductible",
        "oop_applied",
        "is_refund",
        "hra_applied",
        "payer_id",
        "completed_at",
        "created_at",
        "modified_at",
    )
    column_filters = (
        "id",
        "payer_id",
        "accumulation_unique_id",
        "accumulation_transaction_id",
        "treatment_procedure_uuid",
        "reimbursement_request_id",
        "report_id",
        "treatment_accumulation_status",
        MemberIDFilterAccumulationTreatmentMapping(None, "Member ID"),
        WalletIDFilterAccumulationTreatmentMapping(None, "Wallet ID"),
    )
    column_formatters = {
        "response_code": lambda view, context, model, p: response_code_formatter(
            model.payer_id, model.response_code
        )
        if model.response_code
        else None
    }

    # for now, transaction id should be set in the file generation, not here.
    form_excluded_columns = (
        "accumulation_unique_id",
        "accumulation_transaction_id",
        "created_at",
        "modified_at",
    )

    form_widget_args = {
        "is_refund": {"disabled": True},
    }

    def on_model_change(self, form, model, is_created: bool):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model.report and model.report.status == PayerReportStatus.SUBMITTED:
            raise ValueError(
                f"Unable to update report<{model.report.id}> after file is submitted"
            )

        if (
            form.treatment_accumulation_status.data
            == TreatmentAccumulationStatus.PAID.value
        ):
            model.is_refund = False
        elif (
            form.treatment_accumulation_status.data
            == TreatmentAccumulationStatus.REFUNDED.value
        ):
            model.is_refund = True

        super().on_model_change(form, model, is_created)

    def on_model_delete(self, model):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        if model.report and model.report.status == PayerReportStatus.SUBMITTED:
            raise ValueError(
                f"Unable to update report<{model.report.id}> after file is submitted"
            )

    @classmethod
    def factory(  # type: ignore[no-untyped-def] # Function is missing a type annotation for one or more arguments
        cls: Type[AdminViewT],
        *,
        session: RoutingSQLAlchemy = None,  # type: ignore[assignment] # Incompatible default for argument "session" (default has type "None", argument has type "RoutingSQLAlchemy")
        category: AdminCategory = None,  # type: ignore[assignment] # Incompatible default for argument "category" (default has type "None", argument has type "AdminCategory")
        name: str = None,  # type: ignore[assignment] # Incompatible default for argument "name" (default has type "None", argument has type "str")
        endpoint: str = None,  # type: ignore[assignment] # Incompatible default for argument "endpoint" (default has type "None", argument has type "str")
        **kwargs,
    ) -> AdminViewT:
        return cls(  # type: ignore[call-arg] # Too many arguments for "object" #type: ignore[call-arg] # Unexpected keyword argument "category" for "object" #type: ignore[call-arg] # Unexpected keyword argument "name" for "object" #type: ignore[call-arg] # Unexpected keyword argument "endpoint" for "object"
            AccumulationTreatmentMapping,
            session or db.session,
            category=category,
            name=name,
            endpoint=endpoint,
            **kwargs,
        )


def response_code_formatter(
    payer_id: int, response_code: Optional[str]
) -> Optional[str]:
    if response_code:  # Not none, empty, etc
        try:
            payer = Payer.query.get(payer_id)
            generator = AccumulationReportService.get_generator_class_for_payer_name(
                payer.payer_name.value
            )
            # only fixed-width files currently support response codes
            if isinstance(generator, FixedWidthAccumulationFileGenerator):
                response_reason = generator.get_response_reason_for_code(response_code)
                if response_reason:
                    return f"{response_reason} ({response_code})"
            elif isinstance(generator, CSVAccumulationFileGenerator):
                # return response code as HTML to render display formatting
                return Markup(response_code)
        except Exception as e:
            log.error("Exception formatting response code", error=e)
            # fall back to returning the code
    return response_code
