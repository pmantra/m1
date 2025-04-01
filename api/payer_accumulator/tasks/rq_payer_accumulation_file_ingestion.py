from datetime import datetime
from traceback import format_exc
from typing import Any, List, Optional

from paramiko.sftp_client import SFTPClient

from payer_accumulator.common import PayerName
from payer_accumulator.edi.constants import (
    AETNA_277_FILENAME_DATE_INDEX,
    AETNA_277_FILENAME_PATTERN,
    AETNA_277CA_FILENAME_DATE_INDEX,
    AETNA_277CA_FILENAME_PATTERN,
    AETNA_INGESTION_FAILURE,
    AVAILITY_INGESTION_DIR,
    AVAILITY_PORT_NUMBER,
    AVAILITY_SFTP_SECRET,
    SchemaType,
)
from payer_accumulator.edi.file_ingestion import FileIngestionJob
from payer_accumulator.edi.x12_file_parser_277 import X12FileParser277
from payer_accumulator.edi.x12_file_parser_277ca import X12FileParser277CA
from utils.log import logger
from utils.sftp import SSHError, get_sftp_from_secret

log = logger(__name__)


class X12FileIngestionJob(FileIngestionJob):
    def __init__(self, payer_name: PayerName, file_type: SchemaType):
        self.payer_name = payer_name
        self.file_type = file_type

    def run(self, target_date: Optional[datetime] = None) -> None:
        try:
            if not target_date:
                target_date = datetime.today()
            log.info(
                "Starting X12 ingestion job.",
                file_type=self.file_type.value,
                payer_name=self.payer_name.value,
                target_date=target_date,
            )
            self.download_and_parse_files(target_date=target_date)
            log.info(
                "X12 file ingestion job succeeded.",
                file_type=self.file_type.value,
                payer_name=self.payer_name.value,
                target_date=target_date,
            )
        except Exception as e:
            log.error(
                "Failed to run file ingestion job due to exception.",
                reason=format_exc(),
                payer_name=self.payer_name.value,
                file_type=self.file_type.value,
                exc_info=True,
                error_message=str(e),
            )

    def download_and_parse_files(self, target_date: datetime) -> None:
        log.info(
            "Trying to connect to Availity.",
            payer_name=self.payer_name.value,
            file_type=self.file_type.value,
            target_date=target_date,
        )
        sftp_client = get_sftp_from_secret(AVAILITY_SFTP_SECRET, port=AVAILITY_PORT_NUMBER)  # type: ignore[arg-type] # Argument 1 to "get_sftp_from_secret" has incompatible type "Optional[str]"; expected "str"
        if not sftp_client:
            log.warning(
                "Failed to connect to SFTP. No files downloaded from Availity",
                payer_name=self.payer_name.value,
                file_type=self.file_type.value,
                target_date=target_date,
            )
            raise SSHError(
                message="Failed to connect to SFTP. No files downloaded from Availity"
            )
        log.info(
            "Successfully created SFTP connection with Availity.",
            payer_name=self.payer_name.value,
            file_type=self.file_type.value,
            target_date=target_date,
        )
        files = self.get_files_from_availity(
            sftp_client=sftp_client,
            target_date=int(target_date.strftime("%Y%m%d")),
            file_type=self.file_type,
        )
        if not files:
            log.warning(
                "No files of specified type and payer found from Availity",
                payer_name=self.payer_name.value,
                file_type=self.file_type.value,
                target_date=target_date,
            )
            return
        log.info(
            "X12 files identified for ingestion",
            payer_name=self.payer_name.value,
            file_type=self.file_type.value,
            target_date=target_date,
            num_files=len(files),
        )
        for file_name in files:
            file_content = self.download_file(
                file_name=file_name,
                directory=AVAILITY_INGESTION_DIR,
                sftp_client=sftp_client,
                metric_name=AETNA_INGESTION_FAILURE,
            )
            log.info(
                "X12 file downloaded from Availity",
                file_name=file_name,
                file_type=self.file_type.value,
                payer_name=self.payer_name.value,
                target_date=target_date,
            )
            if not file_content:
                log.info(
                    "X12 file contains no content. Not parsing file",
                    file_name=file_name,
                    payer_name=self.payer_name.value,
                    file_type=self.file_type.value,
                    target_date=target_date,
                )
                continue
            self.parse_x12_file(file_content=file_content, file_type=self.file_type)
            log.info(
                "X12 file ingested successfully",
                file_name=file_name,
                payer_name=self.payer_name.value,
                file_type=self.file_type.value,
                target_date=target_date,
            )

    def get_files_from_availity(
        self,
        target_date: int,
        file_type: SchemaType,
        sftp_client: Optional[SFTPClient],
    ) -> List[str]:
        if not sftp_client:
            return []
        file_pattern, date_index = _get_filename_pattern_from_payer_name_and_file_type(
            payer_name=self.payer_name, file_type=file_type
        )
        files = sftp_client.listdir(AVAILITY_INGESTION_DIR)
        new_files = self.find_files_to_process(
            files=files,
            filename_pattern=file_pattern,
            target_date=target_date,
            date_index=date_index,
        )
        return new_files

    def parse_x12_file(self, file_content: str, file_type: SchemaType) -> None:
        if file_type == SchemaType.EDI_277:
            log.info(
                "Parsing x12 file using 277 parser",
                file_type=file_type.value,
            )
            self.parse_277_file_and_update_claim_statuses(file_content=file_content)
        elif file_type == SchemaType.EDI_277CA:
            log.info(
                "Parsing x12 file using 277CA parser",
                file_type=file_type.value,
            )
            self.parse_277ca_file_and_update_claim_statuses(file_content=file_content)
        else:
            log.warning(
                "No parser found for file_type",
                file_type=self.file_type.value,
            )

    def parse_277_file_and_update_claim_statuses(
        self,
        file_content: str,
    ) -> None:
        parser = X12FileParser277(edi_content=file_content)
        parsed_data = parser.get_data()
        if not parsed_data:
            log.error(
                "No parsed 277 data returned from X12FileParser",
                payer_name=self.payer_name.value,
            )
            return
        parser.check_and_update_claim_statuses(data=parsed_data)

    def parse_277ca_file_and_update_claim_statuses(
        self,
        file_content: str,
    ) -> None:
        parser = X12FileParser277CA(edi_content=file_content)
        parsed_data = parser.get_data()
        if not parsed_data:
            log.error(
                "No parsed 277CA data returned from X12FileParser",
                payer_name=self.payer_name.value,
            )
            return
        parser.check_and_update_claim_statuses(data=parsed_data)


def _get_filename_pattern_from_payer_name_and_file_type(
    payer_name: PayerName, file_type: SchemaType
) -> Any:
    if payer_name.value == "aetna":
        if file_type == SchemaType.EDI_277:
            return AETNA_277_FILENAME_PATTERN, AETNA_277_FILENAME_DATE_INDEX
        if file_type == SchemaType.EDI_277CA:
            return AETNA_277CA_FILENAME_PATTERN, AETNA_277CA_FILENAME_DATE_INDEX
    return ""


def aetna_accumulation_277_ingestion(
    target_date: Optional[datetime] = None,
) -> None:
    aetna_277_ingestion_job = X12FileIngestionJob(
        payer_name=PayerName.AETNA, file_type=SchemaType.EDI_277
    )
    aetna_277_ingestion_job.run(target_date=target_date)


def aetna_accumulation_277ca_ingestion(
    target_date: Optional[datetime] = None,
) -> None:
    aetna_277ca_ingestion_job = X12FileIngestionJob(
        payer_name=PayerName.AETNA, file_type=SchemaType.EDI_277CA
    )
    aetna_277ca_ingestion_job.run(target_date=target_date)
