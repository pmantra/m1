from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

import pytz
from sqlalchemy.engine import ResultProxy
from sqlalchemy.orm import Query, scoped_session

from direct_payment.billing.models import Bill
from direct_payment.invoicing.models import (
    DirectPaymentInvoice,
    DirectPaymentInvoiceBillAllocation,
    OrganizationInvoicingSettings,
    Process,
)
from direct_payment.invoicing.repository.direct_payment_invoice import (
    DirectPaymentInvoiceRepository,
)
from direct_payment.invoicing.repository.direct_payment_invoice_bill_allocation import (
    DirectPaymentInvoiceBillAllocationRepository,
)
from direct_payment.invoicing.repository.organization_invoicing_settings import (
    OrganizationInvoicingSettingsRepository,
)
from direct_payment.invoicing.utils import validate_cron_expression
from utils.log import logger

log = logger(__name__)


class DirectPaymentInvoicingService:
    def __init__(self, *, session: scoped_session):
        self.session = session
        self._invoice_repo = DirectPaymentInvoiceRepository(
            session=session, is_in_uow=True
        )
        self._bill_allocation_repo = DirectPaymentInvoiceBillAllocationRepository(
            session=session, is_in_uow=True
        )
        self._org_invoicing_settings_repo = OrganizationInvoicingSettingsRepository(
            session=session, is_in_uow=True
        )

    def delete_invoice(self, *, invoice_id: int) -> None:
        self._invoice_repo.delete(id=invoice_id)

    def get_invoice_bills_ready_to_process(self) -> list[Bill]:
        return self._bill_allocation_repo.get_invoice_bills_ready_to_process()

    def create_new_invoice(
        self,
        *,
        created_by_process: Process,
        created_by_user_id: int | None,
        reimbursement_organization_settings_id: int,
        current_time: datetime,
    ) -> DirectPaymentInvoice | None:
        """
        Creates a new invoice based on organization settings and process parameters.
        :param created_by_process: The process initiating the invoice creation.
        :param created_by_user_id: User creating the invoice. Cannot be None if the process is Admin
        :param reimbursement_organization_settings_id: self-explanatory
        :param current_time: The current time as decided by the caller.
        :return:  A new in memory DirectPaymentInvoice instance if creation was successful, None if creation failed due
        to missing invoicing settings or failed cutoff time restrictions.
        :raises ValueError: If created_by_process is Process.ADMIN and created_by_user_id
            is None.
        """
        if created_by_process == Process.ADMIN and created_by_user_id is None:
            raise ValueError(
                "created_by_user_id must be provided when created_by_process is ADMIN"
            )
        ois = self._org_invoicing_settings_repo.get_by_reimbursement_org_settings_id(
            reimbursement_organization_settings_id=reimbursement_organization_settings_id
        )
        if not ois:
            log.warn(
                "Unable to find organization invoicing setting. Invoice will not be created.",
                reimbursement_organization_settings_id=reimbursement_organization_settings_id,
            )
            return None
        else:
            log.info(
                "Found matching organization invoicing setting.",
                reimbursement_organization_settings_id=reimbursement_organization_settings_id,
                organization_invoicing_setting_uuid=str(ois.uuid),
            )

        prev_invoice = self._invoice_repo.get_latest_invoice_by_reimbursement_organization_settings_id(
            reimbursement_organization_settings_id
        )
        (
            bill_creation_cutoff_start_at,
            bill_creation_cutoff_end_at,
        ) = self._calc_bill_cutoff_times(ois, prev_invoice, current_time)

        if not self._are_cutoffs_allowed(
            bill_creation_cutoff_end_at, bill_creation_cutoff_start_at, prev_invoice
        ):
            return None

        to_return = self._create_empty_invoice(
            created_by_process=created_by_process,
            created_by_user_id=created_by_user_id,
            reimbursement_organization_settings_id=reimbursement_organization_settings_id,
            bill_creation_cutoff_start_at=bill_creation_cutoff_start_at,
            bill_creation_cutoff_end_at=bill_creation_cutoff_end_at,
        )
        return to_return

    @staticmethod
    def _calc_bill_cutoff_times(
        ois: OrganizationInvoicingSettings,
        prev_invoice: DirectPaymentInvoice | None,
        current_time: datetime,
    ) -> tuple[datetime, datetime]:
        if prev_invoice:
            bill_creation_cutoff_start_at = (
                prev_invoice.bill_creation_cutoff_end_at + timedelta(seconds=1)
            )
            log.info(
                "Computing bill_creation_cutoff_start_at from previous invoice.",
                prev_invoice_uuid=str(prev_invoice.uuid),
                prev_invoice_id=str(prev_invoice.id),
                prev_invoice_bill_creation_cutoff_end_at=str(
                    prev_invoice.bill_creation_cutoff_end_at
                ),
                bill_creation_cutoff_start_at=str(bill_creation_cutoff_start_at),
            )
        else:
            bill_creation_cutoff_start_at = datetime.fromtimestamp(0, tz=timezone.utc)
            log.info(
                "No previous invoice found. bill_creation_cutoff_start_at set to the start of the Unix Epoch.",
                bill_creation_cutoff_start_at=str(bill_creation_cutoff_start_at),
            )
        # set it to the last second prior to the cutoff day (respecting the db granularity here)
        # eg - 0 => no bill included from current day
        bill_creation_cutoff_end_at = (
            current_time - timedelta(days=ois.bill_cutoff_at_buffer_days + 1)
        ).replace(hour=23, minute=59, second=59)

        return (
            DirectPaymentInvoicingService._safe_localize(bill_creation_cutoff_start_at),
            DirectPaymentInvoicingService._safe_localize(bill_creation_cutoff_end_at),
        )

    @staticmethod
    def _safe_localize(inp_datetime: datetime) -> datetime:
        return (
            pytz.utc.localize(inp_datetime) if not inp_datetime.tzinfo else inp_datetime
        )

    @staticmethod
    def _are_cutoffs_allowed(
        bill_creation_cutoff_end_at: datetime,
        bill_creation_cutoff_start_at: datetime,
        prev_invoice: DirectPaymentInvoice | None,
    ) -> bool:
        allowed = True
        if bill_creation_cutoff_end_at < bill_creation_cutoff_start_at:
            allowed = False
            log.warn(
                "Invoice cannot be created."
                "bill_creation_cutoff_end_at is before the bill_creation_cutoff_start_at.",
                bill_creation_cutoff_start_at=str(bill_creation_cutoff_start_at),
                bill_creation_cutoff_end_at=str(bill_creation_cutoff_end_at),
            )
        elif (
            prev_invoice
            and bill_creation_cutoff_end_at
            <= DirectPaymentInvoicingService._safe_localize(
                prev_invoice.bill_creation_cutoff_end_at
            )
        ):
            log.warn(
                "Invoice cannot be created."
                "bill_creation_cutoff_end_at is same as or before the previous invoice's bill_creation_cutoff_end_at.",
                bill_creation_cutoff_end_at=str(bill_creation_cutoff_end_at),
                prev_invoice_bill_creation_cutoff_end_at=str(
                    prev_invoice.bill_creation_cutoff_end_at
                ),
                prev_invoice_uuid=str(prev_invoice.uuid),
            )
            allowed = False
        return allowed

    def _create_empty_invoice(
        self,
        *,
        created_by_process: Process,
        created_by_user_id: int | None,
        reimbursement_organization_settings_id: int,
        bill_creation_cutoff_start_at: datetime,
        bill_creation_cutoff_end_at: datetime,
    ) -> DirectPaymentInvoice:
        invoice = DirectPaymentInvoice(
            uuid=uuid.uuid4(),
            created_by_process=created_by_process,
            created_by_user_id=created_by_user_id,
            reimbursement_organization_settings_id=reimbursement_organization_settings_id,
            bill_creation_cutoff_start_at=bill_creation_cutoff_start_at,
            bill_creation_cutoff_end_at=bill_creation_cutoff_end_at,
        )
        to_return = self._invoice_repo.create(instance=invoice)
        return to_return

    def update_invoice(self, *, invoice: DirectPaymentInvoice) -> None:
        self._invoice_repo.update(instance=invoice)

    def create_allocations(
        self, invoice: DirectPaymentInvoice, bill_uuids: list[uuid.UUID]
    ) -> list[DirectPaymentInvoiceBillAllocation]:
        to_return = []
        invoice_id: int | None = invoice.id

        if invoice_id is not None:
            for bill_uuid in bill_uuids:
                allocation = DirectPaymentInvoiceBillAllocation(
                    uuid=uuid.uuid4(),
                    created_by_process=invoice.created_by_process,
                    created_by_user_id=invoice.created_by_user_id,
                    direct_payment_invoice_id=invoice_id,
                    bill_uuid=bill_uuid,
                )
                allocation = self._bill_allocation_repo.create(instance=allocation)
                to_return.append(allocation)
        else:
            log.error(
                "Invoice id is None",
                ros_id=invoice.reimbursement_organization_settings_id,
                start_time=invoice.bill_creation_cutoff_start_at,
                end_time=invoice.bill_creation_cutoff_end_at,
            )
        return to_return

    def get_invoice(self, *, invoice_id: int) -> DirectPaymentInvoice | None:
        return self._invoice_repo.get(id=invoice_id)

    def get_invoice_setting_by_organization_id(
        self, *, organization_id: int
    ) -> OrganizationInvoicingSettings | None:
        return self._org_invoicing_settings_repo.get_by_organization_id(
            organization_id=organization_id
        )

    def get_invoice_setting_by_uuid(
        self, *, uuid: uuid.UUID
    ) -> OrganizationInvoicingSettings | None:
        return self._org_invoicing_settings_repo.get_by_uuid(uuid=uuid)

    def get_all_invoice_setting(self) -> list[OrganizationInvoicingSettings]:
        return self._org_invoicing_settings_repo.all()

    def get_org_level_invoice_report_data_query(self) -> Query:
        return self._invoice_repo.get_org_level_invoice_report_data_query()

    def get_org_level_invoice_report_count_query(self) -> ResultProxy:
        return self._invoice_repo.get_org_level_invoice_report_count_query()

    def create_invoice_setting(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        *,
        organization_invoicing_setting: OrganizationInvoicingSettings,
        return_created_instance: Literal[True, False] = True,
    ):
        try:
            if organization_invoicing_setting.invoice_cadence is not None:
                try:
                    validate_cron_expression(
                        organization_invoicing_setting.invoice_cadence
                    )
                except Exception:
                    raise Exception(
                        "The cron expression of the invoice cadence is invalid"
                    )

            # since is_in_uow is True, the caller is responsible for committing the change
            return self._org_invoicing_settings_repo.create(
                instance=organization_invoicing_setting, fetch=return_created_instance
            )
        except Exception as e:
            log.error(
                f"Error in inserting a record of OrganizationInvoicingSettings: {organization_invoicing_setting}",
                error_msg=str(e),
            )
            raise e

    def update_invoice_setting(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        self,
        *,
        updated_organization_invoicing_setting: OrganizationInvoicingSettings,
        return_updated_instance: Literal[True, False] = True,
    ):
        try:
            if updated_organization_invoicing_setting.invoice_cadence is not None:
                try:
                    validate_cron_expression(
                        updated_organization_invoicing_setting.invoice_cadence
                    )
                except Exception:
                    raise Exception(
                        "The cron expression of the invoice cadence is invalid"
                    )

            # since is_in_uow is True, the caller is responsible for committing the change
            return self._org_invoicing_settings_repo.update(
                instance=updated_organization_invoicing_setting,
                fetch=return_updated_instance,
            )
        except Exception as e:
            log.error(
                f"Error in updating a record of OrganizationInvoicingSettings: {updated_organization_invoicing_setting}",
                error_msg=str(e),
            )
            raise e

    def delete_invoice_setting_by_id(self, *, id: int) -> int:
        try:
            # since is_in_uow is True, the caller is responsible for committing the change
            return self._org_invoicing_settings_repo.delete(id=id)
        except Exception as e:
            log.error(
                "Error in deleting a record of OrganizationInvoicingSettings by id",
                id=id,
                error_msg=str(e),
            )
            raise e

    def delete_invoice_setting_by_organization_id(self, *, organization_id: int) -> int:
        try:
            # since is_in_uow is True, the caller is responsible for committing the change
            return self._org_invoicing_settings_repo.delete_by_organization_id(
                organization_id=organization_id
            )
        except Exception as e:
            log.error(
                "Error in deleting a record of OrganizationInvoicingSettings by organization_id",
                organization_id=organization_id,
                error_msg=str(e),
            )
            raise e

    def delete_invoice_setting_by_uuid(self, *, uuid: uuid.UUID) -> int:
        try:
            # since is_in_uow is True, the caller is responsible for committing the change
            return self._org_invoicing_settings_repo.delete_by_uuid(uuid=uuid)
        except Exception as e:
            log.error(
                "Error in deleting a record of OrganizationInvoicingSettings by uuid",
                uuid=uuid,
                error_msg=str(e),
            )
            raise e
