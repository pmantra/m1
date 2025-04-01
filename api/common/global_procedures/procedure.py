from __future__ import annotations

import datetime
import os
from typing import Literal, Mapping, Optional, TypedDict
from urllib.parse import quote

from common.base_triforce_client import BaseTriforceClient
from common.global_procedures.constants import (
    PROCEDURE_SERVICE_INTERNAL_PATH,
    PROCEDURE_SERVICE_NAME,
    PROCEDURE_SERVICE_URL,
)
from utils.log import logger

log = logger(__name__)


class MissingProcedureData(ValueError):
    pass


def get_base_url(internal: bool) -> str:
    if internal:
        internal_gateway_url = os.environ.get("INTERNAL_GATEWAY_URL", None)
        if internal_gateway_url is None:
            return PROCEDURE_SERVICE_URL
        else:
            return f"{internal_gateway_url}{PROCEDURE_SERVICE_INTERNAL_PATH}"
    return PROCEDURE_SERVICE_URL


def is_date_str_valid_in_iso8601_format(date_string: str | None) -> bool:
    if date_string is None:
        return False
    try:
        datetime.datetime.strptime(date_string, "%Y-%m-%d")
        return True
    except ValueError:
        log.warn(
            f"The date {date_string} sent to the procedure service is not valid. It must follow the ISO 8601 date format"
        )
        return False


class ProcedureService(BaseTriforceClient):
    def __init__(
        self,
        *,
        headers: dict[str, str] = None,  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Dict[str, str]")
        internal: bool = False,
        base_url: str = None,  # type: ignore[assignment] # Incompatible default for argument "base_url" (default has type "None", argument has type "str")
    ) -> None:
        super().__init__(
            base_url=get_base_url(internal) if not base_url else base_url,
            headers=headers,
            service_name=PROCEDURE_SERVICE_NAME,
            internal=internal,
            log=log,
        )

    def get_procedure_by_id(  # type: ignore[return] # Missing return statement
        self, *, procedure_id: Optional[str] = None, headers: Mapping[str, str] = None  # type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
    ) -> GlobalProcedure | PartialProcedure | None:
        response = self.make_service_request(
            f"/global/{procedure_id}", method="GET", extra_headers=headers
        )
        if response.status_code == 200:
            page = response.json()
            return unmarshal_procedure(page)

    def get_procedures_by_ids(
        self, *, procedure_ids: list[str] = None, headers: Mapping[str, str] = None  # type: ignore[assignment] # Incompatible default for argument "procedure_ids" (default has type "None", argument has type "List[str]") #type: ignore[assignment] # Incompatible default for argument "headers" (default has type "None", argument has type "Mapping[str, str]")
    ) -> list[GlobalProcedure | PartialProcedure]:
        response = self.make_service_request(
            "/global/search/",
            data={"procedure_ids": procedure_ids},
            method="POST",
            extra_headers=headers,
        )
        if response.status_code == 200:
            page = response.json()
            return unmarshal_procedures(page["results"])

        return []

    def get_procedures_by_names(
        self,
        *,
        procedure_names: list[str] | None = None,
        headers: Mapping[str, str] | None = None,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> list[GlobalProcedure | PartialProcedure]:
        data = {
            "procedure_names": procedure_names,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        response = self.make_service_request(
            "/global/search/",
            data=data,
            method="POST",
            extra_headers=headers,
        )

        if response.status_code == 200:
            page = response.json()
            return unmarshal_procedures(page["results"])

        return []

    def get_procedures_by_ndc_numbers(
        self,
        *,
        ndc_numbers: list[str] | None = None,
        headers: Mapping[str, str] | None = None,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
    ) -> list[GlobalProcedure | PartialProcedure]:

        data: dict[str, list[str] | str] = {
            "ndc_numbers": ndc_numbers,
        }

        if start_date is not None:
            data["start_date"] = start_date.isoformat()
        if end_date is not None:
            data["end_date"] = end_date.isoformat()

        response = self.make_service_request(
            "/global/search/",
            data=data,
            method="POST",
            extra_headers=headers,
        )
        if response.status_code == 200:
            page = response.json()
            return unmarshal_procedures(page["results"])

        return []

    def list_all_procedures(
        self,
        *,
        headers: Mapping[str, str] | None = None,
        start_date: datetime.date | None = None,
        end_date: datetime.date | None = None,
    ) -> list[GlobalProcedure | PartialProcedure]:

        filters = {}
        if start_date is not None:
            filters["start_date"] = start_date.isoformat()
        if end_date is not None:
            filters["end_date"] = end_date.isoformat()

        url = "/global/"
        if filters:
            encoded_filters = quote(str(filters).replace("'", '"'))
            url = f"/global?filter={encoded_filters}"

        response = self.make_service_request(
            url,
            method="GET",
            extra_headers=headers,
        )
        if response.status_code == 200:
            page = response.json()
            return unmarshal_procedures(page)

        return []

    def create_global_procedure(  # type: ignore[return] # Missing return statement
        self,
        *,
        global_procedure: GlobalProcedure,
        headers: Mapping[str, str] | None = None,
    ) -> GlobalProcedure | None:

        # It is a temporary solution for the case when start_date/end_date is not explicitly set, and it
        # may be updated in the future. The callers of create_global_procedure should explicitly set
        # start_date/end_date
        if not is_date_str_valid_in_iso8601_format(global_procedure.get("start_date")):
            global_procedure["start_date"] = datetime.date(2024, 1, 1).isoformat()
        if not is_date_str_valid_in_iso8601_format(global_procedure.get("end_date")):
            global_procedure["end_date"] = datetime.date(2025, 12, 31).isoformat()

        response = self.make_service_request(
            "/global/",
            data=global_procedure,
            method="POST",
            extra_headers=headers,
        )
        if response.status_code == 200:
            page = response.json()
            return unmarshal_procedure(page)  # type: ignore[return-value] # Incompatible return value type (got "Union[GlobalProcedure, PartialProcedure, None]", expected "Optional[GlobalProcedure]")


def unmarshal_procedures(data: list[dict]) -> list[GlobalProcedure | PartialProcedure]:
    iter = (unmarshal_procedure(d) for d in data)
    return [p for p in iter if p is not None]


def unmarshal_procedure(data: dict) -> GlobalProcedure | PartialProcedure | None:
    given_fields = {*data.keys()}
    required_fields = {*CoreProcedureFields.__annotations__.keys()}
    if given_fields.issuperset(required_fields) is False:
        log.warning(
            "Got an un-parseable response from procedures service.",
            received_fields=[*given_fields],
        )
        return None

    created_at = datetime.datetime.fromisoformat(data["created_at"])
    updated_at = datetime.datetime.fromisoformat(data["updated_at"])

    parsed = {k: data[k] for k in required_fields}
    parsed.update(
        created_at=created_at,
        updated_at=updated_at,
    )
    gp_keys = GlobalProcedure.__annotations__.keys()
    if given_fields.issuperset(gp_keys):
        parsed.update(
            is_partial=False,
            partial_procedures=[
                unmarshal_procedure(p) for p in data["partial_procedures"]
            ],
        )
    else:
        parsed.update(
            is_partial=True, parent_procedure_ids=data.get("parent_procedure_ids")
        )

    return parsed  # type: ignore[return-value] # Incompatible return value type (got "Dict[str, Any]", expected "Union[GlobalProcedure, PartialProcedure, None]")


class PaginatedResponse(TypedDict):
    next: dict | None
    prev: dict | None
    results: list[GlobalProcedure]


class CoreProcedureFields(TypedDict):
    id: str
    name: str
    credits: int
    annual_limit: int
    is_diagnostic: bool
    cost_sharing_category: str
    ndc_number: str
    hcpcs_code: str
    type: str
    start_date: str
    end_date: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class GlobalProcedure(CoreProcedureFields):
    is_partial: Literal[False]
    partial_procedures: list[PartialProcedure]


class PartialProcedure(CoreProcedureFields):
    is_partial: Literal[True]
    parent_procedure_ids: list[str]
