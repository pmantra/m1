from __future__ import annotations

from marshmallow import fields as v3_fields
from marshmallow_v1 import fields

from utils.log import logger
from views.schemas.base import MavenDateTimeV3, MavenSchemaV3, StringWithDefaultV3
from views.schemas.common import MavenDateTime, MavenSchema
from wallet.models.reimbursement_request_source import ReimbursementRequestSource
from wallet.schemas.currency import MoneyAmountSchema
from wallet.schemas.reimbursement_category import (
    ReimbursementCategorySchema,
    ReimbursementRequestCategoryContainerSchema,
    ReimbursementRequestExpenseTypesSchema,
)

log = logger(__name__)


class ReimbursementRequestSummarySchema(MavenSchema):
    reimbursement_request_maximum = fields.Integer()
    reimbursement_spent = fields.Integer()
    currency_code = fields.String()
    wallet_shareable = fields.Boolean(default=False)
    category_breakdown = fields.Nested(
        ReimbursementRequestCategoryContainerSchema, many=True
    )
    expense_types = fields.Nested(ReimbursementRequestExpenseTypesSchema, many=True)


class ReimbursementRequestSourceSchema(MavenSchema):
    type = fields.String()
    source_id = fields.String()

    content_type = fields.Function(lambda source: source.user_asset.content_type)
    source_url = fields.Method("get_source_url")
    inline_url = fields.Method("get_inline_url")

    created_at = MavenDateTime()
    file_name = fields.Function(lambda source: source.user_asset.file_name)

    def get_source_url(
        self, reimbursement_request_source: ReimbursementRequestSource | None
    ) -> None | str:
        if reimbursement_request_source is None:
            return None

        try:
            if not hasattr(reimbursement_request_source, "user_asset"):
                return None
            return reimbursement_request_source.user_asset.direct_download_url()
        except Exception as e:
            log.exception(
                "Unexpected error generating reimbursement request asset source url",
                exception=e,
            )
            return None

    # By passing inline, we change the Content-Disposition response header to
    # indicate that the content should be displayed inline in the browser, that
    # is, as a Web page or as part of a Web page, rather than as an attachment,
    # that is downloaded and saved locally.
    def get_inline_url(
        self, reimbursement_request_source: ReimbursementRequestSource | None
    ) -> None | str:
        if reimbursement_request_source is None:
            return None

        try:
            return reimbursement_request_source.user_asset.direct_download_url(
                inline=True
            )
        except Exception as e:
            log.exception(
                "Unexpected error generating reimbursement request asset inline url",
                exception=e,
            )
            return None


class ReimbursementRequestSourceSchemaV3(MavenSchemaV3):
    type = StringWithDefaultV3(default="")
    source_id = StringWithDefaultV3(default="")

    content_type = v3_fields.Function(
        lambda source: source.user_asset.content_type
        if hasattr(source, "user_asset")
        else None
    )
    source_url = v3_fields.Method("get_source_url")
    inline_url = v3_fields.Method("get_inline_url")

    created_at = MavenDateTimeV3(default=None)
    file_name = v3_fields.Function(
        lambda source: source.user_asset.file_name
        if hasattr(source, "user_asset")
        else None
    )

    def get_source_url(
        self, reimbursement_request_source: ReimbursementRequestSource | None
    ) -> None | str:
        if reimbursement_request_source is None:
            return None

        try:
            return reimbursement_request_source.user_asset.direct_download_url()
        except Exception as e:
            log.exception(
                "Unexpected error generating reimbursement request asset source url",
                exception=e,
            )
            return None

    # By passing inline, we change the Content-Disposition response header to
    # indicate that the content should be displayed inline in the browser, that
    # is, as a Web page or as part of a Web page, rather than as an attachment,
    # that is downloaded and saved locally.
    def get_inline_url(
        self, reimbursement_request_source: ReimbursementRequestSource | None
    ) -> None | str:
        if reimbursement_request_source is None:
            return None

        try:
            if not hasattr(reimbursement_request_source, "user_asset"):
                return None
            return reimbursement_request_source.user_asset.direct_download_url(
                inline=True
            )
        except Exception as e:
            log.exception(
                "Unexpected error generating reimbursement request asset inline url",
                exception=e,
            )
            return None


class ReimbursementRequestCostShareDetailsSchema(MavenSchema):
    reimbursement_amount = fields.String(required=False, allow_none=True, default=None)
    reimbursement_expected_message = fields.String(
        required=False, allow_none=True, default=None
    )
    original_claim_amount = fields.String(required=False, allow_none=True, default=None)


class ReimbursementRequestSchema(MavenSchema):
    id = fields.String()
    label = fields.Function(
        # handle test cases where request is not a ReimbursementRequest object
        lambda request: request.formatted_label
        if hasattr(request, "formatted_label")
        else ""
    )
    service_provider = fields.String()
    person_receiving_service = fields.String()
    employee_name = fields.String()
    description = fields.String()
    amount = fields.Integer()
    benefit_amount = fields.Nested(MoneyAmountSchema)
    state = fields.Function(lambda request: request.state.value)
    state_description = fields.String()
    category = fields.Nested(
        ReimbursementCategorySchema(
            exclude=(
                "reimbursement_request_category_maximum",
                "reimbursement_request_category_maximum_amount",
                "direct_payment_eligible",
                "credit_maximum",
                "credits_remaining",
                "is_fertility_category",
                "is_unlimited",
            )
        )
    )
    source = fields.Nested(ReimbursementRequestSourceSchema, attribute="first_source")
    sources = fields.Nested(ReimbursementRequestSourceSchema, many=True)
    service_start_date = MavenDateTime()
    service_end_date = MavenDateTime()
    created_at = MavenDateTime()
    taxation_status = fields.String()
    reimbursement_type = fields.Function(
        lambda request: request.reimbursement_type.name
    )
    cost_share_details = fields.Nested(
        ReimbursementRequestCostShareDetailsSchema, allow_null=True
    )


class ReimbursementRequestStateSchema(MavenSchema):
    needs_attention = fields.Nested(ReimbursementRequestSchema, many=True)
    transaction_history = fields.Nested(ReimbursementRequestSchema, many=True)
    most_recent = fields.Nested(ReimbursementRequestSchema, many=True)


class ReimbursementRequestDataSchema(MavenSchema):
    summary = fields.Nested(ReimbursementRequestSummarySchema)
    reimbursement_requests = fields.Nested(ReimbursementRequestSchema, many=True)


class ReimbursementRequestMetaSchema(MavenSchema):
    reimbursement_wallet_id = fields.String()
    category = fields.String()


class ReimbursementRequestResponseSchema(MavenSchema):
    meta = fields.Nested(ReimbursementRequestMetaSchema(exclude="category"))
    data = fields.Nested(ReimbursementRequestDataSchema)


class ReimbursementRequestWithCategoryResponseSchema(MavenSchema):
    meta = fields.Nested(ReimbursementRequestMetaSchema())
    data = fields.Nested(ReimbursementRequestDataSchema)


# schemas to separate reimbursement_requests into needs attention and transaction history lists
class ReimbursementRequestStateDataSchema(MavenSchema):
    summary = fields.Nested(ReimbursementRequestSummarySchema)
    reimbursement_requests = fields.Nested(ReimbursementRequestStateSchema())


class ReimbursementRequestStateWithCategoryResponseSchema(MavenSchema):
    meta = fields.Nested(ReimbursementRequestMetaSchema())
    data = fields.Nested(ReimbursementRequestStateDataSchema)


class ReimbursementRequestStateResponseSchema(MavenSchema):
    meta = fields.Nested(ReimbursementRequestMetaSchema(exclude="category"))
    data = fields.Nested(ReimbursementRequestStateDataSchema)
