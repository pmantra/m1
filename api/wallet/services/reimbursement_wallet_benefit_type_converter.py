from __future__ import annotations

import datetime
from typing import Optional, Tuple, Union

import pytz
import sqlalchemy

from common.global_procedures.procedure import GlobalProcedure, ProcedureService
from cost_breakdown.models.cost_breakdown import ReimbursementRequestToCostBreakdown
from direct_payment.treatment_procedure.models.treatment_procedure import (
    TreatmentProcedure,
    TreatmentProcedureStatus,
)
from direct_payment.treatment_procedure.repository.treatment_procedure import (
    TreatmentProcedureRepository,
)
from storage import connection
from storage.connector import RoutingSession
from utils.log import logger
from utils.payments import convert_dollars_to_cents
from wallet.alegeus_api import AlegeusApi, is_request_successful
from wallet.constants import NUM_CREDITS_PER_CYCLE
from wallet.models.constants import (
    BenefitTypes,
    ReimbursementRequestState,
    ReimbursementRequestType,
)
from wallet.models.reimbursement import (
    ReimbursementPlan,
    ReimbursementRequest,
    ReimbursementRequestCategory,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.models.reimbursement_wallet_credit import ReimbursementCycleCredits
from wallet.models.reimbursement_wallet_credit_transaction import (
    ReimbursementCycleMemberCreditTransaction,
)
from wallet.repository.cycle_credits import CycleCreditsRepository
from wallet.repository.reimbursement_request import ReimbursementRequestRepository
from wallet.repository.reimbursement_wallet import ReimbursementWalletRepository
from wallet.services.reimbursement_category_activation_visibility import (
    CategoryActivationService,
)
from wallet.utils.alegeus.enrollments.enroll_wallet import (
    configure_account,
    get_employee_account,
)

log = logger(__name__)


def reactivate_employee_account(
    api: AlegeusApi, wallet: ReimbursementWallet, plan: ReimbursementPlan
) -> Tuple[bool, Optional[dict]]:
    """Convenience function for calling the Alegeus API to reactivate a specific plan the member is enrolled in."""
    organization = wallet.reimbursement_organization_settings.organization
    employer_id = organization.alegeus_employer_id
    employee_id = wallet.alegeus_id

    account_details = None
    response = api.reactivate_employee_account(
        employee_id=employee_id, employer_id=employer_id, plan=plan
    )
    success = is_request_successful(response)

    if success:
        account_details = response.json()
    return success, account_details


def terminate_employee_account(
    api: AlegeusApi,
    wallet: ReimbursementWallet,
    plan: ReimbursementPlan,
    termination_date: datetime.date,
) -> Tuple[bool, Optional[dict]]:
    """Convenience function for calling the Alegeus API to terminate a specific plan the member is enrolled in."""
    organization = wallet.reimbursement_organization_settings.organization
    employer_id = organization.alegeus_employer_id
    employee_id = wallet.alegeus_id

    account_details = None
    response = api.terminate_employee_account(
        employee_id=employee_id,
        employer_id=employer_id,
        plan=plan,
        termination_date=termination_date,
    )
    success = is_request_successful(response)

    if success:
        account_details = response.json()
    return success, account_details


def add_prefunded_deposit(
    api: AlegeusApi,
    wallet: ReimbursementWallet,
    plan: ReimbursementPlan,
    deposit_amount: int,
) -> Tuple[bool, Optional[dict]]:
    """Convenience function for calling the Alegeus API to add a deposit to the member's account (can be negative)"""
    deposit_details = None
    response = api.post_add_prefunded_deposit(
        wallet=wallet, plan=plan, deposit_amount=deposit_amount
    )
    success = is_request_successful(response)

    if success:
        deposit_details = response.json()

    return success, deposit_details


def get_current_est_date() -> datetime.date:
    eastern_tz = pytz.timezone("America/New_York")
    utc_now = datetime.datetime.now(pytz.UTC)
    eastern_now = utc_now.astimezone(eastern_tz)
    return eastern_now.date()


class ReimbursementWalletBenefitTypeConverter:
    def __init__(
        self,
        session: Union[
            sqlalchemy.orm.scoping.ScopedSession, RoutingSession, None
        ] = None,
        reimbursements_repo: ReimbursementRequestRepository | None = None,
        cycle_credits_repo: CycleCreditsRepository | None = None,
        wallet_repo: ReimbursementWallet | None = None,
        tp_repo: TreatmentProcedureRepository | None = None,
        procedure_service: ProcedureService | None = None,
        alegeus_api: AlegeusApi | None = None,
        bypass_alegeus: bool = False,
    ):
        self.session = session or connection.db.session
        self.reimbursements_repo = (
            reimbursements_repo or ReimbursementRequestRepository(session=self.session)
        )
        self.cycle_credits_repo = cycle_credits_repo or CycleCreditsRepository(
            session=self.session
        )
        self.wallet_repo = wallet_repo or ReimbursementWalletRepository(
            session=self.session
        )
        self.tp_repo = tp_repo or TreatmentProcedureRepository(session=self.session)
        self.procedure_service = procedure_service or ProcedureService(internal=True)
        self.alegeus_api = alegeus_api or AlegeusApi()
        self.bypass_alegeus = bypass_alegeus

    @staticmethod
    def convert_reimbursement_to_currency(
        reimbursement_request: ReimbursementRequest,
        new_category: ReimbursementOrgSettingCategoryAssociation,
    ) -> ReimbursementRequest:
        """
        Convert a cycle based reimbursement to currency
        1. Assign the new currency category to it
        """
        log.info(
            "Converting reimbursement from cycle-based to currency-based",
            reimbursement_request_id=str(reimbursement_request.id),
            old_reimbursement_request_category_id=str(
                reimbursement_request.reimbursement_request_category_id
            ),
            new_category_association_id=str(new_category.id),
            new_reimbursement_request_category_id=str(
                new_category.reimbursement_request_category_id
            ),
        )

        if new_category.benefit_type != BenefitTypes.CURRENCY:
            raise BenefitTypeConversionValidationError(
                f"new_category is not of 'CURRENCY' type: category association id: {str(new_category.id)}"
            )

        # Assign new currency category to reimbursement request
        reimbursement_request.reimbursement_request_category_id = (
            new_category.reimbursement_request_category_id
        )

        return reimbursement_request

    def convert_reimbursement_to_cycle(
        self,
        reimbursement_request: ReimbursementRequest,
        new_category: ReimbursementOrgSettingCategoryAssociation,
        cycle_credit: ReimbursementCycleCredits,
    ) -> ReimbursementRequest:
        """
        Convert a currency based reimbursement to cycle
        1. Assign the new currency category to it
        2. Create a cycle credit transaction and attach it to the reimbursement request and cycle credit
        """
        log.info(
            "Converting reimbursement from currency-based to cycle-based",
            reimbursement_request_id=str(reimbursement_request.id),
            old_reimbursement_request_category_id=str(
                reimbursement_request.reimbursement_request_category_id
            ),
            new_category_association_id=str(new_category.id),
            new_reimbursement_request_category_id=str(
                new_category.reimbursement_request_category_id
            ),
        )

        if new_category.benefit_type != BenefitTypes.CYCLE:
            raise BenefitTypeConversionValidationError(
                f"new_category is not of 'CYCLE' type: category association id: {str(new_category.id)}"
            )

        # Assign new currency category to reimbursement request
        reimbursement_request.reimbursement_request_category_id = (
            new_category.reimbursement_request_category_id
        )

        # Check if there is already a credit transaction for this reimbursement/cycle credit
        transactions: list[
            ReimbursementCycleMemberCreditTransaction
        ] = self.cycle_credits_repo.get_credit_transactions_for_reimbursement(
            reimbursement_request_id=reimbursement_request.id,
            cycle_credit_id=cycle_credit.id,
        )
        # If no - get the expense_subtype and query procedures service for it
        if not transactions:
            if reimbursement_request.cost_credit is None:
                treatment_procedure: TreatmentProcedure | None = None
                # Check if the reimbursement is a DIRECT_BILLING reimbursement
                if (
                    reimbursement_request.reimbursement_type
                    == ReimbursementRequestType.DIRECT_BILLING
                ):
                    cb_mapping: ReimbursementRequestToCostBreakdown | None = (
                        self.reimbursements_repo.get_employer_cb_mapping(
                            reimbursement_request_id=reimbursement_request.id
                        )
                    )
                    # Assume this is because it is a EMPLOYEE_DEDUCTIBLE reimbursement, so we can skip
                    if (
                        cb_mapping is None
                        or cb_mapping.treatment_procedure_uuid is None
                    ):
                        log.error(
                            "Unable to find ReimbursementRequestToCostBreakdown - skipping",
                            reimbursement_request_id=str(reimbursement_request.id),
                        )
                        return reimbursement_request

                    treatment_procedures: list[
                        TreatmentProcedure
                    ] = self.tp_repo.get_treatments_by_uuids(
                        treatment_procedure_uuids=[cb_mapping.treatment_procedure_uuid]
                    )

                    if not treatment_procedures:
                        log.error(
                            "Unable to find TreatmentProcedure",
                            reimbursement_request_id=str(reimbursement_request.id),
                            treatment_procedure_uuid=str(
                                cb_mapping.treatment_procedure_uuid
                            ),
                        )
                        raise BenefitTypeConversionError(
                            "Not able to find TreatmentProcedure for reimbursement request"
                        )

                    if len(treatment_procedures) > 1:
                        log.error(
                            "Multiple TreatmentProcedures found",
                            reimbursement_request_id=str(reimbursement_request.id),
                            treatment_procedure_uuids=str(
                                [
                                    tp.treatment_procedure_uuid
                                    for tp in treatment_procedures
                                ]
                            ),
                        )
                        raise BenefitTypeConversionError(
                            "Multiple TreatmentProcedures found"
                        )

                    treatment_procedure = treatment_procedures[0]

                    log.info(
                        "Successfully found global procedure id for reimbursement request",
                        reimbursement_request_id=str(reimbursement_request.id),
                        global_procedure_id=str(
                            treatment_procedure.global_procedure_id
                        ),
                        treatment_procedure_id=str(treatment_procedure.id),
                    )

                    # Set this variable so it can be used to grab the cost credit later
                    gp_id = treatment_procedure.global_procedure_id
                else:  # This block is for member-submitted claims
                    # This should be set for all APPROVED and REIMBURSED reimbursements
                    if (
                        expense_subtype := reimbursement_request.wallet_expense_subtype
                    ) is None:
                        log.warn(
                            "Reimbursement does not have wallet_expense_subtype set - skipping",
                            new_category_association_id=str(new_category.id),
                            new_reimbursement_request_category_id=str(
                                new_category.reimbursement_request_category_id
                            ),
                            reimbursement_request_state=str(
                                reimbursement_request.state
                            ),
                        )
                        return reimbursement_request
                    # If the global_procedure_id is not set, assume it is non-medical (there are some exceptions)
                    elif (gp_id := expense_subtype.global_procedure_id) is None:
                        log.warn(
                            "wallet_expense_subtype does not have global_procedure_id set - skipping",
                            new_category_association_id=str(new_category.id),
                            new_reimbursement_request_category_id=str(
                                new_category.reimbursement_request_category_id
                            ),
                            reimbursement_request_state=str(
                                reimbursement_request.state
                            ),
                        )
                        return reimbursement_request

                procedure = self.procedure_service.get_procedure_by_id(
                    procedure_id=gp_id
                )

                if procedure is None:
                    raise BenefitTypeConversionError("Procedure is not found")

                if treatment_procedure is None:  # For MANUAL claims
                    reimbursement_request.cost_credit = procedure["credits"]
                    self.session.add(reimbursement_request)

                cost_credit = procedure["credits"]
            else:
                cost_credit = reimbursement_request.cost_credit

            # For non-terminal maunal claims - we don't want to reduce the credit yet
            if (
                reimbursement_request.reimbursement_type
                == ReimbursementRequestType.MANUAL
                and reimbursement_request.state
                not in {
                    ReimbursementRequestState.REIMBURSED,
                    ReimbursementRequestState.APPROVED,
                }
            ):
                return reimbursement_request

            # Create a reimbursement cycle credit
            new_transaction = ReimbursementCycleMemberCreditTransaction(
                reimbursement_request_id=reimbursement_request.id,
                reimbursement_cycle_credits_id=cycle_credit.id,
                amount=cost_credit * -1,  # debit the amount as this is spent
                notes="Created from currency to cycle conversion",
            )
            # Reduce the balance of the cycle_credit
            cycle_credit.amount = max(cycle_credit.amount - cost_credit, 0)
            self.session.add(new_transaction)
        else:
            log.info(
                "ReimbursementCycleMemberCreditTransaction already exists for reimbursement - skipping",
                reimbursement_request_id=str(reimbursement_request.id),
                cycle_credit_id=str(cycle_credit.id),
                credit_transactions=str(transactions),
            )

        return reimbursement_request

    def convert_cycle_to_currency(
        self,
        wallet: ReimbursementWallet,
        cycle_category: ReimbursementOrgSettingCategoryAssociation,
        currency_category: ReimbursementOrgSettingCategoryAssociation,
    ) -> int:
        """
        Update the reimbursements attached to cycle_category to currency_category
        Returns: Total USD cents of REIMBURSED spend
        """
        if cycle_category.benefit_type != BenefitTypes.CYCLE:
            raise BenefitTypeConversionValidationError(
                "cycle_category is not of 'CYCLE' type"
            )

        if currency_category.benefit_type != BenefitTypes.CURRENCY:
            raise BenefitTypeConversionValidationError(
                "currency_category is not of 'CURRENCY' type"
            )

        log.info(
            "Converting cycle-based reimbursements to currency-based",
            wallet_id=str(wallet.id),
            cycle_category_id=str(cycle_category.reimbursement_request_category_id),
            currency_category_id=str(
                currency_category.reimbursement_request_category_id
            ),
            cycle_category_association_id=str(cycle_category.id),
            currency_category_association_id=str(currency_category.id),
        )

        reimbursements: list[
            ReimbursementRequest
        ] = self.reimbursements_repo.get_all_reimbursement_requests_for_wallet_and_category(
            wallet_id=wallet.id,
            category_id=cycle_category.reimbursement_request_category_id,
        )

        usd_spend_total: int = 0

        if not reimbursements:
            log.info(
                "No reimbursements found for wallet/category",
                wallet_id=str(wallet.id),
                cycle_category_id=str(cycle_category.reimbursement_request_category_id),
                currency_category_id=str(
                    currency_category.reimbursement_request_category_id
                ),
                cycle_category_association_id=str(cycle_category.id),
                currency_category_association_id=str(currency_category.id),
            )
        else:
            log.info(
                "Reimbursements found for wallet/category",
                num_of_reimbursements=len(reimbursements),
                wallet_id=str(wallet.id),
                cycle_category_id=str(cycle_category.reimbursement_request_category_id),
                currency_category_id=str(
                    currency_category.reimbursement_request_category_id
                ),
                cycle_category_association_id=str(cycle_category.id),
                currency_category_association_id=str(currency_category.id),
            )

            for reimbursement in reimbursements:
                ReimbursementWalletBenefitTypeConverter.convert_reimbursement_to_currency(
                    reimbursement_request=reimbursement, new_category=currency_category
                )

                if reimbursement.state in {
                    ReimbursementRequestState.REIMBURSED,
                    ReimbursementRequestState.APPROVED,
                }:
                    usd_spend_total += reimbursement.amount
                    log.info(
                        "Including reimbursement in total spend calculation",
                        wallet_id=str(wallet.id),
                        reimbursement_request_id=str(reimbursement.id),
                        amount=str(reimbursement.amount),
                        currency_code=str(reimbursement.benefit_currency_code),
                        reimbursement_state=str(reimbursement.state.value),
                    )
                else:
                    log.info(
                        "Excluding reimbursement in total spend calculation",
                        wallet_id=str(wallet.id),
                        reimbursement_request_id=str(reimbursement.id),
                        amount=str(reimbursement.amount),
                        currency_code=str(reimbursement.benefit_currency_code),
                        reimbursement_state=str(reimbursement.state.value),
                    )

        return usd_spend_total

    def convert_currency_to_cycle(
        self,
        wallet: ReimbursementWallet,
        currency_category: ReimbursementOrgSettingCategoryAssociation,
        cycle_category: ReimbursementOrgSettingCategoryAssociation,
    ) -> int:
        """
        Update the reimbursements attached to currency_category to cycle_category
        Returns:
        """
        if cycle_category.benefit_type != BenefitTypes.CYCLE:
            raise ValueError("cycle_category is not of 'CYCLE' type")

        if currency_category.benefit_type != BenefitTypes.CURRENCY:
            raise ValueError("currency_category is not of 'CURRENCY' type")

        log.info(
            "Converting currency-based reimbursements to cycle-based",
            wallet_id=str(wallet.id),
            cycle_category_id=str(cycle_category.reimbursement_request_category_id),
            currency_category_id=str(
                currency_category.reimbursement_request_category_id
            ),
            cycle_category_association_id=str(cycle_category.id),
            currency_category_association_id=str(currency_category.id),
        )

        # if ReimbursementCycleCredits doesn't exist add a new one
        cycle_credit: ReimbursementCycleCredits | None = (
            self.cycle_credits_repo.get_cycle_credit(
                reimbursement_wallet_id=wallet.id,
                category_association_id=cycle_category.id,
            )
        )

        if cycle_credit is None:
            num_credits: int = NUM_CREDITS_PER_CYCLE * cycle_category.num_cycles

            cycle_credit = ReimbursementCycleCredits(
                reimbursement_wallet_id=wallet.id,
                reimbursement_organization_settings_allowed_category_id=cycle_category.id,
                amount=num_credits,
            )
            transaction: ReimbursementCycleMemberCreditTransaction = ReimbursementCycleMemberCreditTransaction(
                reimbursement_cycle_credits_id=cycle_credit.id,
                reimbursement_request_id=None,
                reimbursement_wallet_global_procedures_id=None,
                amount=num_credits,
                notes=f"Added {num_credits} credits when switched from currency to cycle based",
            )
            self.session.add_all([cycle_credit, transaction])
            log.info(
                "Added CycleCredit and ReimbursementCycleMemberCreditTransaction for this wallet/category",
                wallet_id=str(wallet.id),
                cycle_category_association_id=str(cycle_category.id),
                cycle_credit_id=str(cycle_credit.id),
                cycle_credit_transction_id=str(transaction.id),
            )
        else:
            log.info(
                "CycleCredit entry already exists for this wallet/category",
                wallet_id=str(wallet.id),
                cycle_category_association_id=str(cycle_category.id),
                cycle_credit_id=str(cycle_credit.id),
            )

        reimbursements: list[
            ReimbursementRequest
        ] = self.reimbursements_repo.get_all_reimbursement_requests_for_wallet_and_category(
            wallet_id=wallet.id,
            category_id=currency_category.reimbursement_request_category_id,
        )
        usd_spend_total: int = 0

        if not reimbursements:
            log.info(
                "No reimbursements found for wallet/category",
                wallet_id=str(wallet.id),
                cycle_category_id=str(cycle_category.reimbursement_request_category_id),
                currency_category_id=str(
                    currency_category.reimbursement_request_category_id
                ),
                cycle_category_association_id=str(cycle_category.id),
                currency_category_association_id=str(currency_category.id),
            )
        else:
            log.info(
                "Reimbursements found for wallet/category",
                num_of_reimbursements=len(reimbursements),
                wallet_id=str(wallet.id),
                cycle_category_id=str(cycle_category.reimbursement_request_category_id),
                currency_category_id=str(
                    currency_category.reimbursement_request_category_id
                ),
                cycle_category_association_id=str(cycle_category.id),
                currency_category_association_id=str(currency_category.id),
            )

            for reimbursement in reimbursements:
                self.convert_reimbursement_to_cycle(
                    reimbursement_request=reimbursement,
                    new_category=cycle_category,
                    cycle_credit=cycle_credit,
                )

                if reimbursement.state in {
                    ReimbursementRequestState.REIMBURSED,
                    ReimbursementRequestState.APPROVED,
                }:
                    usd_spend_total += reimbursement.amount
                    log.info(
                        "Including reimbursement in total spend calculation",
                        wallet_id=str(wallet.id),
                        reimbursement_request_id=str(reimbursement.id),
                        amount=str(reimbursement.amount),
                        currency_code=str(reimbursement.benefit_currency_code),
                        reimbursement_state=str(reimbursement.state.value),
                    )
                else:
                    log.info(
                        "Excluding reimbursement in total spend calculation",
                        wallet_id=str(wallet.id),
                        reimbursement_request_id=str(reimbursement.id),
                        amount=str(reimbursement.amount),
                        currency_code=str(reimbursement.benefit_currency_code),
                        reimbursement_state=str(reimbursement.state.value),
                    )

        return usd_spend_total

    def reimbursement_account_exists(
        self, wallet: ReimbursementWallet, category: ReimbursementRequestCategory
    ) -> bool:
        return bool(
            self.wallet_repo.get_reimbursement_account(wallet=wallet, category=category)
        )

    def sync_alegeus_accounts(
        self,
        wallet: ReimbursementWallet,
        source_category: ReimbursementOrgSettingCategoryAssociation,
        target_category: ReimbursementOrgSettingCategoryAssociation,
        remaining_balance: int,
    ) -> bool:
        """Used when migrating spend from source_category to target_category - This method attempts the following
        1. Make sure the alegeus account associated with source_category is terminated
        2. Attempts to re-activate the alegeus account associated with target_category if it exists
        3. If it doesn't exist, create the account
        4. Adjust the Alegeus remaining balance in the account based on prior spend
        """
        log.info(
            "Syncing Alegeus accounts called - starting sync",
            wallet_id=str(wallet.id),
            source_category_id=str(source_category.reimbursement_request_category_id),
            target_category_id=str(target_category.reimbursement_request_category_id),
            source_category_association_id=str(source_category.id),
            target_category_association_id=str(target_category.id),
        )

        alegeus_account_exists: bool = False

        # Terminate alegeus account for source_category
        successful_termination, data = terminate_employee_account(
            api=self.alegeus_api,
            wallet=wallet,
            plan=source_category.reimbursement_request_category.reimbursement_plan,
            termination_date=get_current_est_date(),
        )
        if successful_termination is False:
            log.error(
                "Failed to terminate Alegeus account for source category",
                wallet_id=str(wallet.id),
                source_category_id=str(
                    source_category.reimbursement_request_category_id
                ),
                source_category_association_id=str(source_category.id),
            )
            raise BenefitTypeConversionValidationError(
                "Failed to terminate existing Alegeus account"
            )

        log.info(
            "Successfully terminated Alegeus account for source account",
            wallet_id=str(wallet.id),
            source_category_id=str(source_category.reimbursement_request_category_id),
            source_category_association_id=str(source_category.id),
        )

        # If a ReimbursementAccount exists on our side, it means an Alegeus account was created at some point
        # If this is the case, we will attempt to re-use the Alegeus account
        if (
            reimbursement_account := self.wallet_repo.get_reimbursement_account(
                wallet=wallet, category=target_category.reimbursement_request_category
            )
        ) is not None:
            log.info(
                "Detected that reimbursement account already exists for target category - attempting to reactivate",
                wallet_id=str(wallet.id),
                target_category_id=str(
                    target_category.reimbursement_request_category_id
                ),
                target_category_association_id=str(target_category.id),
                reimbursement_plan_id=str(reimbursement_account.reimbursement_plan_id),
            )

            alegeus_account_exists, account_data = get_employee_account(
                api=self.alegeus_api, wallet=wallet, account=reimbursement_account
            )

            if (
                alegeus_account_exists is False
                or account_data is None
                or "RemainingBalance" not in account_data
            ):
                log.error(
                    "Failed to fetch existing Alegeus account",
                    wallet_id=str(wallet.id),
                    target_category_id=str(
                        target_category.reimbursement_request_category_id
                    ),
                    target_category_association_id=str(target_category.id),
                    reimbursement_plan_id=str(
                        reimbursement_account.reimbursement_plan_id
                    ),
                )
                raise BenefitTypeConversionValidationError(
                    "Failed to fetch existing Alegeus account details"
                )

            log.info(
                "Alegeus account already exists - attempting to reactivate",
                wallet_id=str(wallet.id),
                target_category_id=str(
                    target_category.reimbursement_request_category_id
                ),
                target_category_association_id=str(target_category.id),
                reimbursement_plan_id=str(reimbursement_account.reimbursement_plan_id),
            )
            successful_reactivation, _ = reactivate_employee_account(
                api=self.alegeus_api,
                wallet=wallet,
                plan=target_category.reimbursement_request_category.reimbursement_plan,
            )

            if successful_reactivation is False:
                log.error(
                    "Failed to reactivate Alegeus account for target category",
                    wallet_id=str(wallet.id),
                    target_category_id=str(
                        target_category.reimbursement_request_category_id
                    ),
                    target_category_association_id=str(target_category.id),
                    reimbursement_plan_id=str(
                        reimbursement_account.reimbursement_plan_id
                    ),
                )
                raise BenefitTypeConversionValidationError(
                    "Failed to reactivate existing Alegeus account"
                )

            log.info(
                "Successfully reactivated Alegeus account for target category",
                wallet_id=str(wallet.id),
                target_category_id=str(
                    target_category.reimbursement_request_category_id
                ),
                target_category_association_id=str(target_category.id),
                reimbursement_plan_id=str(reimbursement_account.reimbursement_plan_id),
            )

            alegeus_remaining_balance = convert_dollars_to_cents(
                account_data["RemainingBalance"]
            )
            # Calculate the amount we want to post to alegeus to adjust the remaining balance with
            adjustment_amount = remaining_balance - alegeus_remaining_balance

            if abs(adjustment_amount) > 0:
                log.info(
                    "Alegeus balance is incorrect - attempting to adjust with a deposit",
                    wallet_id=str(wallet.id),
                    target_category_id=str(
                        target_category.reimbursement_request_category_id
                    ),
                    target_category_association_id=str(target_category.id),
                    reimbursement_plan_id=str(
                        reimbursement_account.reimbursement_plan_id
                    ),
                    deposit_amount=str(adjustment_amount),
                )

                successful_deposit, data = add_prefunded_deposit(
                    api=self.alegeus_api,
                    wallet=wallet,
                    plan=target_category.reimbursement_request_category.reimbursement_plan,
                    deposit_amount=adjustment_amount,
                )

                if successful_deposit is False:
                    log.error(
                        "Failed to adjust Alegeus account balance",
                        wallet_id=str(wallet.id),
                        target_category_id=str(
                            target_category.reimbursement_request_category_id
                        ),
                        target_category_association_id=str(target_category.id),
                        reimbursement_plan_id=str(
                            reimbursement_account.reimbursement_plan_id
                        ),
                    )
                    raise BenefitTypeConversionValidationError(
                        "Failed to adjust Alegeus account balance"
                    )
            else:
                log.info(
                    "Alegeus balance is correct - skipping adjustment",
                    wallet_id=str(wallet.id),
                    target_category_id=str(
                        target_category.reimbursement_request_category_id
                    ),
                    target_category_association_id=str(target_category.id),
                    reimbursement_plan_id=str(
                        reimbursement_account.reimbursement_plan_id
                    ),
                )

        # Alegeus account doesn't exist - let's create it
        if alegeus_account_exists is False:
            log.info(
                "Alegeus account doesn't exist - creating new account",
                wallet_id=str(wallet.id),
                target_category_id=str(
                    target_category.reimbursement_request_category_id
                ),
                target_category_association_id=str(target_category.id),
                amount=str(remaining_balance),
            )
            # Configure account in alegeus with (ltm - prior_spend)
            plan = target_category.reimbursement_request_category.reimbursement_plan
            start_date = CategoryActivationService().get_start_date_for_user_allowed_category(
                allowed_category=target_category, plan=plan, user_id=wallet.user_id  # type: ignore[arg-type]
            )
            successful_configuration, messages = configure_account(
                api=self.alegeus_api,
                wallet=wallet,
                plan=plan,
                prefunded_amount=remaining_balance,
                coverage_tier=None,
                start_date=start_date,
                messages=[],
            )
            if successful_configuration is False:
                log.error(
                    "Failed to create new Alegeus account",
                    wallet_id=str(wallet.id),
                    target_category_id=str(
                        target_category.reimbursement_request_category_id
                    ),
                    target_category_association_id=str(target_category.id),
                )
                raise BenefitTypeConversionValidationError(
                    "Failed to configure new Alegeus account"
                )

            log.info(
                "Successfully created new alegeus account",
                wallet_id=str(wallet.id),
                target_category_id=str(
                    target_category.reimbursement_request_category_id
                ),
                target_category_association_id=str(target_category.id),
            )

        return True

    def convert_currency_to_cycle_and_update_alegeus(
        self,
        wallet: ReimbursementWallet,
        currency_category: ReimbursementOrgSettingCategoryAssociation,
        cycle_category: ReimbursementOrgSettingCategoryAssociation,
    ) -> bool:
        log.info(
            "convert_currency_to_cycle_and_update_alegeus called",
            wallet_id=str(wallet.id),
            cycle_category_id=str(cycle_category.reimbursement_request_category_id),
            currency_category_id=str(
                currency_category.reimbursement_request_category_id
            ),
            cycle_category_association_id=str(cycle_category.id),
            currency_category_association_id=str(currency_category.id),
        )
        prior_spend_usd = self.convert_currency_to_cycle(
            wallet=wallet,
            currency_category=currency_category,
            cycle_category=cycle_category,
        )
        remaining_balance: int = cycle_category.usd_funding_amount - prior_spend_usd

        all_tps: list[
            TreatmentProcedure
        ] = self.tp_repo.get_all_treatments_from_wallet_id(wallet_id=wallet.id)

        scheduled_tps: list[TreatmentProcedure] = [
            tp for tp in all_tps if tp.status == TreatmentProcedureStatus.SCHEDULED
        ]

        # Set the new category on non-terminal TPs
        self.batch_update_treatment_procedure_category(
            wallet=wallet,
            treatment_procedures=scheduled_tps,
            new_category=cycle_category,
        )

        # Set the cost_credit on all TPs
        self.batch_update_treatment_procedure_cost_credit(
            wallet=wallet,
            treatment_procedures=all_tps,
            new_category=cycle_category,
        )

        self.session.add_all(all_tps)

        if self.bypass_alegeus:
            log.info(
                "convert_currency_to_cycle_and_update_alegeus called with bypass_alegeus=True - returning"
            )
            return True

        return self.sync_alegeus_accounts(
            wallet=wallet,
            source_category=currency_category,
            target_category=cycle_category,
            remaining_balance=remaining_balance,
        )

    def convert_cycle_to_currency_and_update_alegeus(
        self,
        wallet: ReimbursementWallet,
        cycle_category: ReimbursementOrgSettingCategoryAssociation,
        currency_category: ReimbursementOrgSettingCategoryAssociation,
    ) -> bool:
        log.info(
            "convert_cycle_to_currency_and_update_alegeus called",
            wallet_id=str(wallet.id),
            cycle_category_id=str(cycle_category.reimbursement_request_category_id),
            currency_category_id=str(
                currency_category.reimbursement_request_category_id
            ),
            cycle_category_association_id=str(cycle_category.id),
            currency_category_association_id=str(currency_category.id),
        )
        prior_spend_usd = self.convert_cycle_to_currency(
            wallet=wallet,
            cycle_category=cycle_category,
            currency_category=currency_category,
        )
        remaining_balance: int = currency_category.usd_funding_amount - prior_spend_usd

        all_tps: list[
            TreatmentProcedure
        ] = self.tp_repo.get_all_treatments_from_wallet_id(wallet_id=wallet.id)

        scheduled_tps: list[TreatmentProcedure] = [
            tp for tp in all_tps if tp.status == TreatmentProcedureStatus.SCHEDULED
        ]

        self.batch_update_treatment_procedure_category(
            wallet=wallet,
            treatment_procedures=scheduled_tps,
            new_category=currency_category,
        )

        self.batch_update_nullify_treatment_procedure_cost_credit(
            wallet=wallet, treatment_procedures=all_tps
        )

        self.session.add_all(all_tps)

        if self.bypass_alegeus:
            log.info(
                "convert_cycle_to_currency_and_update_alegeus called with bypass_alegeus=True - returning"
            )
            return True

        return self.sync_alegeus_accounts(
            wallet=wallet,
            source_category=cycle_category,
            target_category=currency_category,
            remaining_balance=remaining_balance,
        )

    @staticmethod
    def batch_update_treatment_procedure_category(
        wallet: ReimbursementWallet,
        treatment_procedures: list[TreatmentProcedure],
        new_category: ReimbursementOrgSettingCategoryAssociation,
    ) -> list[TreatmentProcedure]:

        for procedure in treatment_procedures:
            old_category_id: int = procedure.reimbursement_request_category_id
            procedure.reimbursement_request_category_id = (
                new_category.reimbursement_request_category_id
            )
            log.info(
                "Updating treatment procedure category",
                old_category_id=str(old_category_id),
                new_category_id=str(new_category.reimbursement_request_category_id),
                wallet_id=str(wallet.id),
                tp_status=str(procedure.status),
                tp_id=str(procedure.id),
            )

        return treatment_procedures

    def batch_update_treatment_procedure_cost_credit(
        self,
        wallet: ReimbursementWallet,
        treatment_procedures: list[TreatmentProcedure],
        new_category: ReimbursementOrgSettingCategoryAssociation,
    ) -> list[TreatmentProcedure]:

        for procedure in treatment_procedures:
            old_category_id: int = procedure.reimbursement_request_category_id
            global_procedure: GlobalProcedure | None = (
                self.procedure_service.get_procedure_by_id(
                    procedure_id=procedure.global_procedure_id
                )
            )
            if global_procedure is None:
                raise BenefitTypeConversionError("Procedure is not found")

            procedure.cost_credit = global_procedure["credits"]

            log.info(
                "Updating treatment procedure cost_credit",
                old_category_id=str(old_category_id),
                new_category_id=str(new_category.reimbursement_request_category_id),
                wallet_id=str(wallet.id),
                tp_status=str(procedure.status),
                tp_id=str(procedure.id),
                global_procedure_id=str(procedure.global_procedure_id),
                global_procedure_credits=str(procedure.cost_credit),
            )

        return treatment_procedures

    @staticmethod
    def batch_update_nullify_treatment_procedure_cost_credit(
        wallet: ReimbursementWallet,
        treatment_procedures: list[TreatmentProcedure],
    ) -> list[TreatmentProcedure]:

        for procedure in treatment_procedures:
            procedure.cost_credit = None
            log.info(
                "Updating treatment procedure cost_credit to None",
                wallet_id=str(wallet.id),
                tp_status=str(procedure.status),
                tp_id=str(procedure.id),
                global_procedure_id=str(procedure.global_procedure_id),
            )

        return treatment_procedures


class BenefitTypeConversionError(Exception):
    pass


class BenefitTypeConversionValidationError(BenefitTypeConversionError):
    pass
