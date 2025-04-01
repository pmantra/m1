from __future__ import annotations

from datetime import datetime, timedelta, timezone
from traceback import format_exc
from typing import List, Set

import pytz
from flask import request
from flask_restful import abort

from common import stats
from common.document_mapper.helpers import receipt_validation_ops_view_enabled
from common.services.api import PermissionedUserResource
from models.enterprise import UserAsset
from storage.connection import db
from utils.log import logger
from utils.marshmallow_experiment import marshmallow_experiment_enabled
from wallet.models.constants import (
    FERTILITY_EXPENSE_TYPES,
    BenefitTypes,
    InfertilityDX,
    MemberType,
    ReimbursementRequestSourceUploadSource,
    ReimbursementRequestState,
    ReimbursementRequestType,
    TaxationStateConfig,
    WalletUserStatus,
)
from wallet.models.models import ReimbursementPostRequest
from wallet.models.reimbursement import (
    ReimbursementRequest,
    ReimbursementRequestCategory,
    WalletExpenseSubtype,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
    ReimbursementOrgSettingsExpenseType,
)
from wallet.models.reimbursement_request_source import (
    ReimbursementRequestSource,
    ReimbursementRequestSourceRequests,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.schemas.reimbursement import (
    ReimbursementRequestResponseSchema,
    ReimbursementRequestSchema,
    ReimbursementRequestSourceSchema,
    ReimbursementRequestSourceSchemaV3,
    ReimbursementRequestStateResponseSchema,
    ReimbursementRequestStateWithCategoryResponseSchema,
    ReimbursementRequestWithCategoryResponseSchema,
)
from wallet.schemas.reimbursement_v3 import ReimbursementRequestSchemaV3
from wallet.services.annual_questionnaire_lib import (
    get_plan_year_if_survey_needed_for_target_date,
    is_questionnaire_needed_for_wallet_expense_type,
)
from wallet.services.currency import DEFAULT_CURRENCY_CODE, CurrencyService
from wallet.services.reimbursement_benefits import get_member_type_details_from_wallet
from wallet.services.reimbursement_budget_calculator import (
    get_allowed_category_associations_by_wallet,
    get_reimbursement_category_breakdown,
)
from wallet.services.reimbursement_request import ReimbursementRequestService
from wallet.tasks.document_mapping import map_reimbursement_request_documents
from wallet.utils.alegeus.claims.create import upload_claim_attachments_to_alegeus
from wallet.utils.alegeus.debit_cards.document_linking import (
    upload_card_transaction_attachments_to_alegeus,
)
from wallet.utils.alegeus.debit_cards.transactions.process_user_transactions import (
    get_all_debit_card_transactions,
)

log = logger(__name__)


class ReimbursementRequestResource(PermissionedUserResource):
    """Reimbursement request information for the main Maven Wallet screen."""

    def __init__(self) -> None:
        self.currency_service = CurrencyService()
        self.reimbursement_request_service = ReimbursementRequestService()

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        args, wallet = self.validate_args()

        if wallet.debit_card:
            success = get_all_debit_card_transactions(wallet)
            if not success:
                log.warning(
                    "Unable to get_all_debit_card_transactions for wallet.",
                    reimbursement_wallet_id=str(wallet.id),
                )

        category = args.get("category")

        # calculate user's reimbursements from their approved and reimbursed requests
        approved_amount_by_category = wallet.approved_amount_by_category

        allowed_categories: List[
            ReimbursementOrgSettingCategoryAssociation
        ] = get_allowed_category_associations_by_wallet(wallet, category)

        # update wallet categories with the associated benefit_type
        self.set_reimbursement_category_attributes(allowed_categories, wallet)

        reimbursement_requests: List[
            ReimbursementRequest
        ] = self.reimbursement_request_service.get_reimbursement_requests_for_wallet(
            wallet=wallet, category=category
        )

        for reimbursement in reimbursement_requests:
            reimbursement.benefit_amount = self.currency_service.format_amount_obj(
                amount=reimbursement.amount,
                currency_code=reimbursement.benefit_currency_code,
            )

        # Put everything into this one function cause its kinda messy to put it in the calling
        log.info(
            "Wallet Shareability from wallet method:",
            wallet_id=str(wallet.id),
            wallet_shareable=wallet.is_shareable,
        )
        expense_types: list[dict] = get_expense_types_for_wallet(
            wallet=wallet, allowed_categories=allowed_categories
        )
        # format data for output
        data = {
            "meta": args,
            "data": {
                "summary": {
                    "reimbursement_request_maximum": wallet.total_available_amount,
                    "reimbursement_spent": wallet.total_approved_amount,
                    "currency_code": get_summary_currency_code(
                        category_associations=allowed_categories
                    ),
                    "wallet_shareable": wallet.is_shareable,
                    "category_breakdown": (
                        get_reimbursement_category_breakdown(
                            self.currency_service,
                            approved_amount_by_category,
                            allowed_categories,
                            wallet.available_credit_amount_by_category,
                        )
                    ),
                    "expense_types": expense_types,
                },
                "reimbursement_requests": reimbursement_requests,
            },
        }

        if category:
            schema = ReimbursementRequestWithCategoryResponseSchema()
        else:
            schema = ReimbursementRequestResponseSchema()
        return schema.dump(data).data

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        try:
            # launch darkly flag
            experiment_enabled = marshmallow_experiment_enabled(
                "experiment-marshmallow-reimbursement-request-resource",
                self.user.esp_id if self.user else None,
                self.user.email if self.user else None,
                default=False,
            )

            data = ReimbursementPostRequest.from_request(
                request.json if request.is_json else None
            )
            log.info(
                "Reimbursement request successfully parsed",
                currency_code=data.currency_code,
                transaction_amount=str(data.amount),
            )
            new_reimbursement_request = ReimbursementRequestService().create_reimbursement_request(
                data,
                self.user,
                upload_source=ReimbursementRequestSourceUploadSource.INITIAL_SUBMISSION,
            )
            if receipt_validation_ops_view_enabled(
                new_reimbursement_request.service_provider
            ):
                map_reimbursement_request_documents.delay(new_reimbursement_request.id)

            # Set the benefit_amount obj
            new_reimbursement_request.benefit_amount = (
                self.currency_service.format_amount_obj(
                    amount=new_reimbursement_request.amount,
                    currency_code=new_reimbursement_request.benefit_currency_code,
                )
            )

            to_return = (
                ReimbursementRequestSchemaV3().dump(new_reimbursement_request)
                if experiment_enabled
                else ReimbursementRequestSchema().dump(new_reimbursement_request).data
            )
            self._add_plan_year_to_output_if_needed(
                new_reimbursement_request, to_return
            )

            return to_return
        except KeyError as e:
            log.info(
                "Reimbursement Request creation failed: Missing required field", error=e
            )
            abort(400, message=f"Missing required field: [{e.args[0]}]")
        except ValueError as e:
            # Exact validation failures are logged separately
            log.info(
                "Reimbursement Request creation failed: Validation failed", error=e
            )
            abort(400, message=f"Validation failed, due to: {e}")
        except Exception as e:
            log.warning("Reimbursement Request creation failed: Other error", error=e)
            abort(500, message=f"Could not complete request, due to: {e}")

    def _add_plan_year_to_output_if_needed(
        self, reimbursement_request: ReimbursementRequest, payload_to_modify: dict
    ) -> None:
        try:
            wallet = ReimbursementWallet.query.get(
                reimbursement_request.reimbursement_wallet_id
            )
            if (
                is_questionnaire_needed_for_wallet_expense_type(wallet)
                and (
                    plan_year := get_plan_year_if_survey_needed_for_target_date(
                        user=self.user,
                        wallet=wallet,
                        target_date=reimbursement_request.service_start_date,
                    )
                )
                is not None
            ):
                log.info(
                    "Computed plan year.",
                    reimbursement_request_id=str(reimbursement_request.id),
                    user_id=self.user.id,
                    wallet_id=str(wallet.id),
                    target_date=str(reimbursement_request.service_start_date),
                    plan_year=plan_year,
                )
                payload_to_modify["required_plan_year"] = str(plan_year)
        except Exception as e:
            log.info(
                "Unable to compute plan year.",
                reimbursement_request_id=str(reimbursement_request.id),
                error=e,
                reason=format_exc(),
            )

    def validate_args(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        args = get_reimbursement_request(request.args)
        wallet_id = args.get("reimbursement_wallet_id")

        wallet = (
            db.session.query(ReimbursementWallet)
            .filter(ReimbursementWallet.id == wallet_id)
            .one_or_none()
        )
        if not wallet:
            abort(404, message="Wallet not found")
        wallet_is_affiliated_with_user = (
            db.session.query(ReimbursementWalletUsers.id)
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == wallet_id,
                ReimbursementWalletUsers.user_id == self.user.id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
            )
            .count()
            == 1
        )

        if not wallet_is_affiliated_with_user:
            abort(400, message="Invalid User")

        return args, wallet

    @staticmethod
    def set_reimbursement_category_attributes(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        reimbursement_category_associations: List[
            ReimbursementOrgSettingCategoryAssociation
        ],
        reimbursement_wallet: ReimbursementWallet,
    ) -> None:
        type_details = get_member_type_details_from_wallet(reimbursement_wallet)
        is_gold = type_details.member_type == MemberType.MAVEN_GOLD

        for association in reimbursement_category_associations:
            category = association.reimbursement_request_category
            category.benefit_type = association.benefit_type
            category.num_cycles = association.num_cycles
            category.is_fertility_category = category.has_fertility_expense_type()
            category.direct_payment_eligible = (
                category.has_fertility_expense_type() and is_gold
            )


class ReimbursementRequestDetailsResource(PermissionedUserResource):
    """Details for a single reimbursement request"""

    def __init__(self) -> None:
        self.currency_service = CurrencyService()
        self.reimbursement_request_service = ReimbursementRequestService()

    def get(self, reimbursement_request_id: int) -> tuple[dict, int]:
        reimbursement_request = (
            self.reimbursement_request_service.get_reimbursement_request_by_id(
                reimbursement_request_id
            )
        )

        if reimbursement_request:
            rr_with_details = self.reimbursement_request_service.get_reimbursement_request_with_cost_breakdown_details(
                reimbursement_request=reimbursement_request
            )
            return ({"data": rr_with_details}, 200)
        else:
            message = "Reimbursement request not found."
            log.warning(message, reimbursement_request_id=reimbursement_request_id)
            abort(404, message=message)
            return {}, 404


class ReimbursementRequestStateResource(PermissionedUserResource):
    """Reimbursement request information with state for the main Maven Wallet screen."""

    def __init__(self) -> None:
        self.currency_service = CurrencyService()
        self.reimbursement_request_service = ReimbursementRequestService()

    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        args, wallet = self.validate_args()

        category = args.get("category", None)

        reimbursement_requests: list[
            ReimbursementRequest
        ] = self.reimbursement_request_service.get_reimbursement_requests_for_wallet(
            wallet=wallet, category=category
        )

        # calculate user's reimbursements from their approved and reimbursed requests
        approved_amount_by_category = wallet.approved_amount_by_category

        allowed_categories: list[
            ReimbursementOrgSettingCategoryAssociation
        ] = get_allowed_category_associations_by_wallet(wallet, category)

        # update wallet categories with the associated benefit_type
        self.set_reimbursement_category_attributes_for_reimbursement_requests(wallet)

        expense_types: list[dict] = get_expense_types_for_wallet(
            wallet=wallet, allowed_categories=allowed_categories
        )

        # format data for output
        data = {
            "meta": args,
            "data": {
                "summary": {
                    "reimbursement_request_maximum": wallet.total_available_amount,
                    "reimbursement_spent": wallet.total_approved_amount,
                    "currency_code": get_summary_currency_code(
                        category_associations=allowed_categories
                    ),
                    "category_breakdown": get_reimbursement_category_breakdown(
                        self.currency_service,
                        approved_amount_by_category,
                        allowed_categories,
                        wallet.available_credit_amount_by_category,
                    ),
                    "expense_types": expense_types,
                },
                "reimbursement_requests": self.get_reimbursement_requests_with_state(
                    reimbursement_requests
                ),
            },
        }

        if category:
            schema = ReimbursementRequestStateWithCategoryResponseSchema()
        else:
            schema = ReimbursementRequestStateResponseSchema()

        return schema.dump(data).data

    def validate_args(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        args = get_reimbursement_request(request.args)
        wallet_id = args["reimbursement_wallet_id"]

        wallet = (
            db.session.query(ReimbursementWallet)
            .filter(ReimbursementWallet.id == wallet_id)
            .one_or_none()
        )
        if not wallet:
            abort(404, message="Wallet not found")
        wallet_is_affiliated_with_user = (
            db.session.query(ReimbursementWalletUsers.id)
            .filter(
                ReimbursementWalletUsers.reimbursement_wallet_id == wallet_id,
                ReimbursementWalletUsers.user_id == self.user.id,
                ReimbursementWalletUsers.status == WalletUserStatus.ACTIVE,
            )
            .count()
            == 1
        )
        if not wallet_is_affiliated_with_user:
            abort(400, message="Invalid User")

        return args, wallet

    def get_reimbursement_requests_with_state(
        self, reimbursement_requests: List[ReimbursementRequest]
    ) -> dict:
        needs_attention_states: set[ReimbursementRequestState] = {
            ReimbursementRequestState.NEEDS_RECEIPT,
            ReimbursementRequestState.PENDING,
            ReimbursementRequestState.INSUFFICIENT_RECEIPT,
            ReimbursementRequestState.NEW,
            ReimbursementRequestState.APPROVED,
            ReimbursementRequestState.RECEIPT_SUBMITTED,
        }
        needs_attention: list[ReimbursementRequest] = []
        transaction_history_states: set[ReimbursementRequestState] = {
            ReimbursementRequestState.REIMBURSED,
            ReimbursementRequestState.INELIGIBLE_EXPENSE,
            ReimbursementRequestState.REFUNDED,
            ReimbursementRequestState.RESOLVED,
            ReimbursementRequestState.DENIED,
        }
        transaction_history: list[ReimbursementRequest] = []

        for item in reimbursement_requests:
            state = item.state
            item.benefit_amount = self.currency_service.format_amount_obj(
                amount=item.amount, currency_code=item.benefit_currency_code
            )
            item.category = self.format_category_from_reimbursement_request(
                item.category
            )
            if state in needs_attention_states:
                needs_attention.append(item)
            elif state in transaction_history_states:
                transaction_history.append(item)
            elif (
                state == ReimbursementRequestState.DENIED
                and item.reimbursement_type != ReimbursementRequestType.DEBIT_CARD
            ):
                transaction_history.append(item)

        most_recent: list[ReimbursementRequest] = sorted(
            needs_attention + transaction_history,
            key=lambda r: r.created_at,
            reverse=True,
        )
        most_recent = list(
            filter(
                lambda r: r.created_at.replace(tzinfo=pytz.UTC)
                >= datetime.now(timezone.utc) - timedelta(days=60),
                most_recent,
            )
        )

        return {
            "needs_attention": needs_attention,
            "transaction_history": transaction_history,
            "most_recent": most_recent[:3],
        }

    @staticmethod
    def format_category_from_reimbursement_request(
        category: ReimbursementRequestCategory,
    ) -> ReimbursementRequestCategory:
        category.reimbursement_request_category_id = category.id
        if not category.short_label:
            category.title = category.label
            category.subtitle = None
        else:
            category.title = category.short_label
            category.subtitle = category.label

        return category

    @staticmethod
    def set_reimbursement_category_attributes_for_reimbursement_requests(
        reimbursement_wallet: ReimbursementWallet,
    ) -> None:
        type_details = get_member_type_details_from_wallet(reimbursement_wallet)
        is_gold = type_details.member_type == MemberType.MAVEN_GOLD

        allowed_categories = (
            reimbursement_wallet.get_or_create_wallet_allowed_categories
        )
        for association in allowed_categories:
            category = association.reimbursement_request_category
            category.benefit_type = association.benefit_type
            category.num_cycles = association.num_cycles
            category.is_fertility_category = category.has_fertility_expense_type()
            category.direct_payment_eligible = (
                category.has_fertility_expense_type() and is_gold
            )


class ReimbursementRequestSourceRequestsResource(PermissionedUserResource):
    def post(self, reimbursement_request_id):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        """Associates User Asset with ReimbursementRequest."""
        # launch darkly flag
        experiment_enabled = marshmallow_experiment_enabled(
            "experiment-marshmallow-reimbursement-request-source-requests-resource",
            self.user.esp_id if self.user else None,
            self.user.email if self.user else None,
            default=False,
        )
        user_asset_id = request.get_json().get("user_asset_id")

        reimbursement_request = ReimbursementRequest.query.filter_by(
            id=reimbursement_request_id
        ).one_or_none()

        if not reimbursement_request:
            message = f"Could not find ReimbursementRequest by reimbursement request id {reimbursement_request_id}."
            log.warning(message)
            abort(404, message=message)

        user_asset = UserAsset.query.filter_by(id=user_asset_id).one_or_none()
        if not user_asset:
            message = f"Could not find user asset by id {user_asset_id}."
            log.warning(message)
            abort(404, message=message)

        wallet = ReimbursementWallet.query.filter_by(
            id=reimbursement_request.reimbursement_wallet_id, user_id=user_asset.user_id
        ).one_or_none()

        if not wallet:
            message = f"Cannot find maven wallet by user_id {user_asset.user_id}."
            log.warning(message)
            abort(404, message=message)

        reimbursement_request_source = ReimbursementRequestSource(
            user_asset=user_asset,
            wallet=wallet,
            upload_source=ReimbursementRequestSourceUploadSource.POST_SUBMISSION,
        )

        reimbursement_request_source_request = ReimbursementRequestSourceRequests(
            reimbursement_request_id=reimbursement_request_id,
            source=reimbursement_request_source,
        )

        db.session.add(reimbursement_request_source_request)
        db.session.commit()
        db.session.refresh(reimbursement_request)

        success = False
        if (
            reimbursement_request.reimbursement_type
            == ReimbursementRequestType.DEBIT_CARD
        ):
            success = upload_card_transaction_attachments_to_alegeus(
                reimbursement_request, source_ids=[reimbursement_request_source.id]
            )
        else:
            claims = reimbursement_request.claims
            if len(claims) > 0:
                claim = claims[0]
                success, _ = upload_claim_attachments_to_alegeus(
                    wallet,
                    reimbursement_request,
                    claim,
                    [],
                    source_ids=[reimbursement_request_source.id],
                )
            else:
                log.info(
                    "No claims associated with reimbursement request. Skipping claim attachments upload.",
                    reimbursement_request_id=reimbursement_request_id,
                )
                # skip upload step
                success = True
        if not success:
            log.error(
                f"Error uploading attachments to Alegeus for reimbursement request {reimbursement_request_id}"
            )
            reimbursement_request_source = ReimbursementRequestSource.query.filter_by(
                user_asset=user_asset, wallet=wallet
            ).first()
            ReimbursementRequestSourceRequests.query.filter_by(
                reimbursement_request_id=reimbursement_request_id,
                reimbursement_request_source_id=reimbursement_request_source.id,
            ).delete()
            db.session.delete(reimbursement_request_source)
            db.session.commit()
            abort(500, message="Error uploading attachment")
        if receipt_validation_ops_view_enabled(reimbursement_request.service_provider):
            map_reimbursement_request_documents.delay(reimbursement_request.id)

        if experiment_enabled:
            schema = ReimbursementRequestSourceSchemaV3()
            return schema.dump(reimbursement_request_source), 201
        else:
            schema = ReimbursementRequestSourceSchema()
            return schema.dump(reimbursement_request_source).data, 201


def get_reimbursement_request(request_args: dict | None) -> dict:
    if not request_args:
        return {}
    result = {"reimbursement_wallet_id": str(request_args["reimbursement_wallet_id"])}
    if "category" in request_args:
        result["category"] = str(request_args["category"])
    return result


def get_summary_currency_code(
    category_associations: List[ReimbursementOrgSettingCategoryAssociation],
) -> str | None:
    unique_categories: Set[str | None] = {
        c.currency_code for c in category_associations
    }

    # Only 1 currency_code encountered - return it
    if len(unique_categories) == 0:
        return "USD"
    elif len(unique_categories) == 1:
        currency_code = unique_categories.pop()
        return "USD" if currency_code is None else currency_code
    # 2 encountered
    elif {None, "USD"} == unique_categories:
        return "USD"
    else:
        log.warning(
            "Wallet configured with multiple currencies",
            org_setting_id=str(
                category_associations[0].reimbursement_organization_settings_id
            ),
            currencies=str(unique_categories),
        )
        return None


def get_expense_types_for_wallet(
    wallet: ReimbursementWallet,
    allowed_categories: List[ReimbursementOrgSettingCategoryAssociation],
) -> List[dict]:
    """
    Get all expense types associated with the wallet users organization and format for Reimbursement Request Form
    """

    ros_id = wallet.reimbursement_organization_settings_id
    unique_expense_types = set()
    expense_type_to_currency = {}
    for cat in allowed_categories:
        for expense_type in cat.reimbursement_request_category.expense_types:
            unique_expense_types.add(expense_type)
            if cat.benefit_type == BenefitTypes.CURRENCY:
                expense_type_to_currency[expense_type] = (
                    cat.currency_code or DEFAULT_CURRENCY_CODE
                )

    ros_expense_types = ReimbursementOrgSettingsExpenseType.query.filter(
        ReimbursementOrgSettingsExpenseType.reimbursement_organization_settings_id
        == ros_id,
        ReimbursementOrgSettingsExpenseType.expense_type.in_(unique_expense_types),
    ).all()

    expense_subtypes = WalletExpenseSubtype.query.filter(
        WalletExpenseSubtype.expense_type.in_(unique_expense_types),
        WalletExpenseSubtype.visible == True,
    ).all()
    expense_subtypes_by_expense_type = {}
    for expense_subtype in expense_subtypes:
        key = expense_subtype.expense_type
        if key not in expense_subtypes_by_expense_type:
            expense_subtypes_by_expense_type[key] = set()
        expense_subtypes_by_expense_type[key].add(expense_subtype)

    expense_types = []
    for ros_expense_type in ros_expense_types:
        name = ros_expense_type.expense_type.name.capitalize().replace("_", " ")
        is_fertility_expense: bool = (
            ros_expense_type.expense_type in FERTILITY_EXPENSE_TYPES
        )

        subtypes = []
        if ros_expense_type.expense_type in expense_subtypes_by_expense_type:
            for st in expense_subtypes_by_expense_type[ros_expense_type.expense_type]:
                subtypes.append({"id": str(st.id), "label": st.description})
        subtypes.sort(key=lambda st: st["label"])
        subtypes.append({"id": "", "label": "Other"})

        formatted_expense_type = {
            "type": ros_expense_type.expense_type.value,
            "label": name,
            "currency_code": expense_type_to_currency.get(
                ros_expense_type.expense_type,
                DEFAULT_CURRENCY_CODE,  # Cycle based categories default to USD
            ),
            "form_options": [],
            "is_fertility_expense": is_fertility_expense,
            "subtypes": subtypes,
        }
        if ros_expense_type.taxation_status == TaxationStateConfig.SPLIT_DX_INFERTILITY:
            formatted_expense_type["form_options"].append(
                {"name": InfertilityDX.name, "label": InfertilityDX.label}
            )
        expense_types.append(formatted_expense_type)

    if len(expense_types) == 0:
        log.error(f"wallet {wallet.id} is missing associated expense types")
        stats.increment(
            metric_name="api.wallet.reimbursement_requests.expense_types",
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=["error:True", "method:GET"],
        )

    return expense_types
