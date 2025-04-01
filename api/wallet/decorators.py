from flask import abort

from utils.log import logger
from wallet.constants import HISTORICAL_SPEND_LABEL
from wallet.models.constants import (
    ReimbursementRequestAutoProcessing,
    ReimbursementRequestType,
    WalletState,
)

log = logger(__name__)


def validate_wallet(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from wallet.models.reimbursement_wallet import ReimbursementWallet

        arg_wallet = [arg for arg in args if isinstance(arg, ReimbursementWallet)]
        kwarg_wallet = [
            v for v in kwargs.values() if isinstance(v, ReimbursementWallet)
        ]
        wallet = (
            kwarg_wallet[0] if kwarg_wallet else arg_wallet[0] if arg_wallet else None
        )

        if not wallet:
            abort(
                500,
                "Cannot use this wrapper on a function that does not have a ReimbursementWallet parameter",
            )

        if wallet.state not in [WalletState.QUALIFIED, WalletState.RUNOUT]:
            abort(
                403,
                f"Wallet ID={wallet.id} is not QUALIFIED or RUNOUT (currently: {wallet.state})",
            )

        organization_settings = wallet.reimbursement_organization_settings
        if not organization_settings:
            abort(
                500,
                f"Wallet ID={wallet.id} does not have an associated ReimbursementOrganizationSettings",
            )

        organization = organization_settings.organization
        if not organization:
            abort(
                500,
                f"ReimbursementOrganizationSettings ID={organization_settings.id} does not have an associated Organization",
            )

        if not organization.alegeus_employer_id:
            abort(
                500,
                f"Organization ID={organization.id} does not have an alegeus_employer_id",
            )

        if not wallet.alegeus_id:
            log.error(
                "Wallet missing alegeus_id when making an alegeus api call.",
                wallet_id=str(wallet.id),
            )
            abort(
                500,
                f"Wallet ID={wallet.id} does not have an alegeus_id",
            )

        return func(*args, **kwargs)

    return wrapper


def validate_plan(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from wallet.models.reimbursement import ReimbursementPlan

        arg_plan = [arg for arg in args if isinstance(arg, ReimbursementPlan)]
        kwarg_plan = [v for v in kwargs.values() if isinstance(v, ReimbursementPlan)]
        plan = kwarg_plan[0] if kwarg_plan else arg_plan[0] if arg_plan else None

        assert (
            plan
        ), "Cannot use this wrapper on a function that does not have a ReimbursementPlan parameter"

        reimbursement_account_type = plan.reimbursement_account_type
        assert (
            reimbursement_account_type
        ), f"Plan ID={plan.id} does not have an associated ReimbursementAccountType"

        alegeus_account_type = reimbursement_account_type.alegeus_account_type
        assert (
            alegeus_account_type
        ), f"ReimbursementAccountType ID={reimbursement_account_type.id} does not have an alegeus_account_type value"

        alegeus_plan_id = plan.alegeus_plan_id
        assert (
            alegeus_plan_id
        ), f"Plan ID={plan.id} does not have an alegeus_plan_id value"

        start_date = plan.start_date
        assert start_date, f"Plan ID={plan.id} does not have a start date"

        end_date = plan.end_date
        assert end_date, f"Plan ID={plan.id} does not have an end date"

        return func(*args, **kwargs)

    return wrapper


def validate_dependent(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from wallet.models.organization_employee_dependent import (
            OrganizationEmployeeDependent,
        )

        arg_dependent = [
            arg for arg in args if isinstance(arg, OrganizationEmployeeDependent)
        ]
        kwarg_dependent = [
            v for v in kwargs.values() if isinstance(v, OrganizationEmployeeDependent)
        ]
        dependent = (
            kwarg_dependent[0]
            if kwarg_dependent
            else arg_dependent[0]
            if arg_dependent
            else None
        )

        assert (
            dependent
        ), "Cannot use this wrapper on a function that does not have an OrganizationEmployeeDependent parameter"

        alegeus_dependent_id = dependent.alegeus_dependent_id
        assert (
            alegeus_dependent_id
        ), f"Dependent ID={dependent.id} does not have an alegeus_dependent_id"

        return func(*args, **kwargs)

    return wrapper


def validate_account(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from wallet.models.reimbursement import ReimbursementAccount

        arg_account = [arg for arg in args if isinstance(arg, ReimbursementAccount)]
        kwarg_account = [
            v for v in kwargs.values() if isinstance(v, ReimbursementAccount)
        ]
        account = (
            kwarg_account[0]
            if kwarg_account
            else arg_account[0]
            if arg_account
            else None
        )

        assert (
            account
        ), "Cannot use this wrapper on a function that does not have a ReimbursementAccount parameter"

        alegeus_account_type = account.alegeus_account_type
        assert (
            alegeus_account_type
        ), f"ReimbursementAccount ID={account.id} does not have an alegeus_account_type value"

        alegeus_flex_account_key = account.alegeus_flex_account_key
        assert (
            alegeus_flex_account_key
        ), f"ReimbursementAccount ID={account.id} does not have an alegeus_flex_account_key value"

        return func(*args, **kwargs)

    return wrapper


def validate_reimbursement_request(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from wallet.models.reimbursement import ReimbursementRequest

        arg_reimbursement_request = [
            arg for arg in args if isinstance(arg, ReimbursementRequest)
        ]
        kwarg_reimbursement_request = [
            v for v in kwargs.values() if isinstance(v, ReimbursementRequest)
        ]
        reimbursement_request = (
            kwarg_reimbursement_request[0]
            if kwarg_reimbursement_request
            else arg_reimbursement_request[0]
            if arg_reimbursement_request
            else None
        )

        assert (
            reimbursement_request
        ), "Cannot use this wrapper on a function that does not have a ReimbursementRequest parameter"

        service_start_date = reimbursement_request.service_start_date
        assert (
            service_start_date
        ), f"ReimbursementRequest ID={reimbursement_request.id} does not have a service start date"

        amount = reimbursement_request.usd_reimbursement_amount
        assert (
            amount
        ), f"ReimbursementRequest ID={reimbursement_request.id} does not have an amount"

        if (
            reimbursement_request.reimbursement_type
            != ReimbursementRequestType.DIRECT_BILLING
            and reimbursement_request.auto_processed
            != ReimbursementRequestAutoProcessing.RX
            and reimbursement_request.label != HISTORICAL_SPEND_LABEL
        ):
            sources = reimbursement_request.sources
            assert (
                sources
            ), f"ReimbursementRequest ID={reimbursement_request.id} does not have any sources / attachments"

        return func(*args, **kwargs)

    return wrapper


def validate_user_asset(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from models.enterprise import UserAsset, UserAssetState

        arg_user_asset = [arg for arg in args if isinstance(arg, UserAsset)]
        kwarg_user_asset = [v for v in kwargs.values() if isinstance(v, UserAsset)]

        user_asset = (
            kwarg_user_asset[0]
            if kwarg_user_asset
            else arg_user_asset[0]
            if arg_user_asset
            else None
        )

        assert (
            user_asset
        ), "Cannot use this wrapper on a function that does not have a UserAsset parameter"

        user = user_asset.user
        assert user, f"UserAsset ID={user_asset.id} does not have a user"

        file_name = user_asset.file_name
        assert file_name, f"UserAsset ID={user_asset.id} does not have a file name"

        content_type = user_asset.content_type
        assert (
            content_type
        ), f"UserAsset ID={user_asset.id} does not have a content-type"

        state = user_asset.state
        assert (
            state == UserAssetState.COMPLETE
        ), f"UserAsset ID={user_asset.id} is not ready to be served"

        return func(*args, **kwargs)

    return wrapper


def validate_claim(func):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    def wrapper(*args, **kwargs):  # type: ignore[no-untyped-def] # Function is missing a type annotation
        from wallet.models.reimbursement import ReimbursementClaim

        arg_claim = [arg for arg in args if isinstance(arg, ReimbursementClaim)]
        kwarg_claim = [v for v in kwargs.values() if isinstance(v, ReimbursementClaim)]

        claim = kwarg_claim[0] if kwarg_claim else arg_claim[0] if arg_claim else None

        assert (
            claim
        ), "Cannot use this wrapper on a function that does not have a ReimbursementClaim parameter"

        reimbursement_request = claim.reimbursement_request
        assert (
            reimbursement_request
        ), f"Claim ID={claim.id} does not have a reimbursement_request"

        amount = claim.amount
        assert amount, f"Claim ID={claim.id} does not have an amount"

        alegeus_claim_id = claim.alegeus_claim_id
        assert (
            alegeus_claim_id
        ), f"Claim ID={claim.id} does not have an alegeus_claim_id"

        return func(*args, **kwargs)

    return wrapper
