from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from json import JSONEncoder
from traceback import format_exc
from typing import Any, Optional
from uuid import UUID

from common import stats
from direct_payment.billing.billing_service import (
    BillingService,
    from_employer_bill_create_clinic_bill_and_process_with_billing_service,
)
from direct_payment.billing.models import Bill, BillStatus
from direct_payment.billing.tasks.rq_job_create_bill import format_cents_to_usd_str
from direct_payment.invoicing.invoicing_service import DirectPaymentInvoicingService
from direct_payment.invoicing.models import (
    BillInformation,
    BillingReport,
    BillType,
    DirectPaymentInvoice,
    DirectPaymentInvoiceBillAllocation,
    OrganizationInvoicingSettings,
    Process,
)
from direct_payment.invoicing.utils import generate_user_friendly_report_cadence
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedureType,
)
from direct_payment.treatment_procedure.treatment_procedure_service import (
    TreatmentProcedureService,
)
from models.enterprise import Organization
from storage import connection
from utils.log import logger
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)

log = logger(__name__)

DEFAULT_BILL_PROCESSING_DELAY_DAYS = 14
DEFAULT_BILL_CUTOFF_AT_BUFFER_DAYS = 2


class DirectPaymentInvoicingClient:
    def __init__(self, payment_gateway_base_url: Optional[str] = None) -> None:
        self._session = connection.db.session
        self._invoicing_service = DirectPaymentInvoicingService(session=self._session)
        self._billing_service = BillingService(
            session=self._session,
            payment_gateway_base_url=payment_gateway_base_url,
            is_in_uow=True,
        )
        self._treatment_procedure_service = TreatmentProcedureService(
            session=self._session
        )

    def get_all_invoice_settings(self) -> list[OrganizationInvoicingSettings]:
        return self._invoicing_service.get_all_invoice_setting()

    # Return invoice bills which are changed from NEW to PROCESSING status
    def process_invoice_bills(self) -> tuple[list[Bill], list[Bill]]:
        bills_to_process: list[
            Bill
        ] = self._invoicing_service.get_invoice_bills_ready_to_process()
        log.info(
            f"Start to process {len(bills_to_process)} bill(s) in process_invoice_bills"
        )

        finished_bills = []
        exception_bills = []

        for bill in bills_to_process:
            try:
                log.info(
                    "Start processing bill in process_invoice_bills", bill_id=bill.id
                )
                processed_bill = self._billing_service.set_new_bill_to_processing(bill)

                # if the employer bill amount is < the min allowed by stripe> - it will be PAID, so immediately
                # spawn out the clinic bill. This is not a refund flow and so we do not check for
                # Refunded Bill status
                if processed_bill.status == BillStatus.PAID:
                    log.info(
                        "Creating clinic bill from employer bill in process_invoice_bills",
                        bill_uuid=str(bill.uuid),
                        bill_amount=bill.amount,
                    )
                    if processed_bill.id is not None:
                        from_employer_bill_create_clinic_bill_and_process_with_billing_service(
                            emp_bill_id=processed_bill.id,
                            billing_service=self._billing_service,
                        )

                finished_bills.append(processed_bill)
                log.info(
                    "Finish processing bill in process_invoice_bills", bill_id=bill.id
                )
            except Exception as e:
                log.error(
                    "Encounter errors in process_invoice_bills",
                    bill_id=bill.id,
                    bill_status=bill.status,
                    error_msg=str(e),
                )
                exception_bills.append(bill)

        self._record_process_invoice_bills_stat(finished_bills, exception_bills)

        return finished_bills, exception_bills

    @staticmethod
    def _record_process_invoice_bills_stat(
        finished_bills: list[Bill], exception_bills: list[Bill]
    ) -> None:
        num_of_finished_processing_bills = sum(
            1 for bill in finished_bills if bill.status == BillStatus.PROCESSING
        )
        num_of_finished_non_processing_bills = (
            len(finished_bills) - num_of_finished_processing_bills
        )

        log.info(
            "Finish the process_invoice_bills job",
            num_of_finished_processing_bills=num_of_finished_processing_bills,
            num_of_finished_non_processing_bills=num_of_finished_non_processing_bills,
            num_of_exception_bills=len(exception_bills),
        )

        stats.increment(
            metric_name="direct_payment.invoicing.invoice_bill_processing.finished_processing_bills",
            pod_name=stats.PodNames.BENEFITS_EXP,
            metric_value=num_of_finished_processing_bills,
        )

        stats.increment(
            metric_name="direct_payment.invoicing.invoice_bill_processing.finished_non_processing_bills",
            pod_name=stats.PodNames.BENEFITS_EXP,
            metric_value=num_of_finished_non_processing_bills,
        )

        stats.increment(
            metric_name="direct_payment.invoicing.invoice_bill_processing.exception_bills",
            pod_name=stats.PodNames.BENEFITS_EXP,
            metric_value=len(exception_bills),
        )

    def get_invoice_by_id(self, invoice_id: int) -> Optional[DirectPaymentInvoice]:
        return self._invoicing_service.get_invoice(invoice_id=invoice_id)

    def create_invoice_setting(
        self,
        *,
        organization_id: int,
        created_by_user_id: int,
        invoicing_active_at: Optional[datetime] = None,
        invoice_cadence: Optional[str] = None,
        bill_processing_delay_days: int = DEFAULT_BILL_PROCESSING_DELAY_DAYS,
        bill_cutoff_at_buffer_days: int = DEFAULT_BILL_CUTOFF_AT_BUFFER_DAYS,
    ) -> OrganizationInvoicingSettings | str:
        log.info(
            "Start creating org invoicing setting",
            organization_id=organization_id,
            created_by_user_id=str(created_by_user_id),
        )

        try:
            organization_invoicing_setting: OrganizationInvoicingSettings = (
                OrganizationInvoicingSettings(
                    uuid=uuid.uuid4(),
                    organization_id=organization_id,
                    created_by_user_id=created_by_user_id,
                    updated_by_user_id=created_by_user_id,
                    invoicing_active_at=invoicing_active_at,
                    invoice_cadence=invoice_cadence,
                    bill_processing_delay_days=bill_processing_delay_days,
                    bill_cutoff_at_buffer_days=bill_cutoff_at_buffer_days,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
            )
            new_invoicing_setting = self._invoicing_service.create_invoice_setting(
                organization_invoicing_setting=organization_invoicing_setting
            )
            self._session.commit()
            return new_invoicing_setting
        except Exception as e:
            log.error("Error in creating org invoicing setting", error_msg=str(e))
            return str(e)

    def update_invoicing_setting(
        self,
        *,
        existing_invoicing_setting: OrganizationInvoicingSettings,
        updated_by_user_id: int,
        invoicing_active_at: Optional[datetime] = None,
        invoice_cadence: Optional[str] = None,
        bill_processing_delay_days: int = DEFAULT_BILL_PROCESSING_DELAY_DAYS,
        bill_cutoff_at_buffer_days: int = DEFAULT_BILL_CUTOFF_AT_BUFFER_DAYS,
    ) -> OrganizationInvoicingSettings | str:
        log.info(
            "Start updating org invoicing setting",
            organization_id=existing_invoicing_setting.organization_id,
            updated_by_user_id=str(updated_by_user_id),
        )

        try:
            existing_invoicing_setting.updated_by_user_id = updated_by_user_id
            existing_invoicing_setting.invoicing_active_at = invoicing_active_at
            existing_invoicing_setting.invoice_cadence = invoice_cadence
            existing_invoicing_setting.bill_processing_delay_days = (
                bill_processing_delay_days
            )
            existing_invoicing_setting.bill_cutoff_at_buffer_days = (
                bill_cutoff_at_buffer_days
            )
            existing_invoicing_setting.updated_at = datetime.utcnow()

            updated_invoicing_setting: OrganizationInvoicingSettings = (
                self._invoicing_service.update_invoice_setting(
                    updated_organization_invoicing_setting=existing_invoicing_setting
                )
            )
            self._session.commit()
            return updated_invoicing_setting
        except Exception as e:
            log.error("Error in updating org invoicing setting", error_msg=str(e))
            return str(e)

    def delete_invoicing_setting(
        self, *, invoicing_setting_id: int, deleted_by_user_id: int
    ) -> Optional[str]:
        log.info(
            "Start deleting org invoicing setting",
            invoicing_setting_id=invoicing_setting_id,
            deleted_by_user_id=str(deleted_by_user_id),
        )

        try:
            self._invoicing_service.delete_invoice_setting_by_id(
                id=invoicing_setting_id
            )
            self._session.commit()
            return None
        except Exception as e:
            log.error("Error in deleting org invoicing setting", error_msg=str(e))
            return str(e)

    def delete_invoice(
        self, *, invoice_id: int, deleted_by_user_id: int
    ) -> Optional[str]:
        log.info(
            "Start deleting invoices",
            invoice_id=invoice_id,
            deleted_by_user_id=str(deleted_by_user_id),
        )

        try:
            self._invoicing_service.delete_invoice(invoice_id=invoice_id)
            self._session.commit()
            return None
        except Exception as e:
            log.error(
                "Error in deleting invoice", invoice_id=invoice_id, error_msg=str(e)
            )
            return str(e)

    def create_invoice_and_allocate(
        self, *, ros_id: int, created_by_process: Process, created_by_user_id: int
    ) -> dict[int, list[DirectPaymentInvoiceBillAllocation]]:
        log.info(
            "Start creating invoices in create_invoice_and_allocate",
            ros_id=ros_id,
            created_by_process=str(created_by_process),
            created_by_user_id=str(created_by_user_id),
        )

        org_info: Optional[Organization] = (
            self._session.query(Organization)
            .join(
                ReimbursementOrganizationSettings,
                ReimbursementOrganizationSettings.organization_id == Organization.id,
            )
            .filter(
                ReimbursementOrganizationSettings.id == ros_id,
                ReimbursementOrganizationSettings.direct_payment_enabled,
            )
            .one_or_none()
        )

        if org_info is None:
            log.error(
                "Cannot find organization from for ros_id in create_invoice_and_allocate because ros_id does not exist or enable direct payment",
                ros_id=ros_id,
            )
            stats.increment(
                metric_name="direct_payment.invoicing.failed_invoice_creation",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=[f"created_by_process:{str(created_by_process)}"],
            )
            return {}

        organization_id = org_info.id
        organization_name = org_info.name

        try:
            invoices = self._create_blank_invoices_in_memory(
                created_by_process,
                created_by_user_id,
                organization_id,
                organization_name,
                [ros_id],
            )

            ros_ids_to_bills_map = self._get_ros_ids_to_bills_map(invoices)
            invoice_to_allocations_map = self._allocate_bills_to_invoices(
                invoices,
                ros_ids_to_bills_map,
                organization_name,
                created_by_process,
                created_by_user_id,
            )

            invoice_uuid_to_bill_report_dict: dict[str, BillingReport] = {}
            try:
                invoice_uuid_to_bill_report_dict = (
                    self._create_and_stamp_report_on_invoices(
                        organization_id,
                        organization_name,
                        invoices,
                        ros_ids_to_bills_map,
                    )
                )
            except Exception as e:
                log.warn(
                    "Something wrong when creating the report in create_invoice_and_allocate. Won't stop the whole process of create_invoice_and_allocate",
                    organization_id=organization_id,
                    error_msg=str(e),
                )

            self._session.commit()
            log.info(
                "Finish creating invoices in create_invoice_and_allocate",
                organization_id=organization_id,
                ros_id=ros_id,
                created_by_process=str(created_by_process),
                created_by_user_id=str(created_by_user_id),
                invoice_cnt=len(invoice_to_allocations_map),
            )

            for invoice_uuid, bill_report in invoice_uuid_to_bill_report_dict.items():
                self._record_successful_invoice_creation(
                    invoice_uuid, bill_report, "create_invoice_and_allocate"
                )

            return invoice_to_allocations_map
        except Exception as e:
            self._session.rollback()
            log.error(
                "Unable to create and allocate invoices for the ros_id in create_invoice_and_allocate",
                ros_id=ros_id,
                exrror=str(e),
                reason=format_exc(),
            )

            stats.increment(
                metric_name="direct_payment.invoicing.failed_invoice_creation",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=[f"created_by_process:{str(created_by_process)}"],
            )

            raise e

    def create_invoices_and_allocate(
        self,
        *,
        organization_id: int,
        created_by_process: Process,
        created_by_user_id: int | None,
    ) -> dict[int, list[DirectPaymentInvoiceBillAllocation]]:
        """
        Creates invoices for all ROS-es linked to the organization id
        :param organization_id: Self explanatory
        :param created_by_process: The process trying to create these invoices.
        :param created_by_user_id: Required if the process calling this fn is ADMIN
        :return: A dict of invoices to allocations.
        """
        try:
            log.info(
                "Start creating invoices in create_invoices_and_allocate",
                organization_id=organization_id,
                created_by_process=str(created_by_process),
                created_by_user_id=str(created_by_user_id),
            )

            organization_name: Optional[str] = (
                self._session.query(Organization.name)
                .filter(Organization.id == organization_id)
                .scalar()
            )

            if organization_name is None:
                log.error(
                    "Cannot find organization name in create_invoices_and_allocate",
                    organization_id=organization_id,
                )
                stats.increment(
                    metric_name="direct_payment.invoicing.failed_invoice_creation",
                    pod_name=stats.PodNames.BENEFITS_EXP,
                    tags=[f"created_by_process:{str(created_by_process)}"],
                )
                return {}

            ros_ids = self._get_ros_ids(organization_id)
            invoices = self._create_blank_invoices_in_memory(
                created_by_process,
                created_by_user_id,
                organization_id,
                organization_name,
                ros_ids,
            )
            ros_ids_to_bills_map = self._get_ros_ids_to_bills_map(invoices)
            invoice_to_allocations_map = self._allocate_bills_to_invoices(
                invoices,
                ros_ids_to_bills_map,
                organization_name,
                created_by_process,
                created_by_user_id,
            )

            invoice_uuid_to_bill_report_dict: dict[str, BillingReport] = {}
            try:
                invoice_uuid_to_bill_report_dict = (
                    self._create_and_stamp_report_on_invoices(
                        organization_id,
                        organization_name,
                        invoices,
                        ros_ids_to_bills_map,
                    )
                )
            except Exception as e:
                log.warn(
                    "Something wrong when creating the report in create_invoices_and_allocate. Won't stop the whole process of create_invoices_and_allocate",
                    organization_id=organization_id,
                    error_msg=str(e),
                )

            self._session.commit()
            log.info(
                "Finish creating invoices in create_invoices_and_allocate",
                organization_id=organization_id,
                created_by_process=str(created_by_process),
                created_by_user_id=str(created_by_user_id),
                invoice_cnt=len(invoice_to_allocations_map),
            )

            for invoice_uuid, bill_report in invoice_uuid_to_bill_report_dict.items():
                self._record_successful_invoice_creation(
                    invoice_uuid, bill_report, "create_invoices_and_allocate"
                )

            return invoice_to_allocations_map
        except Exception as e:
            self._session.rollback()
            log.error(
                "Unable to create and allocate invoices for the org in create_invoices_and_allocate",
                organization_id=organization_id,
                exrror=str(e),
                reason=format_exc(),
            )

            stats.increment(
                metric_name="direct_payment.invoicing.failed_invoice_creation",
                pod_name=stats.PodNames.BENEFITS_EXP,
                tags=[f"created_by_process:{str(created_by_process)}"],
            )

            raise e

    @staticmethod
    def _record_successful_invoice_creation(
        invoice_uuid: str, bill_report: BillingReport, caller: str
    ) -> None:
        log.info(
            f"Successful invoice creation in {caller}",
            invoice_uuid=str(invoice_uuid),
            organization_name=bill_report.organisation_name,
            start_date_time=bill_report.start_date_time,
            end_date_time=bill_report.end_date_time,
            clinic_bill_amount=bill_report.clinic_bill_amount,
            pharmacy_bill_amount=bill_report.pharmacy_bill_amount,
        )

        stats.increment(
            metric_name="direct_payment.invoicing.successful_invoice_creation",
            pod_name=stats.PodNames.BENEFITS_EXP,
            tags=[f"organization_name:{bill_report.organisation_name}"],
        )

    def _allocate_bills_to_invoices(
        self,
        invoices: list[DirectPaymentInvoice],
        ros_ids_to_bills_map: dict[int, list[Bill]],
        org_name: str,
        created_by_process: Process,
        created_by_user_id: int | None,
    ) -> dict[int, list[DirectPaymentInvoiceBillAllocation]]:
        to_return = {}
        for invoice in invoices:
            try:
                bills_for_invoice = ros_ids_to_bills_map.get(
                    invoice.reimbursement_organization_settings_id, []
                )
                bills_for_invoice_uuids = [b.uuid for b in bills_for_invoice]
                allocations = self._invoicing_service.create_allocations(
                    invoice=invoice,
                    bill_uuids=bills_for_invoice_uuids,
                )

                if created_by_user_id is not None:
                    invoice.bill_allocated_by_user_id = created_by_user_id
                invoice.bills_allocated_by_process = created_by_process
                invoice.bills_allocated_at = datetime.now(timezone.utc)

                log.info(
                    "Allocated bills to invoice in memory.",
                    invoice_id=str(invoice.id),
                    invoice_uuid=str(invoice.uuid),
                    invoice_allocation_cnt=len(allocations),
                    invoice_bill_uuids=bills_for_invoice_uuids,
                )
                if invoice.id is not None:
                    to_return[invoice.id] = allocations
            except Exception as e:
                log.error(
                    "Error when allocating bills to an invoice. Stop the whole process of create_invoices_and_allocate",
                    invoice_id=invoice.id,
                    invoice_uuid=str(invoice.uuid),
                    ros_id=invoice.reimbursement_organization_settings_id,
                    org_name=org_name,
                    error_msg=str(e),
                )
                raise e
        return to_return

    def _create_blank_invoices_in_memory(
        self,
        created_by_process: Process,
        created_by_user_id: int | None,
        org_id: int,
        org_name: str,
        ros_ids: list[int],
    ) -> list[DirectPaymentInvoice]:
        # pegging the time ensures that all ros invoices for the org cover the same time window
        pegged_time = datetime.now(timezone.utc)
        log.info(
            "Creating invoices for org at pegged current time.",
            org_id=org_id,
            ros_id_cnt=len(ros_ids),
            current_time=str(pegged_time),
        )
        invoices = []
        for ros_id in ros_ids:
            try:
                log.info("Building invoice for ROS.", org_id=org_id, ros_id=ros_id)
                invoice = self._invoicing_service.create_new_invoice(
                    created_by_process=created_by_process,
                    created_by_user_id=created_by_user_id,
                    reimbursement_organization_settings_id=ros_id,
                    current_time=pegged_time,
                )
                if invoice:
                    log.info(
                        "Built empty in-memory invoice for ROS.",
                        ros_id=ros_id,
                        invoice=str(invoice.uuid),
                    )
                    invoices.append(invoice)
                else:
                    log.info(
                        "Did not build empty in-memory invoice for ROS.", ros_id=ros_id
                    )

                # get all the ros ids that we created invoices for
                log.info(
                    "Created invoices for org at pegged current time.",
                    org_id=org_id,
                    invoice_cnt=len(invoices),
                    current_time=str(pegged_time),
                    ros_id=ros_id,
                )
            except Exception as e:
                log.error(
                    "Error when creating an invoice. Stop the whole process of create_invoices_and_allocate",
                    org_name=org_name,
                    ros_id=ros_id,
                    error_msg=str(e),
                )
                raise e

        return invoices

    def _get_ros_ids_to_bills_map(
        self, invoices: list[DirectPaymentInvoice]
    ) -> dict[int, list[Bill]]:
        if invoices:
            ros_ids_with_invoices = [
                i.reimbursement_organization_settings_id for i in invoices
            ]

            bills: list[
                Bill
            ] = self._billing_service.get_new_employer_bills_for_payor_ids_in_datetime_range(
                payor_ids=ros_ids_with_invoices,
                start_datetime=invoices[0].bill_creation_cutoff_start_at,
                end_datetime=invoices[0].bill_creation_cutoff_end_at,
            )
            ros_id_to_bill_uuid_map: dict[int, list[Bill]] = defaultdict(list)
            for bill in bills:
                ros_id_to_bill_uuid_map[bill.payor_id].append(bill)
            return ros_id_to_bill_uuid_map
        return {}

    def _get_ros_ids(self, organization_id: int) -> list[int]:
        rows = (
            self._session.query(ReimbursementOrganizationSettings.id)
            .filter(
                ReimbursementOrganizationSettings.organization_id == organization_id,
                ReimbursementOrganizationSettings.direct_payment_enabled,
            )
            .all()
        )
        to_return = [r[0] for r in rows]
        log.info(
            "Pulled ROS ids for org",
            organization_id=organization_id,
            ros_ids=str(to_return),
        )
        return to_return

    def _create_and_stamp_report_on_invoices(
        self,
        organization_id: int,
        organization_name: str,
        invoices: list[DirectPaymentInvoice],
        ros_ids_to_bills_map: dict[int, list[Bill]],
    ) -> dict[str, BillingReport]:
        invoice_setting: Optional[
            OrganizationInvoicingSettings
        ] = self._invoicing_service.get_invoice_setting_by_organization_id(
            organization_id=organization_id
        )
        if invoice_setting is None:
            log.error("Cannot find invoice setting", organization_id=organization_id)
            return {}

        report_cadence: Optional[str] = generate_user_friendly_report_cadence(
            organization_id, invoice_setting.invoice_cadence
        )
        if report_cadence is None:
            log.error(
                "Invalid report cadence in cron format",
                invoice_cadence=invoice_setting.invoice_cadence,
                organization_id=organization_id,
            )
            return {}

        bill_reports = {}
        for invoice in invoices:
            try:
                bill_report: BillingReport = self._create_and_stamp_report_on_invoice(
                    invoice,
                    ros_ids_to_bills_map,
                    organization_name,
                    organization_id,
                    report_cadence,
                )

                bill_reports[str(invoice.uuid)] = bill_report
            except Exception as e:
                log.error(
                    "Error when generating report for an invoice",
                    invoice_id=invoice.id,
                    organization_id=organization_id,
                    error_msg=str(e),
                )
                raise e
        return bill_reports

    def _create_and_stamp_report_on_invoice(
        self,
        invoice: DirectPaymentInvoice,
        ros_ids_to_bills_map: dict[int, list[Bill]],
        organization_name: str,
        organization_id: int,
        report_cadence: str,
    ) -> BillingReport:
        reported_generated_at = datetime.now(timezone.utc)

        ros_id = invoice.reimbursement_organization_settings_id
        bills: list[Bill] = ros_ids_to_bills_map.get(ros_id, [])

        total_number_of_bills = len(bills)
        total_bill_amount: int = 0
        clinic_bill_amount: int = 0
        pharmacy_bill_amount: int = 0
        bill_information = []

        procedure_ids = [bill.procedure_id for bill in bills]
        treatment_procedures = (
            self._treatment_procedure_service.get_treatment_procedure_by_ids(
                procedure_ids
            )
        )

        tp_id_to_tp_type_map: dict[int, TreatmentProcedureType] = {
            treatment_procedure.id: treatment_procedure.procedure_type
            for treatment_procedure in treatment_procedures
        }

        for bill in bills:
            bill_uuid = bill.uuid
            bill_amount = bill.amount
            bill_created_at = bill.created_at

            # Need assert to make sure bill_created_at used to build
            # BillInformation below is not None, and pass mypy checks
            assert bill_created_at is not None

            tp_type: TreatmentProcedureType = tp_id_to_tp_type_map.get(
                bill.procedure_id, TreatmentProcedureType.MEDICAL
            )
            bill_type = BillType[tp_type.value.upper()]

            total_bill_amount = total_bill_amount + bill_amount
            if bill_type == BillType.MEDICAL:
                clinic_bill_amount = clinic_bill_amount + bill_amount
            elif bill_type == BillType.PHARMACY:
                pharmacy_bill_amount = pharmacy_bill_amount + bill_amount

            bill_information.append(
                BillInformation(
                    uuid=bill_uuid,
                    bill_created_at=bill_created_at,
                    bill_amount=format_cents_to_usd_str(bill_amount),
                    bill_type=bill_type,
                )
            )

        billing_report = BillingReport(
            organisation_name=organization_name,
            organisation_id=organization_id,
            report_generated_at=reported_generated_at,
            report_cadence=report_cadence,
            start_date_time=invoice.bill_creation_cutoff_start_at,
            end_date_time=invoice.bill_creation_cutoff_end_at,
            total_bills=total_number_of_bills,
            total_bill_amount=format_cents_to_usd_str(total_bill_amount),
            clinic_bill_amount=format_cents_to_usd_str(clinic_bill_amount),
            pharmacy_bill_amount=format_cents_to_usd_str(pharmacy_bill_amount),
            bill_information=bill_information,
        )

        invoice.report_generated_at = reported_generated_at
        invoice.report_generated_json = json.dumps(
            billing_report, cls=CustomJSONEncoder
        )

        self._invoicing_service.update_invoice(invoice=invoice)
        return billing_report


class CustomJSONEncoder(JSONEncoder):
    def default(self, obj: Any) -> Any:
        if is_dataclass(obj):
            return asdict(obj)
        elif isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, Enum):
            return obj.value
        return super().default(obj)
