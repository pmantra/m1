from __future__ import annotations

from traceback import format_exc

from storage.connection import db
from tasks.queues import job
from utils.log import logger
from wallet.constants import INTERNAL_TRUST_DOCUMENT_MAPPER_URL
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_request_source import (
    ReimbursementRequestSource,
    ReimbursementRequestSourceRequests,
)
from wallet.services.document_mapper_service import DocumentMapperService

log = logger(__name__)


@job(service_ns="document_mapper", team_ns="payments_platform")
def map_reimbursement_request_documents(reimbursement_request_id: int) -> None:
    """
    Asynchronously processes documents for a reimbursement request through the document mapper service.
    """
    try:
        # Get the sources associated with this reimbursement request
        sources = (
            db.session.query(ReimbursementRequestSource)
            .join(
                ReimbursementRequestSourceRequests,
                ReimbursementRequestSourceRequests.reimbursement_request_source_id
                == ReimbursementRequestSource.id,
            )
            .filter(
                ReimbursementRequestSourceRequests.reimbursement_request_id
                == reimbursement_request_id
            )
            .all()
        )

        if not sources:
            log.info(
                "No sources found for reimbursement request",
                reimbursement_request_id=str(reimbursement_request_id),
            )
            return

        user_asset_ids = [source.user_asset_id for source in sources]

        reimbursement_request: ReimbursementRequest = (
            db.session.query(ReimbursementRequest)
            .filter(ReimbursementRequest.id == reimbursement_request_id)
            .one()
        )

        document_mapper_service = DocumentMapperService(
            document_mapper_base_url=INTERNAL_TRUST_DOCUMENT_MAPPER_URL
        )

        mapping_result = document_mapper_service.map_documents(
            source_ids=user_asset_ids,
            service_provider=reimbursement_request.service_provider,
            service_category="Fertility",  # TODO: determine how we will decide what the appropriate subcategory is and remove from API
            amount=reimbursement_request.amount,
            date_of_service=reimbursement_request.service_start_date,
            patient_name=reimbursement_request.person_receiving_service,
        )

        if not mapping_result:
            log.error(
                "Failed to map documents for reimbursement request",
                source_ids=user_asset_ids,
                reimbursement_request_id=str(reimbursement_request_id),
            )
            return

        # Update all associated sources with the document mapping UUID
        for source in sources:
            source.document_mapping_uuid = (
                mapping_result.document_mapping.document_mapping_uuid
            )

        db.session.commit()
        log.info(
            "Successfully updated document mapping UUID for sources",
            reimbursement_request_id=str(reimbursement_request_id),
            document_mapping_uuid=str(
                mapping_result.document_mapping.document_mapping_uuid
            ),
            source_ids=[str(source.id) for source in sources],
        )

    except Exception:
        log.error(
            "Error in document mapping job",
            source_ids=user_asset_ids,
            reimbursement_request_id=str(reimbursement_request_id),
            reason=format_exc(),
        )
