import pytest
from werkzeug.exceptions import HTTPException

from models.enterprise import UserAsset, UserAssetState
from wallet.decorators import (
    validate_account,
    validate_claim,
    validate_dependent,
    validate_plan,
    validate_reimbursement_request,
    validate_user_asset,
    validate_wallet,
)
from wallet.models.constants import WalletState
from wallet.models.organization_employee_dependent import OrganizationEmployeeDependent
from wallet.models.reimbursement import (
    ReimbursementAccount,
    ReimbursementClaim,
    ReimbursementPlan,
    ReimbursementRequest,
    ReimbursementWallet,
)
from wallet.models.reimbursement_organization_settings import (
    ReimbursementOrganizationSettings,
)
from wallet.pytests.factories import (
    ReimbursementClaimFactory,
    ReimbursementPlanFactory,
    ReimbursementWalletFactory,
    WalletUserAssetFactory,
)


def test_validate_wallet_decorator__invalid_no_organization_settings():
    @validate_wallet
    def fn(r_wallet: ReimbursementWallet):
        return r_wallet

    wallet = ReimbursementWallet(state=WalletState.QUALIFIED)

    with pytest.raises(
        HTTPException,
        match=r"500 Internal Server Error: Wallet ID=.* does not have an associated ReimbursementOrganizationSettings",
    ):
        fn(wallet)


def test_validate_wallet_decorator__invalid_wallet_state():
    @validate_wallet
    def fn(r_wallet: ReimbursementWallet):
        return r_wallet

    org_settings = ReimbursementOrganizationSettings()
    wallet = ReimbursementWallet(
        state=WalletState.DISQUALIFIED, reimbursement_organization_settings=org_settings
    )

    with pytest.raises(
        HTTPException,
        match=r"403 Forbidden: Wallet ID=.* is not QUALIFIED or RUNOUT \(currently: DISQUALIFIED\)",
    ):
        fn(wallet)


def test_validate_wallet_decorator__invalid_no_organization():
    @validate_wallet
    def fn(r_wallet: ReimbursementWallet):
        return r_wallet

    org_settings = ReimbursementOrganizationSettings()
    wallet = ReimbursementWallet(
        reimbursement_organization_settings=org_settings, state=WalletState.QUALIFIED
    )

    with pytest.raises(
        HTTPException,
        match=r"500 Internal Server Error: ReimbursementOrganizationSettings ID=.* does not have an associated Organization",
    ):
        fn(wallet)


def test_validate_wallet_decorator__invalid_no_alegeus_employer_id(enterprise_user):
    @validate_wallet
    def fn(r_wallet: ReimbursementWallet):
        return r_wallet

    wallet = ReimbursementWalletFactory.create(state=WalletState.QUALIFIED)

    with pytest.raises(
        HTTPException,
        match=r"500 Internal Server Error: Organization ID=\d+ does not have an alegeus_employer_id",
    ):
        fn(wallet)


def test_validate_wallet_decorator__invalid_no_alegeus_id(
    qualified_alegeus_wallet_hdhp_single,
):
    @validate_wallet
    def fn(r_wallet: ReimbursementWallet):
        return r_wallet

    qualified_alegeus_wallet_hdhp_single.alegeus_id = None

    with pytest.raises(
        HTTPException,
        match=r"500 Internal Server Error: Wallet ID=\d+ does not have an alegeus_id",
    ):
        fn(qualified_alegeus_wallet_hdhp_single)


def test_validate_wallet_decorator__invalid_no_wallet_parameter_in_func(
    qualified_alegeus_wallet_hdhp_single,
):
    @validate_wallet
    def fn():
        return True

    with pytest.raises(
        HTTPException,
        match=r"500 Internal Server Error: Cannot use this wrapper on a function that does not have a ReimbursementWallet parameter",
    ):
        fn()


def test_validate_wallet_decorator__valid(qualified_alegeus_wallet_hdhp_single):
    @validate_wallet
    def fn(r_wallet: ReimbursementWallet):
        return r_wallet

    assert (
        fn(qualified_alegeus_wallet_hdhp_single) == qualified_alegeus_wallet_hdhp_single
    )


def test_validate_plan_decorator__invalid_no_reimbursement_account_type():
    @validate_plan
    def fn(r_plan: ReimbursementPlan):
        return r_plan

    plan = ReimbursementPlanFactory.create()

    with pytest.raises(
        AssertionError,
        match=r"Plan ID=.* does not have an associated ReimbursementAccountType",
    ):
        fn(plan)


def test_validate_plan_decorator__invalid_no_alegeus_account_type(
    valid_alegeus_plan_hdhp,
):
    @validate_plan
    def fn(r_plan: ReimbursementPlan):
        return r_plan

    plan = valid_alegeus_plan_hdhp
    plan.reimbursement_account_type.alegeus_account_type = None

    with pytest.raises(
        AssertionError,
        match=r"ReimbursementAccountType ID=.* does not have an alegeus_account_type value",
    ):
        fn(plan)


def test_validate_plan_decorator__invalid_no_alegeus_plan_id(valid_alegeus_plan_hdhp):
    @validate_plan
    def fn(r_plan: ReimbursementPlan):
        return r_plan

    plan = valid_alegeus_plan_hdhp
    plan.alegeus_plan_id = None

    with pytest.raises(
        AssertionError, match=r"Plan ID=.* does not have an alegeus_plan_id value"
    ):
        fn(plan)


def test_validate_plan_decorator__invalid_no_start_date(valid_alegeus_plan_hdhp):
    @validate_plan
    def fn(r_plan: ReimbursementPlan):
        return r_plan

    plan = valid_alegeus_plan_hdhp
    plan.start_date = None

    with pytest.raises(AssertionError, match=r"Plan ID=.* does not have a start date"):
        fn(plan)


def test_validate_plan_decorator__invalid_no_end_date(valid_alegeus_plan_hdhp):
    @validate_plan
    def fn(r_plan: ReimbursementPlan):
        return r_plan

    plan = valid_alegeus_plan_hdhp
    plan.end_date = None

    with pytest.raises(AssertionError, match=r"Plan ID=.* does not have an end date"):
        fn(plan)


def test_validate_plan_decorator__valid(valid_alegeus_plan_hdhp):
    @validate_plan
    def fn(r_plan: ReimbursementPlan):
        return r_plan

    assert fn(valid_alegeus_plan_hdhp) == valid_alegeus_plan_hdhp


def test_validate_dependent__invalid_no_alegeus_dependent_id():
    @validate_dependent
    def fn(org_dependent: OrganizationEmployeeDependent):
        return org_dependent

    dependent = OrganizationEmployeeDependent()
    with pytest.raises(
        AssertionError, match=r"Dependent ID=.* does not have an alegeus_dependent_id"
    ):
        fn(dependent)


def test_validate_dependent__valid():
    @validate_dependent
    def fn(org_dependent: OrganizationEmployeeDependent):
        return org_dependent

    dependent = OrganizationEmployeeDependent()
    dependent.create_alegeus_dependent_id()

    assert fn(dependent) == dependent


def test_validate_reimbursement_request__invalid_no_service_start_date(
    valid_reimbursement_request,
):
    @validate_reimbursement_request
    def fn(request: ReimbursementRequest):
        return request

    valid_reimbursement_request.service_start_date = None

    with pytest.raises(
        AssertionError,
        match=r"ReimbursementRequest ID=.* does not have a service start date",
    ):
        fn(valid_reimbursement_request)


def test_validate_reimbursement_request__invalid_no_amount(valid_reimbursement_request):
    @validate_reimbursement_request
    def fn(request: ReimbursementRequest):
        return request

    valid_reimbursement_request.amount = None

    with pytest.raises(
        AssertionError, match=r"ReimbursementRequest ID=.* does not have an amount"
    ):
        fn(valid_reimbursement_request)


def test_validate_reimbursement_request__invalid_no_sources(
    valid_reimbursement_request,
):
    @validate_reimbursement_request
    def fn(request: ReimbursementRequest):
        return request

    valid_reimbursement_request.sources = []

    with pytest.raises(
        AssertionError,
        match=r"ReimbursementRequest ID=.* does not have any sources / attachments",
    ):
        fn(valid_reimbursement_request)


def test_validate_reimbursement_request__valid(valid_reimbursement_request):
    @validate_reimbursement_request
    def fn(request: ReimbursementRequest):
        return request

    assert fn(valid_reimbursement_request) == valid_reimbursement_request


def test_validate_account_decorator__invalid_no_alegeus_account_type(
    valid_alegeus_account_hra,
):
    @validate_account
    def fn(r_account: ReimbursementAccount):
        return r_account

    account = valid_alegeus_account_hra
    account.alegeus_account_type = None

    with pytest.raises(
        AssertionError,
        match=r"ReimbursementAccount ID=.* does not have an alegeus_account_type value",
    ):
        fn(account)


def test_validate_account_decorator__invalid_no_alegeus_flex_account_key(
    valid_alegeus_account_hra,
):
    @validate_account
    def fn(r_account: ReimbursementAccount):
        return r_account

    account = valid_alegeus_account_hra
    account.alegeus_flex_account_key = None

    with pytest.raises(
        AssertionError,
        match=r"ReimbursementAccount ID=.* does not have an alegeus_flex_account_key value",
    ):
        fn(account)


def test_validate_account_decorator__valid(valid_alegeus_account_hra):
    @validate_account
    def fn(r_account: ReimbursementAccount):
        return r_account

    assert fn(valid_alegeus_account_hra) == valid_alegeus_account_hra


def test_validate_user_asset__valid(enterprise_user):
    @validate_user_asset
    def fn(ua: UserAsset):
        return ua

    user_asset = WalletUserAssetFactory.create(user=enterprise_user)

    assert fn(user_asset) == user_asset


def test_validate_user_asset__invalid_no_file_name(enterprise_user):
    @validate_user_asset
    def fn(ua: UserAsset):
        return ua

    user_asset = WalletUserAssetFactory.create(user=enterprise_user)

    user_asset.file_name = None

    with pytest.raises(
        AssertionError,
        match=r"UserAsset ID=.* does not have a file name",
    ):
        fn(user_asset)


def test_validate_user_asset__invalid_no_content_type(enterprise_user):
    @validate_user_asset
    def fn(ua: UserAsset):
        return ua

    user_asset = WalletUserAssetFactory.create(user=enterprise_user)

    user_asset.content_type = None

    with pytest.raises(
        AssertionError,
        match=r"UserAsset ID=.* does not have a content-type",
    ):
        fn(user_asset)


def test_validate_user_asset__invalid_state_not_completed(enterprise_user):
    @validate_user_asset
    def fn(ua: UserAsset):
        return ua

    user_asset = WalletUserAssetFactory.create(user=enterprise_user)

    user_asset.state = UserAssetState.UPLOADING

    with pytest.raises(
        AssertionError,
        match=r"UserAsset ID=.* is not ready to be served",
    ):
        fn(user_asset)


def test_validate_claim__valid(valid_reimbursement_request):
    @validate_claim
    def fn(c: ReimbursementClaim):
        return c

    claim = ReimbursementClaimFactory.create(
        reimbursement_request=valid_reimbursement_request,
        amount=1000,
        alegeus_claim_id="alegeus_claim_id",
    )

    assert fn(claim) == claim


def test_validate_claim__invalid_no_reimbursement_request(valid_reimbursement_request):
    @validate_claim
    def fn(c: ReimbursementClaim):
        return c

    claim = ReimbursementClaimFactory.create(
        amount=1000, alegeus_claim_id="alegeus_claim_id"
    )

    with pytest.raises(
        AssertionError,
        match=r"Claim ID=.* does not have a reimbursement_request",
    ):
        fn(claim)


def test_validate_claim__invalid_no_amount(valid_reimbursement_request):
    @validate_claim
    def fn(c: ReimbursementClaim):
        return c

    claim = ReimbursementClaimFactory.create(
        reimbursement_request=valid_reimbursement_request,
        alegeus_claim_id="alegeus_claim_id",
    )

    with pytest.raises(
        AssertionError,
        match=r"Claim ID=.* does not have an amount",
    ):
        fn(claim)


def test_validate_claim__invalid_no_alegeus_claim_id(valid_reimbursement_request):
    @validate_claim
    def fn(c: ReimbursementClaim):
        return c

    claim = ReimbursementClaimFactory.create(
        reimbursement_request=valid_reimbursement_request, amount=1000
    )

    with pytest.raises(
        AssertionError,
        match=r"Claim ID=.* does not have an alegeus_claim_id",
    ):
        fn(claim)
