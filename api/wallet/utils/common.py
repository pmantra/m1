from __future__ import annotations

from datetime import datetime
from typing import Optional

from dateutil.relativedelta import relativedelta
from sqlalchemy import and_

from authn.models.user import User
from common import stats
from eligibility import EnterpriseVerificationError, EnterpriseVerificationService
from eligibility.e9y import EligibilityVerification
from eligibility.e9y import model as e9y_model
from storage.connection import db
from utils.log import logger
from wallet.models.constants import (
    BenefitTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
    WalletUserStatus,
)
from wallet.models.reimbursement import ReimbursementRequest
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers

log = logger(__name__)


def get_wallet_id_by_channel_id(channel_id: int) -> str | None:
    wallet_id = (
        db.session.query(ReimbursementWalletUsers.reimbursement_wallet_id)
        .filter(
            ReimbursementWalletUsers.channel_id == channel_id,
        )
        .scalar()
    )

    if wallet_id is not None:
        # TODO: Wallet_id is a BigInteger, so this should be returned as an int
        return str(wallet_id)
    return None


def is_attached_to_wallet(channel_ids_to_check: list[int]) -> set[int]:
    attached_channel_ids = set()
    # Perform a single database query to check if the provided channel IDs are attached to a wallet
    if channel_ids_to_check:
        query_result = (
            db.session.query(ReimbursementWalletUsers.channel_id)
            .filter(ReimbursementWalletUsers.channel_id.in_(channel_ids_to_check))
            .distinct()
            .all()
        )

        attached_channel_ids = {row[0] for row in query_result}

    return attached_channel_ids


def get_wallet_benefit_id(user_id: int) -> str:
    """
    Returns the benefit id(s) of the wallet(s) affiliated with the user or
    an empty string if no such benefit id exists.
    """
    query = f"""
        SELECT rwb.maven_benefit_id
        FROM reimbursement_wallet_benefit rwb
        JOIN reimbursement_wallet_users rwu
        ON rwb.reimbursement_wallet_id = rwu.reimbursement_wallet_id
        WHERE rwu.user_id = :user_id AND rwu.status = '{WalletUserStatus.ACTIVE.value}'
    """
    benefit_id_tuples = db.session.execute(query, {"user_id": user_id}).fetchall()

    # Hypothetically, this should always be limited to 1 benefit id
    return ", ".join(str(benefit_id) for benefit_id, in benefit_id_tuples)


def get_pending_reimbursement_requests_costs(
    wallet: ReimbursementWallet, remaining_balance: int
) -> int:
    """
    Returns:
        int: Sum of pending reimbursement requests for manual claims
        associated with the wallet.  If cycle based credits are returned. If currency cents returned.
    """
    pending_costs = 0
    direct_payment_category = wallet.get_direct_payment_category
    if direct_payment_category:
        pending_reimbursement_requests = (
            db.session.query(ReimbursementRequest)
            .filter(
                and_(
                    ReimbursementRequest.reimbursement_wallet_id == wallet.id,
                    ReimbursementRequest.reimbursement_request_category_id
                    == direct_payment_category.id,
                    ReimbursementRequest.state == ReimbursementRequestState.PENDING,
                    ReimbursementRequest.reimbursement_type
                    == ReimbursementRequestType.MANUAL,
                )
            )
            .all()
        )
        for reimbursement_request in pending_reimbursement_requests:
            benefit_type = wallet.category_benefit_type(
                request_category_id=reimbursement_request.reimbursement_request_category_id
            )
            if reimbursement_request.amount > 0:
                if benefit_type == BenefitTypes.CYCLE:
                    # we don't want a negative balance
                    pending_costs += min(
                        reimbursement_request.cost_credit
                        if reimbursement_request.cost_credit is not None
                        else 0,
                        remaining_balance - pending_costs,
                    )
                else:
                    pending_costs += reimbursement_request.amount
    return pending_costs


def get_verification_record_data(
    user_id: int,
    organization_id: int,
    eligibility_service: EnterpriseVerificationService,
) -> e9y_model.EligibilityVerification | None:
    """
    Retrieves eligibility verification record data for the specified user and organization.
    """
    try:
        verification: e9y_model.EligibilityVerification = (
            eligibility_service.get_verification_for_user_and_org(
                user_id=user_id, organization_id=organization_id
            )
        )
    except Exception as e:
        raise EnterpriseVerificationError(
            message=f"Eligibility verification exception for"
            f" user {user_id}, org {organization_id}",
            verification_type="lookup",
        ) from e

    if not verification or not verification.record:
        log.info(
            "Eligibility verification record not found.",
            user_id=user_id,
            organization_id=organization_id,
        )
        return None

    return verification


def has_tenure_exceeded(start_date: str, days: int = 0, years: int = 0) -> bool:
    """
    Checks if the tenure exceeds a certain period from the start date.
    """
    formatted_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
    current_date = datetime.utcnow().date()

    comparison_date = formatted_start_date + relativedelta(days=days, years=years)

    log.info(
        "has_tenure_exceeded evaluated.",
        start_date=start_date,
        comparison_date=comparison_date,
        days=days,
        years=years,
    )
    return current_date >= comparison_date


def is_user_international(
    e9y_record: EligibilityVerification | None, user: User
) -> bool:
    """
    Determines if the user is international based on the eligibility record or user country.
    Priority:
    1. `work_country` from `e9y_record`.
    2. `country` from `e9y_record`.
    3. `user.country.alpha_2` if neither is available.
    """
    country = (
        (e9y_record.record.get("work_country") if e9y_record else None)
        or (e9y_record.record.get("country") if e9y_record else None)
        or (user.country.alpha_2 if user.country else None)
    )
    return bool(country and country.upper() not in {"US", "USA"})


def increment_reimbursement_request_field_update(
    field: str,
    source: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
) -> None:
    """
    Record a metric for updating a reimbursement request. Only include old and new values if they are from a limited set (enums: yes, IDs: no).
    """
    tags = [
        f"field:{field}",
        f"source:{source}",
    ]
    if old_value or new_value:
        from_value = old_value or "none"
        to_value = new_value or "none"
        tags.append(f"from:{from_value}")
        tags.append(f"to:{to_value}")
    stats.increment(
        metric_name="api.wallet.reimbursement_request.update",
        pod_name=stats.PodNames.PAYMENTS_POD,
        tags=tags,
    )


def create_refund_reimbursement_request(
    original_request: ReimbursementRequest, refund_amount: int
) -> ReimbursementRequest:
    if refund_amount < 0:
        raise Exception("Refund amount must be greater than 0")
    if original_request.amount < refund_amount:
        raise Exception("Cannot refund amount greater than original request amount")
    data = {
        c.name: getattr(original_request, c.name)
        for c in ReimbursementRequest.__table__.columns
    }
    data.pop("id", None)
    data.pop("created_at", None)
    data.pop("modified_at", None)
    data["service_start_date"] = datetime.combine(
        data["service_start_date"], datetime.min.time()
    )
    data["service_end_date"] = datetime.combine(
        data["service_end_date"], datetime.min.time()
    )
    data["amount"] = -1 * refund_amount
    data["transaction_amount"] = -1 * refund_amount
    data["usd_amount"] = -1 * refund_amount
    reversed_reimbursement_request = ReimbursementRequest(**data)
    return reversed_reimbursement_request
