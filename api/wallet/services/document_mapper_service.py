from __future__ import annotations

import uuid
from datetime import datetime
from traceback import format_exc
from typing import Optional

import sqlalchemy

from common import document_mapper
from common.document_mapper.client import DocumentMapperClient
from common.document_mapper.models import (
    DocumentMappingFeedback,
    ReceiptExtractionDocumentMappingWithFeedback,
)
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class DocumentMapperService:
    def __init__(
        self,
        document_mapper_base_url: Optional[str] = None,
        document_mapper_client: Optional[DocumentMapperClient] = None,
        session: sqlalchemy.orm.scoping.ScopedSession = None,
    ):
        self.document_mapper_client = document_mapper_client or document_mapper.get_client(
            base_url=document_mapper_base_url  # type: ignore[arg-type]
        )
        self.session = session or db.session

    def get_document_mapping(
        self,
        document_mapping_uuid: uuid.UUID,
    ) -> Optional[ReceiptExtractionDocumentMappingWithFeedback]:
        try:
            return self.document_mapper_client.get_document(
                document_mapping_uuid=document_mapping_uuid
            )
        except Exception:
            log.error(
                "Error calling document mapper service to retrieve mapping with feedback",
                document_mapping_uuid=str(document_mapping_uuid),
                reason=format_exc(),
            )
            return None

    def map_documents(
        self,
        source_ids: list[int],
        service_provider: str,
        service_category: str,
        amount: int,
        date_of_service: datetime,
        patient_name: Optional[str],
    ) -> Optional[ReceiptExtractionDocumentMappingWithFeedback]:
        try:
            payload = self.format_request_body(
                source_ids=source_ids,
                service_provider=service_provider,
                service_category=service_category,
                amount=amount,
                date_of_service=date_of_service,
                patient_name=patient_name,
            )
            return self.document_mapper_client.map_document(request_body=payload)
        except Exception:
            log.error(
                "Error calling document mapper service to create mapping",
                source_ids=str(source_ids),
                service_provider=service_provider,
                service_category=service_category,
                reason=format_exc(),
            )
            return None

    def create_feedback(
        self,
        document_mapping_uuid: uuid.UUID,
        field_name: str,
        updated_by: str,
        previous_value: str,
        new_value: Optional[str] = None,
        feedback_accepted: bool = True,
    ) -> Optional[DocumentMappingFeedback]:
        try:
            payload = self.format_feedback_request_body(
                document_mapping_uuid=document_mapping_uuid,
                field_name=field_name,
                updated_by=updated_by,
                previous_value=previous_value,
                new_value=new_value,
                feedback_accepted=feedback_accepted,
            )
            return self.document_mapper_client.create_feedback(request_body=payload)
        except Exception:
            log.error(
                "Error calling document mapper service to create feedback",
                document_mapping_uuid=document_mapping_uuid,
                field_name=field_name,
                updated_by=updated_by,
                reason=format_exc(),
            )
            return None

    def format_request_body(
        self,
        source_ids: list[int],
        service_provider: str,
        service_category: str,
        amount: int,
        date_of_service: datetime,
        patient_name: Optional[str],
    ) -> dict:
        """
        Helper function that builds the request body for the document mapper document_mapping endpoint
        """
        source_ids_as_str = [str(source_id) for source_id in source_ids]
        request_body = {
            "service_provider": service_provider,
            "service_category": service_category,
            "source_ids": source_ids_as_str,
            "form_data": {
                "amount": str(amount),
                "date_of_service": date_of_service.strftime("%Y-%m-%d"),
                "patient_name": patient_name,
            },
        }
        return request_body

    def format_feedback_request_body(
        self,
        document_mapping_uuid: uuid.UUID,
        field_name: str,
        updated_by: str,
        previous_value: str,
        new_value: Optional[str] = None,
        feedback_accepted: bool = False,
    ) -> dict:
        """
        Helper function that builds the request body for the document mapper document_mapping/feedback endpoint
        """
        request_body = {
            "document_mapping_uuid": str(document_mapping_uuid),
            "field_name": field_name,
            "updated_by": updated_by,
            "previous_value": previous_value,
            "feedback_accepted": feedback_accepted,
        }

        if new_value is not None:
            request_body["new_value"] = new_value

        return request_body
