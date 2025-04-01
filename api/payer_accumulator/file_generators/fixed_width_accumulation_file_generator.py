from __future__ import annotations

import importlib
import io
from abc import abstractmethod
from copy import deepcopy
from datetime import date
from typing import Dict, List, Optional

import overpunch
import sqlalchemy
from fixedwidth.fixedwidth import FixedWidth

from common.constants import Environment
from payer_accumulator.common import DetailMetadata, PayerName
from payer_accumulator.file_generators.accumulation_file_generator import (
    AccumulationFileGenerator,
)
from utils.log import logger
from wallet.models.reimbursement_wallet import MemberHealthPlan

log = logger(__name__)


METRIC_PREFIX = "api.payer_accumulator.fixed_width_accumulation_file_generator"
MISSING_CRITICAL_ACCUMULATION_INFO = "missing_critical_accumulation_info"


class FixedWidthAccumulationFileGenerator(AccumulationFileGenerator):
    def __init__(
        self,
        payer_name: PayerName,
        session: Optional[sqlalchemy.orm.Session] = None,
    ):
        super().__init__(session=session, payer_name=payer_name)

        self.config = importlib.import_module(
            f"payer_accumulator.config.{self.payer_name.value}_fixed_width_config"
        )

        self.detail_config = deepcopy(self.config.DETAIL_ROW)
        self.header_config = deepcopy(self.config.HEADER_ROW)
        self.trailer_config = deepcopy(self.config.TRAILER_ROW)

        self.record_count = 0  # only used within generate_file_contents and it's callees; some tests require initialization

    @staticmethod
    def _get_environment() -> str:
        return "P" if Environment.current() == Environment.PRODUCTION else "T"

    def _generate_header(self) -> str:
        if not self.header_config:
            return ""
        header_obj = FixedWidth(self.header_config)
        header_obj.update(**self._get_header_required_fields())
        return header_obj.line

    def _get_header_required_fields(self) -> Dict:
        raise NotImplementedError

    def _generate_trailer(self, record_count: int, oop_total: int = 0) -> str:
        if not self.trailer_config:
            return ""
        tailer_obj = FixedWidth(self.trailer_config)
        tailer_obj.update(**self._get_trailer_required_fields(record_count, oop_total))
        return tailer_obj.line

    def _get_trailer_required_fields(
        self, record_count: int, oop_total: int = 0
    ) -> Dict:
        raise NotImplementedError

    def _get_header_trailer_row_count(self) -> int:
        return int(bool(self.header_config)) + int(bool(self.trailer_config))

    def get_record_count_from_buffer(self, buffer: io.StringIO) -> int:
        record_count = buffer.getvalue().count("\n")
        return record_count - self._get_header_trailer_row_count()

    def _update_trailer_with_record_counts(
        self, trailer_data: Dict, record_count: int, oop_total: int = 0
    ) -> Dict:
        trailer_data.update(
            **self._get_trailer_required_fields(record_count, oop_total)
        )
        return trailer_data

    def file_contents_to_dicts(self, file_contents: str) -> List[Dict]:
        # For UHC and ESI. Cigna should overwrite this method
        rows = []
        file_rows = [file_row for file_row in file_contents.splitlines() if file_row]
        num_rows = len(file_rows)

        first_detail_row = 1 if self.header_config else 0
        last_detail_row = num_rows - 1 if self.trailer_config else num_rows

        # header row
        if self.header_config:
            header_obj = FixedWidth(self.header_config)
            header_obj.line = file_rows[0]
            rows.append(header_obj.data)

        # detail rows
        detail_obj = FixedWidth(self.detail_config)
        for i in range(first_detail_row, last_detail_row):
            detail_obj.line = file_rows[i]
            rows.append(detail_obj.data)

        # trailer row
        if self.trailer_config:
            trailer_obj = FixedWidth(self.trailer_config)
            trailer_obj.line = file_rows[-1]
            rows.append(trailer_obj.data)

        return rows

    def detail_to_dict(self, detail_line: str) -> dict:
        # Note: also overwritten in cigna file generation
        detail_obj = FixedWidth(self.detail_config)
        detail_obj.line = detail_line
        return detail_obj.data

    def generate_file_contents_from_json(self, report_data: List[Dict]) -> io.StringIO:
        # For UHC and ESI. Cigna should overwrite this method
        # gather metadata
        num_rows = len(report_data)
        oop_total = 0

        first_detail_row = 1 if self.header_config else 0
        last_detail_row = num_rows - 1 if self.trailer_config else num_rows

        buffer = io.StringIO()

        # generate header row
        if self.header_config:
            header_obj = FixedWidth(self.header_config)
            self.validate_json_against_config(report_data[0], 0, self.header_config)
            header_obj.update(**report_data[0])
            buffer.write(header_obj.line)

        # generate detail rows
        detail_obj = FixedWidth(self.detail_config)
        for i in range(first_detail_row, last_detail_row):
            self.validate_json_against_config(report_data[i], i, self.detail_config)
            detail_obj.update(**report_data[i])
            buffer.write(detail_obj.line)
            oop_total += self.get_oop_from_row(report_data[i])
        # generate trailer row
        if self.trailer_config:
            trailer_obj = FixedWidth(self.trailer_config)
            trailer_row = report_data[-1]
            record_count = num_rows - (2 if self.header_config else 1)
            trailer_data = self._update_trailer_with_record_counts(
                trailer_row, record_count, oop_total
            )
            self.validate_json_against_config(trailer_data, -1, self.trailer_config)
            trailer_obj.update(**trailer_data)
            buffer.write(trailer_obj.line)
        return buffer

    def validate_json_against_config(
        self, report_data: dict, row: int, expected_config: dict
    ) -> bool:
        expected_columns = set(expected_config.keys())
        available_columns = set(report_data.keys())
        if not available_columns <= expected_columns:
            raise ValueError(
                f"Unexpected columns for report type {self.payer_name} in row {row}: {', '.join(available_columns - expected_columns)}"
            )
        return True

    def get_run_date(self, delimiter: str = "") -> str:
        return self.run_time.strftime(f"%Y{delimiter}%m{delimiter}%d")

    def get_run_time(self, length: int = 6, delimiter: str = "") -> str:
        if not (2 <= length <= 12):
            raise ValueError("The length parameter must be between 2 and 12")
        return self.run_time.strftime(f"%H{delimiter}%M{delimiter}%S{delimiter}%f")[
            :length
        ]

    def get_batch_number(self) -> str:
        return self.run_time.strftime("%y%j")

    @staticmethod
    def get_oop_to_submit(deductible: int, oop_applied: int) -> int:
        return oop_applied

    @staticmethod
    @abstractmethod
    def get_cardholder_id(member_health_plan: MemberHealthPlan) -> str:
        pass

    # ----- Response Processing Methods -----
    def match_response_filename(self, file_name: str) -> bool:
        raise NotImplementedError

    def get_detail_metadata(self, detail_record: dict) -> DetailMetadata:
        raise NotImplementedError

    def get_response_file_date(self, file_name: str) -> Optional[str]:
        raise NotImplementedError

    def get_response_reason_for_code(self, response_code: str) -> Optional[str]:
        raise NotImplementedError

    @staticmethod
    def add_signed_overpunch(number: int) -> str:
        """
        UHC requires that dollar amounts to be in the s9(6)v9(2) format with a signed overpunch.
        This method adds the signed overpunch to the input number.

        Parameters
        ----------
        number: int
        This integer number represents dollar amount in cents.
        For example, 12345 is $123.45

        Returns
        ----------
        A string representing the input number with the sign over punched at the end.

        """
        if number > 99999999:
            err_msg = "Dollar amount larger than 999999.99 is not supported by the UHC and Credence accumulator"
            log.error(err_msg)
            raise Exception(f"Failed to add signed overpunch to number: {number}")
        return overpunch.format(number / 100)

    # ----- Reconciliation Methods -----
    @staticmethod
    @abstractmethod
    def get_cardholder_id_from_detail_dict(detail_row_dict: dict) -> Optional[str]:
        pass

    @staticmethod
    @abstractmethod
    def get_detail_rows(report_rows: list) -> list:
        pass

    @abstractmethod
    def get_dob_from_report_row(self, detail_row_dict: dict) -> date:
        pass

    @abstractmethod
    def get_deductible_from_row(self, detail_row: dict) -> int:
        pass

    @abstractmethod
    def get_oop_from_row(self, detail_row: dict) -> int:
        pass
