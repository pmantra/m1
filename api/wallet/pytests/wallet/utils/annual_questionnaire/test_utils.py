from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest import mock

import pytest

from wallet.models.constants import AlegeusCoverageTier, QuestionnaireType
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    AnnualInsuranceQuestionnaireResponseFactory,
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementAccountTypeFactory,
    ReimbursementPlanFactory,
    ReimbursementWalletPlanHDHPFactory,
)
from wallet.pytests.wallet.utils.annual_questionnaire.conftest import (
    HDHP_SURVEY_RESPONSE_JSON_BOTH_HDHP,
    HDHP_SURVEY_RESPONSE_JSON_NO_HDHP,
    HDHP_SURVEY_RESPONSE_JSON_ONE_HDHP,
)
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR
from wallet.utils.annual_questionnaire.utils import (
    FdcHdhpCheckResults,
    HDHPCheckResults,
    check_if_hdhp_reimbursement_plan_exists_for_wallet_on_date,
    check_if_is_hdhp,
    check_if_wallet_is_fdc_hdhp,
)


@pytest.mark.parametrize(
    argnames=" direct_payment_enabled, first_dollar_coverage, deductible_accumulation_enabled,"
    "linked_employer_hp_hdhp_status, reimbursement_plan_exists, hdhp_exists_for_org, response, exp",
    argvalues=[
        pytest.param(
            False,
            None,
            None,
            None,
            None,
            None,
            None,
            FdcHdhpCheckResults.FDC_NO,
            id="2. Direct Pay Enabled is false",
        ),
        pytest.param(
            True,
            False,
            None,
            None,
            None,
            None,
            None,
            FdcHdhpCheckResults.FDC_NO,
            id="3. First Dollar coverage is false",
        ),
        pytest.param(
            True,
            True,
            True,
            None,
            None,
            None,
            None,
            FdcHdhpCheckResults.FDC_UNKNOWN,
            id="4. Deductible accumulation is true",
        ),
        pytest.param(
            True,
            True,
            False,
            True,
            None,
            None,
            None,
            FdcHdhpCheckResults.FDC_YES_HDHP_YES,
            id="5. Wallet member health plan is linked to an employer HDHP",
        ),
        pytest.param(
            True,
            True,
            False,
            False,
            True,
            None,
            None,
            FdcHdhpCheckResults.FDC_YES_HDHP_YES,
            id="6.HDHP reimbursement plan exists",
        ),
        pytest.param(
            True,
            True,
            False,
            False,
            False,
            False,
            None,
            FdcHdhpCheckResults.FDC_YES_HDHP_NO,
            id="7.HDHP does not exist for org",
        ),
        pytest.param(
            True,
            True,
            False,
            False,
            False,
            True,
            None,
            FdcHdhpCheckResults.FDC_YES_HDHP_UNKNOWN,
            id="8. No survey response",
        ),
        pytest.param(
            True,
            True,
            False,
            False,
            False,
            True,
            HDHP_SURVEY_RESPONSE_JSON_ONE_HDHP,
            FdcHdhpCheckResults.FDC_YES_HDHP_YES,
            id="9. HDHP yes survey response 1",
        ),
        pytest.param(
            True,
            True,
            False,
            False,
            False,
            True,
            HDHP_SURVEY_RESPONSE_JSON_BOTH_HDHP,
            FdcHdhpCheckResults.FDC_YES_HDHP_YES,
            id="10. HDHP yes survey response 2",
        ),
        pytest.param(
            True,
            True,
            False,
            False,
            False,
            True,
            HDHP_SURVEY_RESPONSE_JSON_NO_HDHP,
            FdcHdhpCheckResults.FDC_YES_HDHP_NO,
            id="11. HDHP no survey response",
        ),
    ],
)
def test_check_if_wallet_is_fdc_hdhp(
    qualified_alegeus_wallet_hra: ReimbursementWallet,
    ff_test_data,
    hdhp_reimbursement_plan,
    create_ehp,
    direct_payment_enabled,
    first_dollar_coverage,
    deductible_accumulation_enabled,
    linked_employer_hp_hdhp_status,
    reimbursement_plan_exists,
    hdhp_exists_for_org,
    response,
    exp,
):
    ff_test_data.update(
        ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
    )
    ros = qualified_alegeus_wallet_hra.reimbursement_organization_settings
    ros.direct_payment_enabled = direct_payment_enabled
    ros.first_dollar_coverage = first_dollar_coverage
    ros.deductible_accumulation_enabled = deductible_accumulation_enabled
    effective_date = date(2024, 10, 10)

    if linked_employer_hp_hdhp_status:
        create_ehp(effective_date, qualified_alegeus_wallet_hra, ros)
    if reimbursement_plan_exists:
        hdhp_reimbursement_plan(
            effective_date.year,
            ros.organization_id,
            qualified_alegeus_wallet_hra.id,
            True,
        )
    if hdhp_exists_for_org:
        hdhp_reimbursement_plan(
            effective_date.year,
            ros.organization_id,
            qualified_alegeus_wallet_hra.id,
            False,
        )

    if response:
        AnnualInsuranceQuestionnaireResponseFactory(
            wallet_id=qualified_alegeus_wallet_hra.id,
            submitting_user_id=qualified_alegeus_wallet_hra.user_id,
            survey_year=effective_date.year,
            user_response_json=response,
            questionnaire_type=QuestionnaireType.DIRECT_PAYMENT_HDHP,
        )

    res = check_if_wallet_is_fdc_hdhp(
        qualified_alegeus_wallet_hra,
        qualified_alegeus_wallet_hra.user_id,
        effective_date,
    )
    assert res == exp


@pytest.mark.parametrize(
    "rx_direct_payment_enabled, deductible_accumulation_enabled, has_health_plan, "
    "health_plan_linked_hdhp_status, wallet_linked_hdhp_status, org_linked_hdhp_status, survey_status, expected",
    [
        pytest.param(
            False, None, None, None, None, None, None, HDHPCheckResults.HDHP_NO
        ),
        pytest.param(
            True, False, None, None, None, None, None, HDHPCheckResults.HDHP_NO
        ),
        pytest.param(
            True, False, True, False, None, None, None, HDHPCheckResults.HDHP_NO
        ),
        pytest.param(
            True, False, True, True, None, None, None, HDHPCheckResults.HDHP_YES
        ),
        pytest.param(
            True, False, False, None, True, None, None, HDHPCheckResults.HDHP_YES
        ),
        pytest.param(
            True, False, False, None, False, False, None, HDHPCheckResults.HDHP_NO
        ),
        pytest.param(
            True,
            False,
            False,
            None,
            False,
            True,
            FdcHdhpCheckResults.FDC_YES_HDHP_YES,
            HDHPCheckResults.HDHP_YES,
        ),
        pytest.param(
            True,
            False,
            False,
            None,
            False,
            True,
            FdcHdhpCheckResults.FDC_YES_HDHP_NO,
            HDHPCheckResults.HDHP_NO,
        ),
        pytest.param(
            True,
            False,
            False,
            None,
            False,
            True,
            FdcHdhpCheckResults.FDC_YES_HDHP_UNKNOWN,
            HDHPCheckResults.HDHP_UNKNOWN,
        ),
    ],
)
def test_check_if_is_hdhp(
    qualified_alegeus_wallet_hra: ReimbursementWallet,
    rx_direct_payment_enabled,
    deductible_accumulation_enabled,
    has_health_plan: bool,
    health_plan_linked_hdhp_status,
    wallet_linked_hdhp_status,
    org_linked_hdhp_status,
    survey_status,
    expected,
    ff_test_data,
):
    ff_test_data.update(
        ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
    )
    org_setting = qualified_alegeus_wallet_hra.reimbursement_organization_settings
    org_setting.direct_payment_enabled = rx_direct_payment_enabled
    org_setting.deductible_accumulation_enabled = deductible_accumulation_enabled
    effective_date = date(2024, 1, 1)

    with mock.patch.multiple(
        "wallet.utils.annual_questionnaire.utils",
        _get_linked_employer_hp_hdhp_status_if_available=mock.MagicMock(
            return_value=health_plan_linked_hdhp_status
        ),
        check_if_hdhp_reimbursement_plan_exists_for_wallet_on_date=mock.MagicMock(
            return_value=wallet_linked_hdhp_status
        ),
        _check_if_hdhp_exists_for_org=mock.MagicMock(
            return_value=org_linked_hdhp_status
        ),
        _parse_response=mock.MagicMock(return_value=survey_status),
    ):
        result = check_if_is_hdhp(
            wallet=qualified_alegeus_wallet_hra,
            user_id=qualified_alegeus_wallet_hra.user_id,
            effective_date=effective_date,
            has_health_plan=has_health_plan,
        )

    assert result == expected


@pytest.mark.parametrize("exp", [True, False])
def test_check_if_hdhp_reimbursement_plan_exists_for_wallet_on_date(
    qualified_alegeus_wallet_hra, hdhp_reimbursement_plan, ff_test_data, exp
):
    ff_test_data.update(
        ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
    )
    ros = qualified_alegeus_wallet_hra.reimbursement_organization_settings
    ros.direct_payment_enabled = False
    ros.first_dollar_coverage = True
    ros.deductible_accumulation_enabled = False
    effective_date = date(2024, 10, 10)

    hdhp_reimbursement_plan(
        effective_date.year,
        ros.organization_id,
        qualified_alegeus_wallet_hra.id,
        exp,
    )
    res = check_if_hdhp_reimbursement_plan_exists_for_wallet_on_date(
        qualified_alegeus_wallet_hra, effective_date
    )
    assert res is exp


@pytest.fixture(scope="function")
def create_ehp():
    def fn(effective_date, qualified_alegeus_wallet_hra, ros):
        ehp = EmployerHealthPlanFactory.create(
            reimbursement_organization_settings=ros,
            reimbursement_org_settings_id=ros.id,
            is_hdhp=True,
        )
        mhp = MemberHealthPlanFactory.create(
            employer_health_plan=ehp,
            reimbursement_wallet__reimbursement_organization_settings=ros,
            plan_start_at=datetime.fromordinal(
                (effective_date - timedelta(days=100)).toordinal()
            ),
            plan_end_at=datetime.fromordinal(
                (effective_date + timedelta(days=265)).toordinal()
            ),
        )
        mhp.reimbursement_wallet_id = qualified_alegeus_wallet_hra.id
        mhp.member_id = qualified_alegeus_wallet_hra.user_id

    return fn


@pytest.fixture(scope="function")
def hdhp_reimbursement_plan():
    def fn(
        year: int,
        organization_id: int,
        wallet_id: int,
        create_wallet_plan: bool,
    ):
        plan = ReimbursementPlanFactory.create(
            reimbursement_account_type=ReimbursementAccountTypeFactory.create(
                alegeus_account_type="DTR"
            ),
            alegeus_plan_id="HDHP",
            start_date=date(year=year, month=1, day=1),
            end_date=date(year=year, month=12, day=31),
            is_hdhp=True,
            organization_id=organization_id,
        )
        if create_wallet_plan:
            _ = ReimbursementWalletPlanHDHPFactory(
                reimbursement_plan_id=plan.id,
                reimbursement_wallet_id=wallet_id,
                alegeus_coverage_tier=AlegeusCoverageTier.SINGLE,
            )

    return fn
