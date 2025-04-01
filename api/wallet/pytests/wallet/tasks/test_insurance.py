import datetime
from unittest import mock

import pytest

from wallet.models.constants import (
    AnnualQuestionnaireSyncStatus,
    ReimbursementMethod,
    WalletState,
)
from wallet.models.models import AnnualInsuranceQuestionnaireHDHPData
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    ReimbursementOrgSettingCategoryAssociationFactory,
    ReimbursementPlanFactory,
    ReimbursementRequestCategoryFactory,
    ReimbursementWalletFactory,
)
from wallet.tasks.insurance import COVERAGE_YEAR, process_annual_questionnaire
from wallet.utils.admin_helpers import FlashMessage, FlashMessageCategory


@pytest.fixture(scope="function")
def reimbursement_wallet(enterprise_user) -> ReimbursementWallet:
    wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED,
        reimbursement_organization_settings__allowed_reimbursement_categories=[
            ("fertility", 5000, None),
            ("other", 3000, None),
        ],
        reimbursement_method=ReimbursementMethod.PAYROLL,
    )
    return wallet


@pytest.fixture(scope="function")
def reimbursement_plan(reimbursement_wallet):
    today = datetime.date.today()

    new_category = ReimbursementRequestCategoryFactory.create(
        label="One Request Category"
    )

    plan = ReimbursementPlanFactory.create(
        category=new_category,
        start_date=today - datetime.timedelta(days=4),
        end_date=today - datetime.timedelta(days=2),
    )

    ReimbursementOrgSettingCategoryAssociationFactory.create(
        reimbursement_request_category=new_category,
        reimbursement_organization_settings=reimbursement_wallet.reimbursement_organization_settings,
        reimbursement_request_category_maximum=0,
    )

    return plan


@pytest.mark.parametrize(
    "inp_questionnaire_data, mocked_configure_account_flag, mocked_configure_account_msgs, mocked_reimbursement_plan,"
    "wallet_id_offset, exp_res",
    [
        (
            AnnualInsuranceQuestionnaireHDHPData(True, True),
            True,
            [FlashMessageCategory.SUCCESS],
            "reimbursement_plan",
            0,
            AnnualQuestionnaireSyncStatus.ALEGEUS_SUCCESS,
        ),
        (
            AnnualInsuranceQuestionnaireHDHPData(True, False),
            True,
            [FlashMessageCategory.INFO],
            "reimbursement_plan",
            0,
            AnnualQuestionnaireSyncStatus.ALEGEUS_PRE_EXISTING_ACCOUNT,
        ),
        (
            AnnualInsuranceQuestionnaireHDHPData(False, True),
            True,
            [FlashMessageCategory.WARNING, FlashMessageCategory.SUCCESS],
            "reimbursement_plan",
            0,
            AnnualQuestionnaireSyncStatus.ALEGEUS_SUCCESS,
        ),
        (
            AnnualInsuranceQuestionnaireHDHPData(False, True),
            False,
            [FlashMessageCategory.WARNING, FlashMessageCategory.ERROR],
            "reimbursement_plan",
            0,
            AnnualQuestionnaireSyncStatus.ALEGEUS_FAILURE,
        ),
        (
            AnnualInsuranceQuestionnaireHDHPData(False, True),
            None,  # won't get used
            [],  # won't get used
            None,
            0,
            AnnualQuestionnaireSyncStatus.PLAN_ERROR,
        ),
        (
            AnnualInsuranceQuestionnaireHDHPData(False, True),
            None,  # won't get used
            [],  # won't get used
            None,  # won't get used
            1,
            AnnualQuestionnaireSyncStatus.MISSING_WALLET_ERROR,
        ),
        (
            None,
            None,  # won't get used
            [],  # won't get used
            None,  # won't get used
            0,  # won't get used
            AnnualQuestionnaireSyncStatus.UNKNOWN_ERROR,
        ),
    ],
)
def test_process_annual_questionnaire(
    reimbursement_wallet,
    annual_insurance_questionnaire_response,
    inp_questionnaire_data,
    mocked_configure_account_flag,
    mocked_configure_account_msgs,
    mocked_reimbursement_plan,
    wallet_id_offset,
    exp_res,
    request,
):
    aiq_response = annual_insurance_questionnaire_response(
        wallet_id=reimbursement_wallet.id,
        submitting_user_id=reimbursement_wallet.user_id,
    )
    reimbursement_plan = (
        request.getfixturevalue(mocked_reimbursement_plan)
        if mocked_reimbursement_plan is not None
        else None
    )
    with mock.patch(
        "wallet.tasks.insurance.create_wallet_hdhp_plan",
        return_value=reimbursement_plan,
    ), mock.patch("wallet.alegeus_api.AlegeusApi"), mock.patch(
        "wallet.tasks.insurance.configure_account",
        return_value=(
            mocked_configure_account_flag,
            [FlashMessage("test", m) for m in mocked_configure_account_msgs],
        ),
    ):
        # test legacy
        res_legacy = process_annual_questionnaire(
            reimbursement_wallet.id + wallet_id_offset,
            aiq_response.uuid,
            inp_questionnaire_data,
            COVERAGE_YEAR,
            True,
        )
        assert res_legacy == exp_res
        # test new version
        res_new = process_annual_questionnaire(
            reimbursement_wallet.id + wallet_id_offset,
            aiq_response.uuid,
            inp_questionnaire_data,
            COVERAGE_YEAR,
            False,
        )
        assert res_new == exp_res
