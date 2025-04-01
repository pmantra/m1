from __future__ import annotations

from typing import Mapping, Optional
from uuid import UUID

from requests import Response

from common.base_triforce_client import BaseTriforceClient
from common.document_mapper.models import (
    DocumentMappingFeedback,
    ReceiptExtractionDocumentMappingWithFeedback,
    from_api_response_feedback,
    from_api_response_with_feedback,
)
from utils.log import logger

log = logger(__name__)

SERVICE_NAME = "document-mapper"


class DocumentMapperClient(BaseTriforceClient):
    def __init__(
        self,
        *,
        base_url: str,
        headers: Optional[dict[str, str]] = None,
        internal: bool = False,
    ) -> None:
        super().__init__(
            base_url=base_url,
            headers=headers,
            service_name=SERVICE_NAME,
            internal=internal,
            log=log,
        )

    def map_document(
        self,
        request_body: dict,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Optional[ReceiptExtractionDocumentMappingWithFeedback]:
        response = self.make_service_request(
            "document_mapping",
            data=request_body,
            method="POST",
            extra_headers=headers,
        )
        if response.status_code != 200:
            log.error("Failed to create DocumentMapper object", response=response)
            raise DocumentMapperClientException(
                message=response.text, code=response.status_code, response=response
            )
        return from_api_response_with_feedback(response.json())

    def create_feedback(
        self,
        request_body: dict,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Optional[DocumentMappingFeedback]:
        response = self.make_service_request(
            "document_mapping/feedback",
            data=request_body,
            method="POST",
            extra_headers=headers,
        )
        if response.status_code != 200:
            log.error(
                "Failed to create DocumentMapperFeedback object", response=response
            )
            raise DocumentMapperClientException(
                message=response.text, code=response.status_code, response=response
            )
        return from_api_response_feedback(response.json())

    def get_document(
        self,
        document_mapping_uuid: UUID,
        headers: Optional[Mapping[str, str]] = None,
    ) -> Optional[ReceiptExtractionDocumentMappingWithFeedback]:
        response = self.make_service_request(
            f"document_mapping/{str(document_mapping_uuid)}",
            method="GET",
            extra_headers=headers,
        )
        if response.status_code != 200:
            log.error("Failed to retrieve DocumentMapper object", response=response)
            raise DocumentMapperClientException(
                message=response.text, code=response.status_code, response=response
            )
        return from_api_response_with_feedback(response.json())


class DocumentMapperClientException(Exception):
    __slots__ = ("code", "response", "message")

    def __init__(self, message: str, code: int, response: Optional[Response]):
        super().__init__(message)
        self.message = message
        self.code = code
        self.response = response
