from __future__ import annotations

import datetime
from typing import Dict, List, Optional

from utils.log import logger
from wallet.constants import NUM_CREDITS_PER_CYCLE
from wallet.models.reimbursement import ReimbursementPlan, ReimbursementRequestCategory
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.services.currency import CurrencyService

log = logger(__name__)


def get_allowed_category_associations_by_wallet(
    wallet: ReimbursementWallet, category: Optional[str] = None
) -> List[ReimbursementOrgSettingCategoryAssociation]:

    allowed_categories_query = ReimbursementOrgSettingCategoryAssociation.query.join(
        ReimbursementOrgSettingCategoryAssociation.reimbursement_organization_settings,
        ReimbursementOrganizationSettings.reimbursement_wallets,
        ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category,
        ReimbursementRequestCategory.reimbursement_plan,
    ).filter(
        ReimbursementWallet.id == wallet.id,
        ReimbursementPlan.start_date <= datetime.date.today(),
        ReimbursementPlan.end_date >= datetime.date.today(),
    )

    if category:
        allowed_categories_query = allowed_categories_query.filter(
            ReimbursementRequestCategory.label == category
        )

    wallet_allowed_category_ids = [
        cat.id for cat in wallet.get_or_create_wallet_allowed_categories
    ]
    allowed_categories_query = allowed_categories_query.filter(
        ReimbursementOrgSettingCategoryAssociation.id.in_(wallet_allowed_category_ids)
    )

    return allowed_categories_query.all()


def get_reimbursement_category_breakdown(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    currency_service: CurrencyService,
    approved_amount_by_category: dict,
    category_associations: List[ReimbursementOrgSettingCategoryAssociation],
    remaining_credit_balances_map: Dict[int, int],
):
    breakdown = []

    for category_association in category_associations:
        category = category_association.reimbursement_request_category
        plan = category.reimbursement_plan
        num_remaining_credits = remaining_credit_balances_map.get(category.id, 0)

        breakdown.append(
            {
                "category": format_category(
                    category_association, currency_service, num_remaining_credits
                ),
                "plan_type": plan and plan.plan_type and plan.plan_type.value,
                "plan_start": plan and plan.start_date,
                "plan_end": plan and plan.end_date,
                "spent": approved_amount_by_category.get(category.id, 0),
                "spent_amount": currency_service.format_amount_obj(
                    amount=approved_amount_by_category.get(category.id),
                    currency_code=category_association.currency_code,
                ),
                "remaining_amount": currency_service.format_amount_obj(
                    amount=calculate_remaining_amount(
                        maximum=category_association.reimbursement_request_category_maximum,
                        spent=approved_amount_by_category.get(category.id),
                    ),
                    currency_code=category_association.currency_code,
                ),
            }
        )
    return breakdown


def format_category(  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    allowed_category: ReimbursementOrgSettingCategoryAssociation,
    currency_service: CurrencyService,
    num_credits_remaining: int = 0,
):
    request_category = allowed_category.reimbursement_request_category
    if not request_category.short_label:
        title = request_category.label
        subtitle = None
    else:
        title = request_category.short_label
        subtitle = request_category.label
    cycles = request_category.num_cycles or 0
    category_max: int = allowed_category.reimbursement_request_category_maximum or 0
    currency_code: str | None = allowed_category.currency_code

    return {
        "label": request_category.label,
        "is_unlimited": allowed_category.is_unlimited,
        "reimbursement_request_category_maximum": category_max,
        "reimbursement_request_category_maximum_amount": currency_service.format_amount_obj(
            amount=category_max, currency_code=currency_code
        ),
        "title": title,
        "subtitle": subtitle,
        "reimbursement_request_category_id": request_category.id,
        "benefit_type": allowed_category.benefit_type.value,  # type: ignore[attr-defined] # "str" has no attribute "value"
        "num_cycles": cycles,
        "credits_remaining": num_credits_remaining,
        "credit_maximum": cycles * NUM_CREDITS_PER_CYCLE,
        "is_fertility_category": request_category.is_fertility_category,
        "direct_payment_eligible": request_category.direct_payment_eligible,
    }


def calculate_remaining_amount(
    maximum: int | None = None, spent: int | None = None
) -> int:
    if maximum is None:
        maximum = 0
    if spent is None:
        spent = 0
    return maximum - spent
