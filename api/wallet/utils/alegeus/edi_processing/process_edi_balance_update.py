from __future__ import annotations

import abc
import csv
import dataclasses
import io
from datetime import datetime, timezone
from typing import Generic, Iterable, TypedDict, TypeVar

import paramiko

from direct_payment.pharmacy.utils.gcs_handler import upload_to_gcp_bucket
from storage.connection import db
from utils.log import logger
from wallet.constants import (
    ALEGEUS_EDI_BUCKET,
    ALEGEUS_PASSWORD_EDI,
    ALEGEUS_TPAID,
    EdiFileType,
    EdiTemplateName,
)
from wallet.models.models import AlegeusAccountBalanceUpdate
from wallet.services.currency import CurrencyService
from wallet.services.reimbursement_wallet import ReimbursementWalletService
from wallet.utils.alegeus.edi_processing.common import (
    check_file_availability,
    create_temp_file,
    get_client_sftp,
)
from wallet.utils.alegeus.upload_to_ftp_bucket import upload_blob

log = logger(__name__)

T = TypeVar("T", TypedDict, AlegeusAccountBalanceUpdate)


@dataclasses.dataclass
class EdiResponseSummary:
    file_name: str
    num_total_rows: int
    num_failure_rows: int
    row_summaries: list[EdiResponseRow] = dataclasses.field(default_factory=list)
    success: bool = True


@dataclasses.dataclass
class EdiResponseRow:
    identifier: tuple
    response_code: int
    message: str


class AbstractEdiFileGenerator(abc.ABC, Generic[T]):
    file_type: EdiFileType = None

    def __init__(self, data: list[T]):
        if self.file_type is None:
            raise NotImplementedError("file_type must be specified")
        self.data = data

    def _header_row(self, no_auth: bool = False) -> list[str | None]:
        """Defines the header row values"""
        return [
            "IA",
            str(len(self.data)),
            ALEGEUS_PASSWORD_EDI if no_auth is False else "",
            EdiTemplateName.IMPORT,
            EdiTemplateName.RESULT,
            EdiTemplateName.EXPORT,
        ]

    def _mapped_rows(self) -> Iterable[list]:
        """Return a generator for the final row values of the file"""
        if not self.data:
            raise ValueError("No data found to generate file with")
        for row in self.data:
            yield self.row_mapper(row_dict=row)

    def generate_file(self, no_auth: bool = False) -> io.StringIO:
        """Generate the file with the header and rows"""
        string_buffer = io.StringIO()
        writer = csv.writer(string_buffer)
        writer.writerow(self._header_row(no_auth=no_auth))
        writer.writerows(self._mapped_rows())
        return string_buffer

    @staticmethod
    def _response_header_parser(row: list[str]) -> EdiResponseSummary:
        """Map the header of the response file - should be same for all file types"""
        return EdiResponseSummary(
            file_name=row[1],
            num_total_rows=int(row[3]),
            num_failure_rows=int(row[4]),
        )

    def parse_response_file(self, buffer: io.StringIO) -> EdiResponseSummary:
        """Parse the response file and return a summary object with row details"""
        reader = csv.reader(buffer)
        header_row = next(reader)

        summary = AbstractEdiFileGenerator._response_header_parser(row=header_row)

        for row in reader:
            row_summary = self.response_row_parser(row=row)
            summary.row_summaries.append(row_summary)

            if row_summary.response_code == 0:
                log.info(
                    "parse_response_file: No error found for row",
                    file_name=summary.file_name,
                    identifier=row_summary.identifier,
                    response_code=row_summary.response_code,
                    message=row_summary.message,
                )
                continue  # Successful row, do nothing
            else:
                log.info(
                    "parse_response_file: Error found for row",
                    file_name=summary.file_name,
                    identifier=row_summary.identifier,
                    response_code=row_summary.response_code,
                    message=row_summary.message,
                )
                summary.success = False

        if summary.success is True:
            log.info(
                "parse_response_file: No errors found in response file",
                file_name=summary.file_name,
                num_total_rows=summary.num_total_rows,
            )
        else:
            log.info(
                "parse_response_file: Errors found in response file",
                file_name=summary.file_name,
                num_total_rows=summary.num_total_rows,
                num_failure_rows=summary.num_failure_rows,
            )

        return summary

    @abc.abstractmethod
    def row_mapper(self, row_dict: T) -> list[str | None]:
        """Return a row of the EDI file"""
        raise NotImplementedError("row_mapper must be implemented")

    @staticmethod
    @abc.abstractmethod
    def response_row_parser(row: list[str]) -> EdiResponseRow:
        """Map the header of response file row"""
        raise NotImplementedError("response_row_parser must be implemented")


class IHEdiFileGenerator(AbstractEdiFileGenerator[AlegeusAccountBalanceUpdate]):
    file_type = EdiFileType.IH

    def row_mapper(self, row_dict: AlegeusAccountBalanceUpdate) -> list[str | None]:
        return [
            self.file_type.value,
            ALEGEUS_TPAID,
            row_dict["employer_id"],
            row_dict["employee_id"],
            "2",
            row_dict["account_type"],
            str(row_dict["usd_amount"]),
            "0",
            "1",
        ]

    @staticmethod
    def response_row_parser(row: list[str]) -> EdiResponseRow:
        return EdiResponseRow(
            identifier=(row[1], row[2]),
            response_code=int(row[10]),
            message=row[11],
        )


def process_balance_update(
    year: int, dry_run: bool = True, upload_to_gcs: bool = True, **kwargs: list[int]
) -> io.StringIO:
    wallet_service = ReimbursementWalletService()
    currency_service = CurrencyService()

    balances_updates: list[
        AlegeusAccountBalanceUpdate
    ] = wallet_service.calculate_ltm_updates(
        year=year, currency_service=currency_service, **kwargs
    )

    db.session.remove()

    ih_generator = IHEdiFileGenerator(data=balances_updates)
    # generate a file with no secrets for GCP & download from admin
    ih_file_buffer_no_auth: io.StringIO = ih_generator.generate_file(no_auth=True)
    ih_file_name: str = f"MAVEN_IH_{str(year)}_UPDATE_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
    request_file_name: str = f"{ih_file_name}.mbi"
    response_file_name: str = f"{ih_file_name}.res"

    if upload_to_gcs:
        # Upload to GCS bucket
        upload_to_gcp_bucket(
            content=ih_file_buffer_no_auth,
            filename=f"{EdiFileType.IH.value}/outbound/{request_file_name}",
            bucket=ALEGEUS_EDI_BUCKET,
        )

    if not dry_run:
        # generate a file with secret
        ih_file_buffer_with_auth: io.StringIO = ih_generator.generate_file(
            no_auth=False
        )

        # Open a SFTP connection to Alegeus server
        client: paramiko.SSHClient | None = None

        try:
            client, sftp = get_client_sftp()
        except Exception as e:
            log.exception(
                "process_balance_update: Unable to connect to SFTP server.", exc=e
            )
            if client:
                client.close()
            raise e

        try:
            upload_blob(
                csv_contents=ih_file_buffer_with_auth.getvalue(),
                destination_blob_name=request_file_name,
                client=client,
                sftp=sftp,
            )
        except Exception as e:
            log.exception(
                "process_balance_update: Unable to upload file to SFTP server.",
                request_file_name=request_file_name,
                exc=e,
            )
            client.close()
            raise e
        else:
            log.info(
                "process_balance_update: file successfully uploaded",
                request_file_name=request_file_name,
            )

        try:
            if check_file_availability(
                filename=response_file_name, client=client, sftp=sftp
            ):
                temp_file = create_temp_file(response_file_name, sftp)
                response_file_buffer = io.StringIO(temp_file.read().decode("utf-8"))
            else:
                raise Exception("No response file found")
        except Exception as e:
            log.exception(
                "process_balance_update: Unable to fetch response file",
                response_file_name=response_file_name,
                exc=e,
            )
            client.close()
            raise e
        else:
            log.info(
                "process_balance_update: Response file fetched",
                response_file_name=response_file_name,
            )
            client.close()

        try:
            _ = ih_generator.parse_response_file(buffer=response_file_buffer)
        except Exception as e:
            log.exception(
                "process_balance_update: Unable to process response file",
                response_file_name=response_file_name,
                exc=e,
            )
            raise e

        if upload_to_gcs:
            # Upload response file to GCS
            upload_to_gcp_bucket(
                content=response_file_buffer,
                filename=f"{EdiFileType.IH.value}/inbound/{response_file_name}",
                bucket=ALEGEUS_EDI_BUCKET,
            )

    return ih_file_buffer_no_auth
