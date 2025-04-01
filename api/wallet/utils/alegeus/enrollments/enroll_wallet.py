from __future__ import annotations

import datetime
from traceback import format_exc
from typing import TYPE_CHECKING, Any, List, Optional, Set, Tuple

from requests import Response
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.exc import MultipleResultsFound, NoResultFound

from authn.models.user import User
from common import stats
from eligibility import e9y
from eligibility import service as e9y_service
from eligibility.e9y import model as e9y_model
from models.profiles import Address
from storage.connection import db
from utils.log import logger
from utils.payments import convert_dollars_to_cents
from wallet import alegeus_api
from wallet.alegeus_api import AlegeusApi, is_request_successful
from wallet.models.constants import (
    AlegeusCoverageTier,
    ReimbursementAccountStatus,
    ReimbursementMethod,
    WalletState,
    WalletUserType,
)
from wallet.models.organization_employee_dependent import OrganizationEmployeeDependent
from wallet.models.reimbursement import (
    ReimbursementAccount,
    ReimbursementAccountType,
    ReimbursementRequestCategory,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
    ReimbursementOrgSettingCategoryAssociation,
)
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory

if TYPE_CHECKING:
    from wallet.models.reimbursement import ReimbursementPlan
    from wallet.models.reimbursement_wallet import ReimbursementWallet

log = logger(__name__)

metric_prefix = "api.wallet.utils.alegeus.enrollments.enroll_wallet"


def configure_wallet_in_alegeus(
    wallet: ReimbursementWallet,
) -> Tuple[bool, List[FlashMessage]]:
    """
    Configures a qualified wallet in Alegeus by sequentially creating an employee, their dependents (if they have any),
    and an employee account via the Alegeus Api.

    Dependents that are created must also be linked in a separate call to that employee account.

    The employee account in Alegeus maps to Reimbursement Plan in our schema.

    @param wallet: ReimbursementWallet that has been updated to a qualified state.
    """
    messages = []

    api = alegeus_api.AlegeusApi()

    success, messages = configure_employee(api, wallet, messages)
    if not success:
        return success, messages

    success, messages = configure_dependents(api, wallet, messages)
    if not success:
        return success, messages

    # HDHP
    for hdhp_plan in wallet.reimbursement_hdhp_plans:
        plan = hdhp_plan.reimbursement_plan
        coverage_tier = hdhp_plan.alegeus_coverage_tier
        start_date = get_start_date(allowed_category=None, user_id=wallet.user_id, plan=plan)  # type: ignore[arg-type]
        success, messages = configure_account(
            api=api,
            wallet=wallet,
            plan=plan,
            prefunded_amount=0,
            coverage_tier=coverage_tier,
            start_date=start_date,
            messages=messages,
        )
        if not success:
            return success, messages

    # For per-category activation we bypass the Alegeus
    # call that lives in get_or_create_wallet_allowed_categories and call
    # get_wallet_allowed_categories instead
    allowed_categories = wallet.get_wallet_allowed_categories

    if not allowed_categories:
        messages.append(
            FlashMessage(
                message=f"Wallet {wallet.id} has no eligible wallet categories. Please confirm and deny the "
                f"wallet.",
                category=FlashMessageCategory.ERROR,
            )
        )
        return False, messages

    for allowed_category in allowed_categories:
        request_category = allowed_category.reimbursement_request_category

        if request_category.reimbursement_plan:
            plan = request_category.reimbursement_plan
            start_date = get_start_date(allowed_category, plan, wallet.user_id)  # type: ignore[arg-type]
            success, messages = configure_account(
                api=api,
                wallet=wallet,
                plan=plan,
                prefunded_amount=allowed_category.usd_funding_amount,
                coverage_tier=None,
                messages=messages,
                start_date=start_date,
            )

            # send a metric to keep track of how many wallets and for what currencies are getting configured
            try:
                stats.increment(
                    metric_name=f"{metric_prefix}.non_hdhp_configure_account_called",
                    pod_name=stats.PodNames.PAYMENTS_POD,
                    tags=[
                        "success:true",
                        f"currency_code:{str(allowed_category.currency_code or 'USD')}",
                        f"reimbursement_org_setting_id:{str(wallet.reimbursement_organization_settings_id)}",
                        f"org_name:{str(wallet.reimbursement_organization_settings.organization.display_name)}",
                    ],
                )
            except Exception as e:
                log.exception(
                    "exception encountered while generating metric non_hdhp_configure_account_called",
                    error=str(e),
                )

            if not success:
                return success, messages

    stats.increment(
        metric_name=f"{metric_prefix}.configure_wallet_in_alegeus",
        pod_name=stats.PodNames.PAYMENTS_POD,
        tags=["success:true"],
    )
    return True, messages


def get_start_date(
    allowed_category: Optional[ReimbursementOrgSettingCategoryAssociation],
    plan: ReimbursementPlan,
    user_id: int,
) -> Optional[datetime.date]:
    # handle circular import
    from wallet.services.reimbursement_category_activation_visibility import (
        CategoryActivationService,
    )

    start_date = CategoryActivationService().get_start_date_for_user_allowed_category(
        allowed_category=allowed_category,
        plan=plan,
        user_id=user_id,
    )
    return start_date


def create_employee_demographic(
    api: AlegeusApi, wallet: ReimbursementWallet
) -> Tuple[bool, Response]:
    """
    Convenience function for calling the Alegeus API to add a member and populate demographic information.
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @return: boolean indicating whether the response was successful
    """
    # Create employee demographic information in Alegeus
    response = api.post_employee_services_and_banking(
        wallet=wallet, eligibility_date=get_eligibility_date_from_wallet(wallet)
    )
    return is_request_successful(response), response


def update_employee_demographic(
    api: AlegeusApi, wallet: ReimbursementWallet, address: Optional[Address]
) -> bool:
    """
    Convenience function for calling the Alegeus API to update a member and populate demographic information.
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @return: boolean indicating whether the response was successful
    """

    # All members with a debit card should have an address, but in case they don't allow the update to continue.

    # Get the ACH account to send it back and avoid clearing it. Failure is okay.
    banking_info = get_banking_info(api, wallet)

    # Update employee demographic information in Alegeus
    response = api.put_employee_services_and_banking(
        wallet=wallet,
        banking_info=banking_info,
        eligibility_date=get_eligibility_date_from_wallet(wallet),
        member_address=address,
    )

    banking_info = None
    del banking_info

    return is_request_successful(response)


def get_employee_demographic(api: AlegeusApi, wallet: ReimbursementWallet) -> bool:
    """
    Convenience function for calling the Alegeus API to fetch a member's demographic information.
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @return: boolean indicating whether the response was successful
    """
    # Get employee demographic to check if employee exists already in Alegeus
    response = api.get_employee_demographic(wallet)
    # TODO: currently alegeus returns a 200 and a null body for an invalid user id. Waiting on Alegeus to fix this.
    # Until Alegeus fixes this, we need to verify that the response has a body.
    return is_request_successful(response) and response.json() is not None


def create_dependent_demographic(
    api: AlegeusApi,
    wallet: ReimbursementWallet,
    alegeus_id_of_dependent: str,
    first_name: str,
    last_name: str,
) -> Tuple[bool, Response]:
    """
    Convenience function for calling the Alegeus API to add a member's dependents' demographic information
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @param dependent: the member's `OrganizationEmployeeDependent`
    @return: boolean indicating whether the response was successful
    """
    response = api.post_dependent_services(
        wallet, alegeus_id_of_dependent, first_name, last_name
    )
    return (is_request_successful(response), response)


def update_dependent_demographic(
    api: AlegeusApi,
    wallet: ReimbursementWallet,
    alegeus_dependent_id: str,
    first_name: str,
    last_name: str,
) -> bool:
    """
    Convenience function for calling the Alegeus API to update a member's dependents' demographic information
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @param dependent: the member's `OrganizationEmployeeDependent`
    @param first_name: first name of the member
    @param last_name: last_name of the member
    @return: boolean indicating whether the response was successful
    """
    response = api.put_dependent_services(
        wallet, alegeus_dependent_id, first_name, last_name
    )
    return is_request_successful(response)


def get_dependents(api: AlegeusApi, wallet: ReimbursementWallet) -> Tuple[bool, list]:
    """
    Convenience function for calling the Alegeus API to fetch a member's dependents' information
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @return: a tuple containing a booleaning indicating the response's success status,
    and a list of the dependents' demographic info as returned by the Alegeus API.
    """
    dependents = []
    response = api.get_all_dependents(wallet)
    success = is_request_successful(response)
    if success:
        dependents = response.json()
    return success, dependents


def get_dependent_demographic(
    api: AlegeusApi,
    wallet: ReimbursementWallet,
    dependent: OrganizationEmployeeDependent,
) -> bool:
    """
    Convenience function for calling the Alegeus API to fetch a demographic information for a specific dependent.
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @param dependent: the member's `OrganizationEmployeeDependent`
    @return: boolean indicating whether the response was successful
    """
    response = api.get_dependent_demographic(wallet, dependent)
    return is_request_successful(response)


def create_employee_account(
    api: AlegeusApi,
    wallet: ReimbursementWallet,
    plan: ReimbursementPlan,
    prefunded_amount: int,
    coverage_tier: AlegeusCoverageTier | None,
    start_date: Optional[datetime.date],
) -> Tuple[bool, List[FlashMessage]]:
    """
    Convenience function for calling the Alegeus API to enroll a member in a specific plan.
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @param plan: the `ReimbursementPlan` in which the member should be enrolled
    @param prefunded_amount: the amount of money the member will have access to in the plan
    @param coverage_tier: SINGLE/FAMILY flag
    @param start_date: date of coverage start, including tenure rules if applicable
    @return: boolean indicating whether the response was successful
    """
    if start_date is None:
        log.error(
            "Unable to create a reimbursement account. Cannot create an account with a null start date.",
            wallet_id=wallet.id,
            plan_id=plan.id,
        )
        return False, [
            FlashMessage(
                message="Reimbursement Account Creation Error: Cannot create an account with a null start date.",
                category=FlashMessageCategory.ERROR,
            )
        ]
    response = api.post_add_employee_account(
        wallet, plan, prefunded_amount, coverage_tier, start_date
    )
    if not is_request_successful(response):
        log.error(
            "Unable to add employee to account. Alegeus request failed.",
            wallet_id=wallet.id,
            plan_id=plan.id,
        )
        return False, [
            FlashMessage(
                message=f"Alegeus Error: {response.text}",
                category=FlashMessageCategory.ERROR,
            )
        ]

    success, error = create_reimbursement_account_from_alegeus(api, wallet, plan)
    if not success:
        log.error(
            "Unable to create reimbursement account from Alegeus Data. Alegeus request may have failed.",
            wallet_id=wallet.id,
            plan_id=plan.id,
        )
        return False, [
            FlashMessage(
                message=f"Reimbursement Account Creation Error: {str(error)}",
                category=FlashMessageCategory.ERROR,
            )
        ]

    # link dependents to new alegeus account
    reimbursement_wallet_user_dependents = (
        db.session.query(ReimbursementWalletUsers)
        .filter(
            ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id,
            type == WalletUserType.DEPENDENT,
        )
        .all()
    )
    seen_alegeus_dependent_ids = set()
    dependent_messages = []
    for dependent in wallet.authorized_users:
        response = api.post_link_dependent_to_employee_account(
            wallet, plan, dependent.alegeus_dependent_id
        )
        if not is_request_successful(response):
            log.error(
                "Unable to link legacy dependent(s) to employee account. Alegeus request failed.",
                wallet_id=wallet.id,
                plan_id=plan.id,
            )
            dependent_messages.append(
                FlashMessage(
                    message=f"Failed to link a legacy dependent ({dependent}) to this account {plan}: {response.text}",
                    category=FlashMessageCategory.ERROR,
                )
            )
            success = False
        seen_alegeus_dependent_ids.add(dependent.alegeus_dependent_id)

    for rwu_dependent in reimbursement_wallet_user_dependents:
        if rwu_dependent.alegeus_id in seen_alegeus_dependent_ids:
            continue
        response = api.post_link_dependent_to_employee_account(
            wallet, plan, rwu_dependent.alegeus_id
        )
        if not is_request_successful(response):
            log.error(
                "Unable to link RWU dependent(s) to employee account. Alegeus request failed.",
                wallet_id=wallet.id,
                plan_id=plan.id,
            )
            dependent_messages.append(
                FlashMessage(
                    message=f"Failed to link a dependent ({rwu_dependent}) to this account {plan}: {response.text}",
                    category=FlashMessageCategory.ERROR,
                )
            )
            success = False
        seen_alegeus_dependent_ids.add(rwu_dependent.alegeus_id)

    return success, dependent_messages


def get_employee_account(
    api: AlegeusApi, wallet: ReimbursementWallet, account: ReimbursementAccount
) -> Tuple[bool, Optional[dict]]:
    """
    Convenience function for calling the Alegeus API to get the details for a specific plan the member is enrolled in.
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @param account: the `ReimbursementAccount` corresponding to the plan the member is enrolled in
    @return: a tuple containing a boolean indicating whether the response was successful and the account data if so
    """
    account_details = None
    response = api.get_account_details(wallet, account)
    success = is_request_successful(response)
    if success:
        account_details = response.json()
    return success, account_details


def get_employee_accounts(
    api: AlegeusApi, wallet: ReimbursementWallet
) -> Tuple[bool, Optional[dict]]:
    """
    Convenience function for calling the Alegeus API to get the details for a specific plan the member is enrolled in.
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @param account: the `ReimbursementAccount` corresponding to the plan the member is enrolled in
    @return: a tuple containing a boolean indicating whether the response was successful and the account data if so
    """
    account_summary = None
    response = api.get_account_summary(wallet)
    success = is_request_successful(response)
    if success:
        account_summary = response.json()
    return success, account_summary


def create_reimbursement_account_from_alegeus(
    api: AlegeusApi, wallet: ReimbursementWallet, plan: ReimbursementPlan
) -> Tuple[bool, Optional[Any]]:
    """
    Call the Alegeus API to create a `ReimbursementAccount` with the information provided by Alegeus after enrollment.
    The call to enroll the member in the plan does not return the FlexAccountKey (the unique ID in the Alegeus system),
    therefore it is necessary to call the API using this function so that we can save this info in our system.
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @param plan: the `ReimbursementPlan` in which the member should be enrolled
    @return: boolean indicating whether the response was successful
    """
    account = ReimbursementAccount.query.filter_by(
        wallet=wallet,
        plan=plan,
    ).scalar()

    if account:
        return True, None
    else:
        # Create ReimbursementAccount and populate flex account key from the GET response
        response = api.get_account_summary(wallet)
        if not is_request_successful(response):
            return False, response.text

        try:
            resp_json = response.json()
            for account in resp_json:
                plan_id = account.get("PlanId", "")
                if plan.alegeus_plan_id.upper() == plan_id.upper():  # type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "upper"

                    status_code = account.get("AcctStatusCde")
                    maven_status = ReimbursementAccountStatus(status_code)

                    account_type = account.get("AccountType")
                    alegeus_account_type = ReimbursementAccountType.query.filter_by(
                        alegeus_account_type=account_type
                    ).one()

                    flex_account_key = account.get("FlexAccountKey")
                    if not flex_account_key:
                        log.error(
                            f"Account under Plan [ID: {plan_id}] does not have a FlexAccountKey."
                        )
                        return (
                            False,
                            f"Account under Plan [ID: {plan_id}] does not have a FlexAccountKey.",
                        )

                    reimbursement_account = ReimbursementAccount(
                        wallet=wallet,
                        plan=plan,
                        status=maven_status,
                        alegeus_flex_account_key=flex_account_key,
                        alegeus_account_type=alegeus_account_type,
                    )

                    db.session.add(reimbursement_account)
                    db.session.commit()
                    return True, None
            else:
                log.warning(
                    f"Plan with alegeus_plan_id: {plan.alegeus_plan_id} did not match any accounts in the Alegeus response"
                )
                return False, None
        except Exception as e:
            log.exception("Unable to create ReimbursementAccount", error=e)
            return False, str(e)


def configure_employee(
    api: AlegeusApi, wallet: ReimbursementWallet, messages: list
) -> Tuple[bool, List[FlashMessage]]:
    """
    Configure a member in the Alegeus system if the member is not already in the system.
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @param messages: collection of logging messages to be displayed in Admin
    @return: boolean indicating whether the response was successful
    """

    def tag_successful(
        successful: bool, reason: Optional[str] = None, end_point: Optional[str] = None
    ) -> None:
        metric_name = f"{metric_prefix}.configure_employee"

        if successful:
            tags = ["success:true"]
        else:
            metric_name = f"{metric_name}.error"
            tags = [
                "error:true",
                "error_cause:failed_configure_employee",
                f"reason:{reason}",
                f"end_point:{end_point}",
            ]
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    is_existing_employee = get_employee_demographic(api, wallet)
    if is_existing_employee:
        messages.append(
            FlashMessage(
                message=f"Found existing Employee in Alegeus for Wallet ID: {wallet.id}.",
                category=FlashMessageCategory.INFO,
            )
        )
    else:
        messages.append(
            FlashMessage(
                message=f"Could not find an existing Employee in Alegeus for Wallet ID: {wallet.id}. Will attempt to create one.",
                category=FlashMessageCategory.INFO,
            )
        )
        is_employee_created_in_alegeus, response = create_employee_demographic(
            api, wallet
        )

        if is_employee_created_in_alegeus:
            messages.append(
                FlashMessage(
                    message=f"Successfully created an Employee in Alegeus for Wallet ID: {wallet.id}.",
                    category=FlashMessageCategory.SUCCESS,
                )
            )
            tag_successful(True)
        else:
            message = f"Could not create Employee in Alegeus for Wallet ID: {wallet.id}. Error: {response.text}. Aborting Alegeus configuration."
            messages.append(
                FlashMessage(message=message, category=FlashMessageCategory.ERROR)
            )
            log.error(message)
            tag_successful(
                False,
                reason="alegeus_api_failure",
                end_point="create_employee_demographic",
            )
            return False, messages

    return True, messages


def configure_dependents(
    api: AlegeusApi, wallet: ReimbursementWallet, messages: list
) -> Tuple[bool, List[FlashMessage]]:
    """
    Configure a member's dependents in the Alegeus system if they are not already in the system.
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @param messages: collection of logging messages to be displayed in Admin
    @return: boolean indicating whether the response was successful
    """

    def tag_outcome(
        successful: bool, reason: str = None, end_point: str | None = None
    ) -> None:
        metric_name = f"{metric_prefix}.configure_dependents"
        if successful:
            tags = ["success:true"]
        else:
            tags = [
                "error:true",
                "error_cause:failed_configure_dependents",
                f"reason:{reason}",
                f"end_point:{end_point}",
            ]
            metric_name = f"{metric_name}.error"
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    # ReimbursementWalletUsers.alegeus_dependent_id is str
    reimbursement_wallet_user_user_ids_and_alegeus_dependent_ids: List[
        Tuple[int, str]
    ] = (
        db.session.query(
            # Need the user id to potentially enroll the dependent in Alegeus
            ReimbursementWalletUsers.user_id,
            ReimbursementWalletUsers.alegeus_dependent_id,
        )
        .filter(
            ReimbursementWalletUsers.reimbursement_wallet_id == wallet.id,
            ReimbursementWalletUsers.type == WalletUserType.DEPENDENT,
        )
        .all()
    )

    # While we transition from the legacy wallet model to the ReimbursementWalletUsers model,
    # we need to handle both models.
    if (
        wallet.authorized_users
        or reimbursement_wallet_user_user_ids_and_alegeus_dependent_ids
    ):
        _, dependents_in_alegeus = get_dependents(api, wallet)
        alegeus_dependent_ids = {
            dependent.get("DepId") for dependent in dependents_in_alegeus
        }
        for dependent in wallet.authorized_users:
            if dependent.alegeus_dependent_id in alegeus_dependent_ids:
                messages.append(
                    flash_existing_dependent(wallet.id, dependent.alegeus_dependent_id)
                )
            else:
                messages.append(
                    flash_missing_dependent(wallet.id, dependent.alegeus_dependent_id)
                )
                first_name = getattr(dependent, "first_name", "")
                last_name = getattr(dependent, "last_name", "")

                (
                    is_dependent_created_in_alegeus,
                    response,
                ) = create_dependent_demographic(
                    api, wallet, dependent.alegeus_dependent_id, first_name, last_name
                )

                if is_dependent_created_in_alegeus:
                    messages.append(
                        flash_successfully_created_alegeus_dependent(
                            wallet.id, dependent.alegeus_dependent_id
                        )
                    )
                    tag_outcome(True)
                else:
                    messages.append(
                        flash_failed_to_create_alegeus_dependent(
                            wallet.id, dependent.alegeus_dependent_id, response.text
                        )
                    )
                    tag_outcome(
                        False,
                        reason="alegeus_api_failure",
                        end_point="create_dependent_demographic",
                    )
                    return False, messages
        handled_alegeus_dependent_ids: Set[str] = {
            dependent.alegeus_dependent_id for dependent in wallet.authorized_users
        }
        for (
            rwu_user_id,
            rwu_alegeus_dependent_id,
        ) in reimbursement_wallet_user_user_ids_and_alegeus_dependent_ids:
            # Handle the above cases for the ReimbursementWalletUsers model.
            # This code will be "deduplicated" once the migration is complete the legacy model is deprecated.
            if rwu_alegeus_dependent_id not in handled_alegeus_dependent_ids:
                if rwu_alegeus_dependent_id in alegeus_dependent_ids:
                    messages.append(
                        flash_existing_dependent(wallet.id, rwu_alegeus_dependent_id)
                    )
                else:
                    messages.append(
                        flash_missing_dependent(wallet.id, rwu_alegeus_dependent_id)
                    )

                    first_name, last_name = db.session.query(
                        User.first_name, User.last_name
                    ).filter(User.id == rwu_user_id).one_or_none() or ["", ""]

                    (
                        is_dependent_created_in_alegeus,
                        response,
                    ) = create_dependent_demographic(
                        api, wallet, rwu_alegeus_dependent_id, first_name, last_name
                    )
                    if is_dependent_created_in_alegeus:
                        messages.append(
                            flash_successfully_created_alegeus_dependent(
                                wallet.id, rwu_alegeus_dependent_id
                            )
                        )
                        tag_outcome(True)
                    else:
                        messages.append(
                            flash_failed_to_create_alegeus_dependent(
                                wallet.id, rwu_alegeus_dependent_id, response.text
                            )
                        )
                        tag_outcome(
                            False,
                            reason="alegeus_api_failure",
                            end_point="create_dependent_demographic",
                        )
                        return False, messages
    else:
        messages.append(
            FlashMessage(
                message=f"Wallet ID: {wallet.id} has no associated dependents. Skipping Alegeus Dependent setup.",
                category=FlashMessageCategory.INFO,
            )
        )

    return True, messages


def flash_existing_dependent(wallet_id: int, alegeus_dependent_id: str) -> FlashMessage:
    return FlashMessage(
        message=f"Found existing Dependent (ID: {alegeus_dependent_id} in Alegeus for Wallet ID: {wallet_id}.",
        category=FlashMessageCategory.INFO,
    )


def flash_missing_dependent(wallet_id: int, alegeus_dependent_id: str) -> FlashMessage:
    return FlashMessage(
        message=f"Could not find existing Dependent (ID: {alegeus_dependent_id} in Alegeus for Wallet ID: {wallet_id}. Will attempt to create.",
        category=FlashMessageCategory.INFO,
    )


def flash_successfully_created_alegeus_dependent(
    wallet_id: int, alegeus_dependent_id: str
) -> FlashMessage:
    return FlashMessage(
        message=f"Successfully created Dependent (ID: {alegeus_dependent_id} in Alegeus for Wallet ID: {wallet_id}.",
        category=FlashMessageCategory.SUCCESS,
    )


def flash_failed_to_create_alegeus_dependent(
    wallet_id: int, alegeus_dependent_id: str, error_message: str
) -> FlashMessage:
    return FlashMessage(
        message=f"Could not create Dependent (ID: {alegeus_dependent_id} in Alegeus for Wallet ID: {wallet_id}. Error: {error_message}. Aborting Alegeus Configuration.",
        category=FlashMessageCategory.ERROR,
    )


def configure_account(
    api: AlegeusApi,
    wallet: ReimbursementWallet,
    plan: ReimbursementPlan,
    prefunded_amount: int,
    coverage_tier: AlegeusCoverageTier | None,
    start_date: Optional[datetime.date],
    messages: list,
) -> Tuple[bool, List[FlashMessage]]:
    """
    Enroll a member in a plan in Alegeus and create a corresponding `ReimbursementAccount`.
    Does not re-enroll a member if the member is already enrolled and will not recreate a `ReimbursementAccount`
    if it already exists.
    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @param plan: the `ReimbursementPlan` in which the member should be enrolled
    @param messages: collection of logging messages to be displayed in Admin
    @param prefunded_amount: the amount of money the member will have access to in the plan
    @param coverage_tier: enum for SINGLE/FAMILY
    @param start_date: date indicating the start of eligibility for this category
    @return: boolean indicating whether the response was successful
    """

    def tag_successful(
        successful: bool, reason: str | None = None, end_point: str | None = None
    ) -> None:
        metric_name = f"{metric_prefix}.configure_account"
        if successful:
            tags = ["success:true"]
        else:
            tags = ["error:true", "error_cause:failed_create_employee_account"]
            tags.append(f"reason:{reason}")
            tags.append(f"end_point:{end_point}")
            metric_name += ".error"
        stats.increment(
            metric_name=metric_name,
            pod_name=stats.PodNames.PAYMENTS_POD,
            tags=tags,
        )

    log.info(
        "configure_account called",
        wallet_id=str(wallet.id),
        prefunded_amount=str(prefunded_amount),
        plan=str(plan),
        coverage_tier=str(coverage_tier),
        start_date=str(start_date),
    )

    # Get any existing ReimbursementAccounts for this wallet/plan
    account = ReimbursementAccount.query.filter_by(
        wallet=wallet,
        plan=plan,
    ).scalar()

    # If we do not have an account for this wallet/plan, create it
    if not account:
        is_account_created_in_alegeus, alegeus_messages = create_employee_account(
            api, wallet, plan, prefunded_amount, coverage_tier, start_date
        )
        if is_account_created_in_alegeus:
            messages.append(
                FlashMessage(
                    message=f"Successfully created ReimbursementAccount for {plan} in Alegeus for Wallet ID: {wallet.id}.",
                    category=FlashMessageCategory.SUCCESS,
                )
            )
            tag_successful(True)
        else:
            messages.extend(alegeus_messages)
            messages.append(
                FlashMessage(
                    message=f"Could not create ReimbursementAccount for {plan} in Alegeus for Wallet ID: {wallet.id}.",
                    category=FlashMessageCategory.ERROR,
                )
            )
            tag_successful(
                False, reason="alegeus_api_failure", end_point="create_employee_account"
            )
            return False, messages
    else:
        account_exists_in_alegeus, _unused = get_employee_account(api, wallet, account)
        if account_exists_in_alegeus:
            messages.append(
                FlashMessage(
                    message=f"Found existing Account (ID: {account.id}, FlexAcctKey: {account.alegeus_flex_account_key}) in Alegeus for {wallet}, {plan}.",
                    category=FlashMessageCategory.INFO,
                )
            )
        else:
            messages.append(
                FlashMessage(
                    message=f"Could not find existing Account (ID: {account.id}, FlexAcctKey: {account.alegeus_flex_account_key}) in Alegeus for {wallet}, {plan}.",
                    category=FlashMessageCategory.WARNING,
                )
            )
            tag_successful(
                False, reason="alegeus_api_failure", end_point="get_employee_account"
            )
            is_account_created_in_alegeus, alegeus_messages = create_employee_account(
                api, wallet, plan, prefunded_amount, coverage_tier, start_date
            )
            if is_account_created_in_alegeus:
                messages.append(
                    FlashMessage(
                        message=f"Successfully created Account (ID: {account.id}, FlexAcctKey: {account.alegeus_flex_account_key}) in Alegeus for {wallet}, {plan}.",
                        category=FlashMessageCategory.SUCCESS,
                    )
                )
                tag_successful(True)
            else:
                messages.extend(alegeus_messages)
                messages.append(
                    FlashMessage(
                        message=f"Could not create Account (ID: {account.id}, FlexAcctKey: {account.alegeus_flex_account_key}) in Alegeus for {wallet}, {plan}.",
                        category=FlashMessageCategory.ERROR,
                    )
                )
                tag_successful(
                    False,
                    reason="alegeus_api_failure",
                    end_point="create_employee_account",
                )
                return False, messages

    return True, messages


def get_banking_info(api: AlegeusApi, wallet: ReimbursementWallet) -> Optional[dict]:
    """
    Retrieve a member's full bank account information, which is not stored locally.

    @param api: instance of `AlegeusApi`
    @param wallet: the member's `ReimbursementWallet`
    @return: banking info, or None
    """

    if wallet.reimbursement_method == ReimbursementMethod.DIRECT_DEPOSIT:
        response = api.get_employee_details(wallet)
        if is_request_successful(response):
            employee_details_json = response.json()
            banking_info = {
                "BankAcctName": employee_details_json.get("BankName", ""),
                "BankAccount": employee_details_json.get("BankAccountNumber", ""),
                "BankAccountTypeCode": employee_details_json.get(
                    "BankAccountTypeCode", ""
                ),
                "BankRoutingNumber": employee_details_json.get("BankRoutingNumber", ""),
            }
            # explicitly clearing/deleting the variable to protect sensitive data
            employee_details_json = None
            del employee_details_json
            response = None
            del response

            if banking_info["BankAcctName"] and banking_info["BankAccount"]:
                return banking_info

    return None


def _get_hdhp_plan(wallet: ReimbursementWallet) -> Optional[ReimbursementPlan]:
    if len(wallet.reimbursement_hdhp_plans) == 0:
        return None

    current_hdhp_plan = None
    for hdhp_plan in wallet.reimbursement_hdhp_plans:
        plan = hdhp_plan.reimbursement_plan
        if plan and plan.start_date <= datetime.date.today() <= plan.end_date:
            current_hdhp_plan = plan
            break

    if current_hdhp_plan is None:
        return None
    return current_hdhp_plan


def _get_hdhp_account_summary(
    plan: ReimbursementPlan, wallet: ReimbursementWallet
) -> Optional[dict]:
    api = alegeus_api.AlegeusApi()
    success, account_summary = get_employee_accounts(api, wallet)

    if not success:
        log.error(
            "Failed to retrieve account summary",
            wallet=wallet,
        )
        return None

    hdhp_account_summary = None
    for account in account_summary:  # type: ignore[union-attr] # Item "None" of "Optional[Dict[Any, Any]]" has no attribute "__iter__" (not iterable)
        plan_id = account.get("PlanId", "")
        if plan.alegeus_plan_id.upper() == plan_id.upper():  # type: ignore[union-attr] # Item "None" of "Optional[str]" has no attribute "upper"
            hdhp_account_summary = account
    return hdhp_account_summary


def check_hdhp_status(wallet: ReimbursementWallet) -> Optional[bool]:
    """
    Checks if an HDHP account linked to this wallet has met the necessary deductible.

    May fail closed (returning False) if some data is expected but not available.

    @return: None if no HDHP, False if unmet (*or cannot be determined*), True if met
    """
    current_hdhp_plan = _get_hdhp_plan(wallet)
    if not current_hdhp_plan:
        return None

    hdhp_account_summary = _get_hdhp_account_summary(
        plan=current_hdhp_plan, wallet=wallet
    )
    if not hdhp_account_summary:
        log.error(
            "Missing account for HDHP plan", wallet=wallet, hdhp_plan=current_hdhp_plan
        )
        return False

    annual_election = hdhp_account_summary.get("AnnualElection", None)
    available_balance = hdhp_account_summary.get("AvailBalance", None)

    if annual_election is None or available_balance is None:
        log.error(
            "Account details missing balances",
            wallet=wallet,
            hdhp_plan=current_hdhp_plan,
            annual_election=annual_election,
            available_balance=available_balance,
        )
        return False

    if annual_election == 0:
        # DTR account hasn't been funded yet (it happens nightly)
        return False

    return available_balance == 0


def get_alegeus_hdhp_plan_year_to_date_spend(
    wallet: ReimbursementWallet,
) -> Optional[int]:
    """
    Checks how much the member has spent towards their HDHP plan deductible,
    returns the difference between AnnualElection and AvailBalance returned from alegeus,
    @return: None if no HDHP, exception raised when unexpected happens. Return the difference if succeeds.
    """
    current_hdhp_plan = _get_hdhp_plan(wallet)
    if not current_hdhp_plan:
        return None

    hdhp_account_summary = _get_hdhp_account_summary(
        plan=current_hdhp_plan, wallet=wallet
    )
    if not hdhp_account_summary:
        msg = "Missing account for HDHP plan"
        log.error(msg, wallet=wallet, hdhp_plan=current_hdhp_plan)
        raise ValueError(msg)

    annual_election = hdhp_account_summary.get("AnnualElection", None)
    available_balance = hdhp_account_summary.get("AvailBalance", None)

    if annual_election is None or available_balance is None:
        msg = "Account details missing balances"
        log.error(
            msg,
            wallet=wallet,
            hdhp_plan=current_hdhp_plan,
            annual_election=annual_election,
            available_balance=available_balance,
        )
        raise ValueError(msg)

    year_to_date_spend: int = max(
        convert_dollars_to_cents(annual_election - available_balance), 0
    )
    return year_to_date_spend


def get_eligibility_date_from_wallet(
    wallet: ReimbursementWallet,
    wallet_enablement: Optional[e9y_model.WalletEnablement] = None,
) -> Optional[datetime.date]:
    """
    Call the e9y service to retrieve a member's eligibility date and get a plan start date from the 'first' non-hdhp
    ReimbursementPlan. Add tenure to the larger of the two start dates.
    # See https://mavenclinic.atlassian.net/issues/ARCH-2688
    # See https://mavenclinic.atlassian.net/browse/PAY-6234
    @param wallet: the member's `ReimbursementWallet`
    @param wallet_enablement: the member's `WalletEnablement`
    @return: the eligibility date or creation date of the earliest verification if available, else None
    """
    # Get the start date for the 'first' non-hdhp ReimbursementPlan for the Member.
    plan_start_date = _get_wallet_plan_start_date(wallet=wallet)

    # Get an eligibility date from the e9y service
    user_id = wallet.all_active_users[0].id if wallet.all_active_users else None
    base_eligibility_date = _get_wallet_eligibility_date(
        user_id=user_id, wallet=wallet, wallet_enablement=wallet_enablement
    )
    if base_eligibility_date is not None:
        eligibility_date = base_eligibility_date + datetime.timedelta(
            days=wallet.reimbursement_organization_settings.required_tenure_days
        )
    else:
        eligibility_date = base_eligibility_date

    valid_dates = list(filter(None, [plan_start_date, eligibility_date]))
    later_of_e9y_and_plan_start_date = max(valid_dates) if valid_dates else None
    log.info(
        "get_eligibility_date_from_wallet.",
        plan_start_date=plan_start_date,
        base_eligibility_date=base_eligibility_date,
        later_of_e9y_and_plan_start_date=later_of_e9y_and_plan_start_date,
        eligibility_date_with_tenure=eligibility_date,
        wallet_id=str(wallet.id),
        user_id=str(user_id),
    )
    return later_of_e9y_and_plan_start_date


def _get_wallet_plan_start_date(wallet: ReimbursementWallet) -> Optional[datetime.date]:
    """
    Wallet_allowed_categories are pulled from the CategoryActivationService without an order by statement.
    We want the earliest start date available from the allowed_categories.
    We purposefully DO NOT use per-category tenure rules to adjust these start dates.
    This function gets called (should get called?) before the wallet is setup in Alegeus - so we use the
    get_wallet_allowed_categories method to avoid category setup in Alegeus. This method also reads directly
    from the database and will skip the cache.
    """
    allowed_categories = wallet.get_wallet_allowed_categories
    non_hdhp_plan_start_dates = [
        allowed_category.reimbursement_request_category.reimbursement_plan.start_date
        for allowed_category in allowed_categories
        if allowed_category.reimbursement_request_category.reimbursement_plan
        and not allowed_category.reimbursement_request_category.reimbursement_plan.is_hdhp
        and allowed_category.reimbursement_request_category.reimbursement_plan.start_date
        is not None
    ]
    if len(non_hdhp_plan_start_dates) == 0:
        return None
    return min(non_hdhp_plan_start_dates)


def _get_wallet_eligibility_date(
    user_id: Optional[int],
    wallet: ReimbursementWallet,
    wallet_enablement: Optional[e9y_model.WalletEnablement] = None,
) -> Optional[datetime.date]:
    """
    In waterfall order, pick the e9y date to be:
    1. The wallet eligibility start date (wallet_enablement.start_date)
    2. The eligibility employee start date (also wallet_enablement.start_date)
    3. The eligibility record created_at date
    4. The earliest employee verification date for any active user on the wallet
    """
    if wallet_enablement is None:
        wallet_enablement = (
            e9y.grpc_service.wallet_enablement_by_user_id_search(
                user_id=user_id,
            )
            if user_id
            else None
        )
    if wallet_enablement and wallet_enablement.start_date:
        # The wallet enablement start date is a combination of wallet_eligibility_start_date and employee_start_date
        # See: https://gitlab.com/maven-clinic/maven/eligibility-api/-/blob/main/db/queries/member_2/fetch.sql?ref_type=heads#L95
        eligibility_date = wallet_enablement.start_date
    elif wallet_enablement and wallet_enablement.created_at:
        eligibility_date = wallet_enablement.created_at.date()
    else:
        # Use the earliest verification date for all active users of a wallet
        # Note: this may hit the eligibility service multiple times
        min_verification_at = None
        org_id = wallet.reimbursement_organization_settings.organization_id
        e9y_svc = e9y_service.EnterpriseVerificationService()
        for user in wallet.all_active_users:
            verification: Optional[
                e9y_model.EligibilityVerification
            ] = e9y_svc.get_verification_for_user_and_org(
                user_id=user.id, organization_id=org_id
            )
            if verification:
                if min_verification_at is None:
                    min_verification_at = verification.verified_at
                else:
                    min_verification_at = min(
                        min_verification_at, verification.verified_at
                    )
        eligibility_date = min_verification_at.date() if min_verification_at else None
    if eligibility_date is None:
        log.warning(
            "get_eligibility_date_from_wallet: No wallet enablement. Member is not enabled for wallet. ",
            wallet_id=str(wallet.id),
            user_id=user_id,
        )
        stats.increment(
            f"{metric_prefix}.get_eligibility_date_from_wallet.no_wallet_enablement",
            pod_name=stats.PodNames.PAYMENTS_POD,
        )
    return eligibility_date


def update_member_accounts(
    start_date: datetime.date, organization_ids: list
) -> Optional[bool]:
    """
    Finds qualified wallets for a given organizations plans, filtered by a specific start_date,
    enrolls all qualified wallets into member accounts and creates associated reimbursement accounts.

    Useful for an organization that has a plan rolled over or added new.

    @param start_date The date object to filter plan start date by
    @param organization_ids A list of organizations
    @return bool if it runs without an exception
    """

    api = alegeus_api.AlegeusApi()

    for organization_id in organization_ids:
        error_count = 0
        try:
            organization_settings = ReimbursementOrganizationSettings.query.filter_by(
                organization_id=organization_id
            ).one()
            all_wallets = organization_settings.reimbursement_wallets
            qualified_wallets = [
                w for w in all_wallets if w.state == WalletState.QUALIFIED
            ]
            allowed_categories = organization_settings.allowed_reimbursement_categories

            for allowed_category in allowed_categories:
                request_category = allowed_category.reimbursement_request_category

                if request_category.reimbursement_plan:
                    plan = request_category.reimbursement_plan
                    if (
                        plan
                        and plan.reimbursement_account_type.alegeus_account_type
                        != "DTR"
                    ):
                        if plan.start_date >= start_date <= plan.end_date:
                            for wallet in qualified_wallets:
                                allowed_wallet_categories = (
                                    wallet.get_wallet_allowed_categories
                                )
                                if allowed_category in allowed_wallet_categories:
                                    try:
                                        start_date = get_start_date(
                                            allowed_category, plan, wallet.user_id
                                        )
                                        success, _ = configure_account(
                                            api=api,
                                            wallet=wallet,
                                            plan=plan,
                                            prefunded_amount=allowed_category.usd_funding_amount,
                                            coverage_tier=None,
                                            start_date=start_date,
                                            messages=[],
                                        )
                                        if not success:
                                            error_count += 1
                                            log.error(
                                                "update_member_accounts: configure_account was not successful.",
                                                wallet_id=wallet.id,
                                                organization_id=organization_id,
                                            )
                                    except Exception as e:
                                        error_count += 1
                                        log.exception(
                                            "update_member_accounts: configure_account threw an unexpected exception.",
                                            wallet_id=wallet.id,
                                            organization_id=organization_id,
                                            error=e,
                                        )
                            log.info(
                                f"update_member_accounts: {len(qualified_wallets)} qualified wallet accounts "
                                f"configured in Alegeus for plan: {plan.alegeus_plan_id}. {error_count} errors logged."
                            )

        except (NoResultFound, MultipleResultsFound) as e:
            log.exception(
                "update_member_accounts: Exception finding organization settings.",
                error=e,
                organization_id=organization_id,
            )
            raise e

    return True


def configure_wallet_allowed_category(
    wallet: ReimbursementWallet, allowed_category_id: int
) -> Tuple[bool, List[FlashMessage]]:
    """
    Configures the wallet and plan associated with the allowed category in Alegeus.
    """
    api = alegeus_api.AlegeusApi()
    error_message = "Failed to configure wallet allowed category account in Alegeus."
    success = False
    messages = []
    log.info(
        "configure_wallet_allowed_category for wallet and allowed category.",
        wallet_id=str(wallet.id),
        allowed_category_id=str(allowed_category_id),
    )
    allowed_category = (
        db.session.query(ReimbursementOrgSettingCategoryAssociation)
        .filter(ReimbursementOrgSettingCategoryAssociation.id == allowed_category_id)
        .options(
            joinedload(
                ReimbursementOrgSettingCategoryAssociation.reimbursement_request_category
            ).options(joinedload(ReimbursementRequestCategory.reimbursement_plan))
        )
        .one_or_none()
    )
    try:
        if allowed_category:
            request_category = allowed_category.reimbursement_request_category
            if request_category:
                plan = request_category.reimbursement_plan
                if plan:
                    start_date = get_start_date(allowed_category, plan, wallet.user_id)  # type: ignore[arg-type]
                    success, messages = configure_account(
                        api=api,
                        wallet=wallet,
                        plan=plan,
                        prefunded_amount=allowed_category.usd_funding_amount,
                        coverage_tier=None,
                        start_date=start_date,
                        messages=[],
                    )
                    log.info(
                        "configure_account for wallet and allowed category results.",
                        results=success,
                        wallet_id=str(wallet.id),
                        allowed_category_id=str(allowed_category_id),
                    )
                    if not success:
                        log.error(
                            error_message,
                            wallet_id=str(wallet.id),
                            allowed_category_id=str(allowed_category_id),
                            error="Alegeus configure_account failed.",
                        )
                else:
                    log.info(
                        "Skipping configure account for allowed category without a plan.",
                        wallet_id=str(wallet.id),
                        allowed_category_id=str(allowed_category_id),
                    )
                    return True, []
            else:
                log.error(
                    error_message,
                    wallet_id=str(wallet.id),
                    allowed_category_id=str(allowed_category_id),
                    error="Missing allowed category.",
                )
    except Exception as e:
        log.error(
            error_message,
            wallet_id=str(wallet.id),
            allowed_category_id=str(allowed_category_id),
            error=str(e),
            traceback=format_exc(),
        )
    return success, messages
