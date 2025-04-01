from __future__ import annotations

import uuid
from unittest.mock import Mock, patch

import pytest

from common.document_mapper.models import (
    ReceiptExtractionDocumentMapping,
    ReceiptExtractionDocumentMappingWithFeedback,
)
from wallet.models.reimbursement import (
    ReimbursementRequest,
    ReimbursementRequestCategory,
)
from wallet.models.reimbursement_request_source import ReimbursementRequestSource
from wallet.pytests.factories import (
    ReimbursementRequestCategoryFactory,
    ReimbursementRequestFactory,
    ReimbursementRequestSourceFactory,
    ReimbursementRequestSourceRequestsFactory,
)
from wallet.tasks.document_mapping import map_reimbursement_request_documents


@pytest.fixture
def mock_document_mapper_service():
    with patch("wallet.tasks.document_mapping.DocumentMapperService") as mock_service:
        mock_instance = Mock()
        mock_service.return_value = mock_instance
        yield mock_instance


def test_map_reimbursement_request_documents_success(
    mock_document_mapper_service, qualified_wallet, valid_alegeus_plan_hra
):
    document_mapping_uuid = uuid.uuid4()
    category: ReimbursementRequestCategory = ReimbursementRequestCategoryFactory.create(
        label="Preservation", reimbursement_plan=valid_alegeus_plan_hra
    )

    sources = ReimbursementRequestSourceFactory.create_batch(
        reimbursement_wallet_id=qualified_wallet.id, size=2
    )

    reimbursement_request = ReimbursementRequestFactory.create(
        service_provider="Test Provider",
        wallet=qualified_wallet,
        reimbursement_wallet_id=qualified_wallet.id,
        reimbursement_request_category_id=category.id,
    )

    for source in sources:
        ReimbursementRequestSourceRequestsFactory.create(
            reimbursement_request_id=reimbursement_request.id,
            reimbursement_request_source_id=source.id,
        )
    mock_mapping_result = ReceiptExtractionDocumentMappingWithFeedback(
        document_mapping=ReceiptExtractionDocumentMapping(
            document_mapping_uuid=document_mapping_uuid,
            source_ids=[1, 2],
            service_provider="Test",
            patient_name="Test",
            payment_amount="1000",
            service_evidence=True,
            date_of_service="2020-01-1",
        ),
        feedback=[],
    )
    mock_document_mapper_service.map_documents.return_value = mock_mapping_result

    map_reimbursement_request_documents(reimbursement_request.id)

    mock_document_mapper_service.map_documents.assert_called_once_with(
        source_ids=[source.user_asset_id for source in sources],
        service_provider="Test Provider",
        service_category="Fertility",
        amount=reimbursement_request.amount,
        date_of_service=reimbursement_request.service_start_date,
        patient_name=reimbursement_request.person_receiving_service,
    )

    from storage.connection import db

    saved_sources = (
        db.session.query(ReimbursementRequestSource)
        .filter(ReimbursementRequestSource.id.in_([s.id for s in sources]))
        .all()
    )

    for source in saved_sources:
        assert source.document_mapping_uuid == document_mapping_uuid


def test_map_reimbursement_request_documents_mapping_failure(
    mock_document_mapper_service, qualified_wallet, valid_alegeus_plan_hra
):
    category = ReimbursementRequestCategoryFactory.create(
        label="Preservation", reimbursement_plan=valid_alegeus_plan_hra
    )

    sources = ReimbursementRequestSourceFactory.create_batch(
        reimbursement_wallet_id=qualified_wallet.id,
        size=2,
        document_mapping_uuid=None,
    )

    reimbursement_request: ReimbursementRequest = ReimbursementRequestFactory.create(
        service_provider="Test Provider",
        wallet=qualified_wallet,
        reimbursement_wallet_id=qualified_wallet.id,
        reimbursement_request_category_id=category.id,
    )

    for source in sources:
        ReimbursementRequestSourceRequestsFactory.create(
            reimbursement_request_id=reimbursement_request.id,
            reimbursement_request_source_id=source.id,
        )

    mock_document_mapper_service.map_documents.return_value = None

    map_reimbursement_request_documents(reimbursement_request.id)

    mock_document_mapper_service.map_documents.assert_called_once_with(
        source_ids=[source.user_asset_id for source in sources],
        service_provider="Test Provider",
        service_category="Fertility",
        amount=reimbursement_request.amount,
        date_of_service=reimbursement_request.service_start_date,
        patient_name=reimbursement_request.person_receiving_service,
    )

    from storage.connection import db

    saved_sources = (
        db.session.query(ReimbursementRequestSource)
        .filter(ReimbursementRequestSource.id.in_([s.id for s in sources]))
        .all()
    )

    for source in saved_sources:
        assert source.document_mapping_uuid is None


def test_map_reimbursement_request_documents_no_sources(
    mock_document_mapper_service, qualified_wallet, valid_alegeus_plan_hra
):
    category = ReimbursementRequestCategoryFactory.create(
        label="Preservation", reimbursement_plan=valid_alegeus_plan_hra
    )

    reimbursement_request = ReimbursementRequestFactory.create(
        service_provider="Test Provider",
        wallet=qualified_wallet,
        reimbursement_wallet_id=qualified_wallet.id,
        reimbursement_request_category_id=category.id,
    )

    map_reimbursement_request_documents(reimbursement_request.id)

    mock_document_mapper_service.map_documents.assert_not_called()
