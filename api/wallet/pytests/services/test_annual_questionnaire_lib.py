from __future__ import annotations

import datetime
import json
from unittest import mock

import pytest
import requests

from authn.models.user import User
from wallet.models.annual_insurance_questionnaire_response import (
    AnnualInsuranceQuestionnaireResponse,
)
from wallet.models.constants import (
    AlegeusCoverageTier,
    AnnualQuestionnaireRequestStatus,
    AnnualQuestionnaireSyncStatus,
    QuestionnaireType,
    ReimbursementRequestExpenseTypes,
    WalletState,
)
from wallet.models.reimbursement import ReimbursementWalletPlanHDHP
from wallet.models.reimbursement_wallet import ReimbursementWallet
from wallet.pytests.factories import (
    AnnualInsuranceQuestionnaireResponseFactory,
    EmployerHealthPlanFactory,
    MemberHealthPlanFactory,
    ReimbursementAccountTypeFactory,
    ReimbursementPlanFactory,
    ReimbursementWalletFactory,
    ReimbursementWalletPlanHDHPFactory,
)
from wallet.pytests.services.testdata.annual_questionnaire_data import (
    ANNUAL_INSURANCE_SURVEY_DP_WALLET_SCREENER,
    ANNUAL_INSURANCE_SURVEY_DP_WALLET_SCREENER_OP,
    ANNUAL_INSURANCE_SURVEY_DP_WALLET_SURVEY_JSON,
    ANNUAL_INSURANCE_SURVEY_DP_WALLET_SURVEY_OP,
    ANNUAL_INSURANCE_SURVEY_TRAD_WALLET_HDHP_SURVEY_JSON,
    ANNUAL_INSURANCE_SURVEY_TRAD_WALLET_HDHP_SURVEY_OP,
)
from wallet.repository.health_plan import HEALTH_PLAN_YOY_FLAG, NEW_BEHAVIOR
from wallet.services.annual_questionnaire_lib import (
    STATUS,
    AnnualQuestionnaireCategory,
    create_insurance_questionnaire_dict,
    get_followup_questionnaire_category_and_type,
    handle_insurance_survey_response,
    handle_survey_response_for_hdhp,
    is_any_questionnaire_needed_for_user_and_wallet,
    is_questionnaire_needed_for_user_and_wallet,
)
from wallet.tasks.insurance import process_annual_questionnaire

# Current date in UTC
T = datetime.datetime.now(datetime.timezone.utc).date()

# Date 10 days before the current date
T_MINUS_10 = T - datetime.timedelta(days=10)

# Date 5 days before the current date
T_MINUS_5 = T - datetime.timedelta(days=5)

# Date 5 days after the current date
T_PLUS_5 = T + datetime.timedelta(days=5)

# Date 6 days after the current date
T_PLUS_6 = T + datetime.timedelta(days=5)

# Date 10 days after the current date
T_PLUS_10 = T + datetime.timedelta(days=10)

# Date 100 days after the current date
T_PLUS_100 = T + datetime.timedelta(days=100)

# Date 360 days (slightly lees than 1 year) after the current date
T_PLUS_360 = T + datetime.timedelta(days=360)

# Date 360 days (slightly lees than 1 year) before the current date
T_MINUS_360 = T - datetime.timedelta(days=360)


# Date 370 days after the current date
T_PLUS_370 = T + datetime.timedelta(days=370)

# Date 380 days after the current date
T_PLUS_380 = T + datetime.timedelta(days=380)

# Date 390 days after the current date
T_PLUS_390 = T + datetime.timedelta(days=390)


class TestAnnualQuestionnaireLib:
    @pytest.mark.parametrize(
        "survey_response,survey_year, reimbursement_plan_integration_enabled, questionnaire_type,"
        "create_reimbursement_plan, exp_plan_created, exp_alegeus_coverage_tier",
        [
            pytest.param(
                # survey_response=
                {
                    "id": "1436822963349121913",
                    "answers": {
                        "annual_insurance_survey_trad_wallet_hdhp_survey_self_q": "yes",
                        "annual_insurance_survey_trad_wallet_hdhp_survey_partner_q": "no",
                        "annual_insurance_survey_trad_wallet_hdhp_survey_q_health_pla_thru_employer": "self_only",
                    },
                    "questionnaire_type": "TRADITIONAL_HDHP",
                    "single_questionnaire": None,
                    "plan_year": "2025",
                },
                # survey_year=
                2025,
                # reimbursement_plan_integration_enabled=
                True,
                # questionnaire_type=
                QuestionnaireType.TRADITIONAL_HDHP,
                # create_reimbursement_plan=
                True,
                # exp_plan_created=
                True,
                # exp_alegeus_coverage_tier =
                AlegeusCoverageTier.SINGLE,
                id="1. Plan exists and integration is turned on. Wallet HDHP plan is created for one person.",
            ),
            pytest.param(
                # survey_response=
                {
                    "id": "1436822963349121913",
                    "answers": {
                        "annual_insurance_survey_trad_wallet_hdhp_survey_self_q": "no",
                        "annual_insurance_survey_trad_wallet_hdhp_survey_partner_q": "yes",
                        "annual_insurance_survey_trad_wallet_hdhp_survey_q_health_pla_thru_employer": "self_only",
                    },
                    "questionnaire_type": "TRADITIONAL_HDHP",
                    "single_questionnaire": None,
                    "plan_year": "2025",
                },
                # survey_year=
                2025,
                # reimbursement_plan_integration_enabled=
                True,
                # questionnaire_type=
                QuestionnaireType.TRADITIONAL_HDHP,
                # create_reimbursement_plan=
                True,
                # exp_plan_created=
                True,
                # exp_alegeus_coverage_tier =
                AlegeusCoverageTier.SINGLE,
                id="1.1 Plan exists and integration is turned on. Wallet HDHP plan is created for one person.",
            ),
            pytest.param(
                # survey_response=
                {
                    "id": "1436822963349121913",
                    "answers": {
                        "annual_insurance_survey_trad_wallet_hdhp_survey_self_q": "yes",
                        "annual_insurance_survey_trad_wallet_hdhp_survey_partner_q": "yes",
                        "annual_insurance_survey_trad_wallet_hdhp_survey_q_health_pla_thru_employer": "self_only",
                    },
                    "questionnaire_type": "TRADITIONAL_HDHP",
                    "single_questionnaire": None,
                    "plan_year": "2025",
                },
                # survey_year=
                2025,
                # reimbursement_plan_integration_enabled=
                True,
                # questionnaire_type=
                QuestionnaireType.TRADITIONAL_HDHP,
                # create_reimbursement_plan=
                True,
                # exp_plan_created=
                True,
                # exp_alegeus_coverage_tier =
                AlegeusCoverageTier.FAMILY,
                id="1.2 Plan exists and integration is turned on. Wallet HDHP plan is created for the family.",
            ),
            pytest.param(
                # survey_response=
                {
                    "id": "1436822963349121913",
                    "answers": {
                        "annual_insurance_survey_trad_wallet_hdhp_survey_self_q": "yes",
                        "annual_insurance_survey_trad_wallet_hdhp_survey_partner_q": "no",
                        "annual_insurance_survey_trad_wallet_hdhp_survey_q_health_pla_thru_employer": "both",
                    },
                    "questionnaire_type": "TRADITIONAL_HDHP",
                    "single_questionnaire": None,
                    "plan_year": "2025",
                },
                # survey_year=
                2025,
                # reimbursement_plan_integration_enabled=
                False,
                # questionnaire_type=
                QuestionnaireType.TRADITIONAL_HDHP,
                # create_reimbursement_plan=
                True,
                # exp_plan_created=
                False,
                # exp_alegeus_coverage_tier =
                None,
                id="2. Plan exists and integration is turned off. Wallet HDHP plan is not created",
            ),
            pytest.param(
                # survey_response=
                {
                    "id": "1436822963349121913",
                    "answers": {
                        "annual_insurance_survey_trad_wallet_hdhp_survey_self_q": "yes",
                        "annual_insurance_survey_trad_wallet_hdhp_survey_partner_q": "no",
                        "annual_insurance_survey_trad_wallet_hdhp_survey_q_health_pla_thru_employer": "neither",
                    },
                    "questionnaire_type": "TRADITIONAL_HDHP",
                    "single_questionnaire": None,
                    "plan_year": "2025",
                },
                # survey_year=
                2025,
                # reimbursement_plan_integration_enabled=
                True,
                # questionnaire_type=
                QuestionnaireType.TRADITIONAL_HDHP,
                # create_reimbursement_plan=
                False,
                # exp_plan_created=
                False,
                # exp_alegeus_coverage_tier =
                None,
                id="3. Plan does not exist and integration is turned on. Wallet HDHP plan is not created",
            ),
        ],
    )
    def test_handle_survey_response_new(
        self,
        ff_test_data,
        questionnaire_wallet_user,
        survey_response: dict,
        survey_year: int,
        reimbursement_plan_integration_enabled: bool,
        questionnaire_type: QuestionnaireType,
        create_reimbursement_plan: bool,
        exp_plan_created: bool,
        exp_alegeus_coverage_tier: AlegeusCoverageTier | None,
    ):
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
        )
        reimbursement_plan = None
        if create_reimbursement_plan:
            reimbursement_plan = ReimbursementPlanFactory.create(
                reimbursement_account_type=ReimbursementAccountTypeFactory.create(
                    alegeus_account_type="DTR"
                ),
                alegeus_plan_id="TESTHDHP",
                start_date=datetime.date(2025, 1, 1),
                end_date=datetime.date(2025, 12, 31),
                is_hdhp=True,
                organization_id=questionnaire_wallet_user.wallet.reimbursement_organization_settings.organization_id,
            )

        with mock.patch(
            "wallet.tasks.insurance.process_annual_questionnaire.delay",
            side_effect=process_annual_questionnaire,
        ), mock.patch("wallet.alegeus_api.AlegeusApi"), mock.patch(
            "wallet.tasks.insurance.configure_account"
        ):
            res = handle_survey_response_for_hdhp(
                questionnaire_wallet_user.id,
                questionnaire_wallet_user.wallet,
                survey_response,
                survey_year,
                reimbursement_plan_integration_enabled,
                questionnaire_type,
            )

        assert res == ("Response Accepted.", 200)
        hdhp_wallet_plan = ReimbursementWalletPlanHDHP.query.one_or_none()
        if exp_plan_created:
            # Basic existence checks
            assert hdhp_wallet_plan

            # Wallet Plan validations
            assert (
                hdhp_wallet_plan.reimbursement_wallet_id
                == questionnaire_wallet_user.wallet.id
            )
            assert hdhp_wallet_plan.reimbursement_plan_id == reimbursement_plan.id
            assert hdhp_wallet_plan.alegeus_coverage_tier == exp_alegeus_coverage_tier
        else:
            assert hdhp_wallet_plan is None


class TestExtendedAnnualQuestionnaireLib:
    @pytest.mark.parametrize(  # fmt: off
        [
            "primary_expense_type",
            "wallet_state",
            "get_plan_start_date_called",
            "exp",
        ],
        [
            pytest.param(None, None, False, False, id="No wallet. False expected,"),
            pytest.param(
                ReimbursementRequestExpenseTypes.CHILDCARE,
                WalletState.QUALIFIED,
                False,
                False,
                id="Non-fertility primary expense type on wallet. False expected,",
            ),
            pytest.param(
                ReimbursementRequestExpenseTypes.FERTILITY,
                WalletState.PENDING,
                False,
                False,
                id="Pending wallet. False expected,",
            ),
            pytest.param(
                ReimbursementRequestExpenseTypes.FERTILITY,
                WalletState.QUALIFIED,
                True,
                True,
                id="Fertility qualified wallet. True expected",
            ),
            pytest.param(
                ReimbursementRequestExpenseTypes.FERTILITY,
                WalletState.RUNOUT,
                True,
                True,
                id="Fertility runout wallet. True expected",
            ),
        ],
    )
    def test_is_questionnaire_needed_for_user_and_wallet(
        self,
        primary_expense_type,
        wallet_state,
        get_plan_start_date_called,
        exp,
    ):
        test_wallet: ReimbursementWallet = ReimbursementWalletFactory.create(
            state=wallet_state
        )
        test_wallet.primary_expense_type = primary_expense_type
        with mock.patch(
            "wallet.services.annual_questionnaire_lib._get_plan_start_date",
            return_value=T,
        ) as mock_get_get_plan_start_date, mock.patch(
            "wallet.services.annual_questionnaire_lib.has_survey_been_taken",
            return_value=False,
        ) as mockhas_survey_been_taken:
            res = is_questionnaire_needed_for_user_and_wallet(
                wallet=test_wallet, user=User.query.get(test_wallet.user_id)
            )
            assert res == exp
            # check that downstream is not called in case the expense type check failed
            assert mock_get_get_plan_start_date.called == get_plan_start_date_called
            assert mockhas_survey_been_taken.called == exp

    @pytest.mark.parametrize(
        argnames="plan_dates, create_user_resp, mhp_dates, exp",
        argvalues=[
            # fmt: off
            ([(T_MINUS_10, T_MINUS_5)], False, None, False),
            ([(T_PLUS_5, T_PLUS_10)], False, None, False),
            ([(T_MINUS_10, T_PLUS_10)], False, None, True),
            ([(T_MINUS_10, T_PLUS_10), (T_MINUS_10, T_PLUS_10)], False, None, True),
            ([(T_MINUS_5, T_PLUS_10), (T_MINUS_10, T_PLUS_10)], False, None, True),
            ([(T_MINUS_10, T_MINUS_5)], True, None, False),
            ([(T_PLUS_5, T_PLUS_10)], True, None, False),
            ([(T_MINUS_10, T_PLUS_10)], True, None, False),
            ([(T_MINUS_10, T_PLUS_10)], False, [(T_MINUS_10, T_PLUS_10)], False),
            ([(T_MINUS_10, T_PLUS_10)], False, [(T_PLUS_380, T_PLUS_390)], True),
            # fmt: on
        ],
        ids=[
            "1_test_no_questionnaire_needed_past_plan_direct_payment",
            "2_test_no_questionnaire_needed_future_plan_direct_payment",
            "3_test_questionnaire_needed_current_plan_direct_payment",
            "4_test_questionnaire_needed_overlapping_current_plans_direct_payment",
            "5_test_questionnaire_needed_overlapping_current_plans_different_order_direct_payment",
            "6_test_no_questionnaire_needed_past_plan_existing_response_direct_payment",
            "7_test_no_questionnaire_needed_future_plan_existing_response_direct_payment",
            "8_test_no_questionnaire_needed_current_plan_existing_response_direct_payment",
            "9_test_no_questionnaire_needed_current_plan_existing_member_plan_direct_payment",
            "10_test_questionnaire_needed_current_plan_future_member_plan_direct_payment",
        ],
    )
    def test_is_questionnaire_needed_for_dp_wallet_plan_year(
        self,
        ff_test_data,
        plan_dates,
        create_user_resp,
        mhp_dates,
        exp,
    ):
        test_wallet: ReimbursementWallet = ReimbursementWalletFactory.create(
            state=WalletState.QUALIFIED
        )
        test_ros = test_wallet.reimbursement_organization_settings
        test_ros.direct_payment_enabled = True
        test_ros.deductible_accumulation_enabled = True
        test_ros.first_dollar_coverage = False
        test_wallet.primary_expense_type = ReimbursementRequestExpenseTypes.FERTILITY
        for plan_date in plan_dates:
            start_date = plan_date[0]
            end_date = plan_date[1]
            _ = EmployerHealthPlanFactory(
                reimbursement_organization_settings=test_ros,
                start_date=start_date,
                end_date=end_date,
            )
            if mhp_dates:
                _ = MemberHealthPlanFactory.create(
                    member_id=test_wallet.user_id,
                    reimbursement_wallet=test_wallet,
                    plan_start_at=datetime.datetime.fromordinal(
                        mhp_dates[0][0].toordinal()
                    ),
                    plan_end_at=datetime.datetime.fromordinal(
                        mhp_dates[0][1].toordinal()
                    ),
                )
        if create_user_resp:
            first_start_date = plan_dates[0][0]
            _ = AnnualInsuranceQuestionnaireResponseFactory(
                wallet_id=test_wallet.id,
                submitting_user_id=test_wallet.user_id,
                survey_year=first_start_date.year,
            )
        # only really interested in the new behavior
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
        )

        res = is_questionnaire_needed_for_user_and_wallet(
            wallet=test_wallet, user=User.query.get(test_wallet.user_id)
        )
        assert res == exp

    @pytest.mark.parametrize(
        argnames=" plan_dates_and_member_plan, create_user_resp, exp",
        argvalues=[
            # fmt: off
            ([(T_MINUS_10, T_MINUS_5, False)], False,   False),
            ([(T_PLUS_5, T_PLUS_10, False)], False, False),
            ([(T_MINUS_10, T_PLUS_10, False)], False, True),
            ([(T_MINUS_10, T_PLUS_10, False), (T_MINUS_5, T_PLUS_10, False)], False, True),
            ([(T_MINUS_10, T_PLUS_10, False), (T_PLUS_5, T_PLUS_10, False)], False, True),
            ([(T_MINUS_10, T_MINUS_5, False)], True, False),
            ([(T_PLUS_5, T_PLUS_10, False)], True, False),
            ([(T_MINUS_10, T_PLUS_10, False)], True, False),
            ([(T_MINUS_10, T_PLUS_10, True)], False, False),
            ([(T_MINUS_10, T_PLUS_10, True), (T_PLUS_5, T_PLUS_10, False)], False, False),
            # fmt: on
        ],
        ids=[
            "01_test_no_questionnaire_needed_past_plan",
            "02_test_no_questionnaire_needed_future_plan",
            "03_test_questionnaire_needed_current_plan",
            "04_test_questionnaire_needed_overlapping_current_plans",
            "05_test_questionnaire_needed_current_and_future_plans",
            "06_test_no_questionnaire_needed_past_plan_existing_response",
            "07_test_no_questionnaire_needed_future_plan_existing_response",
            "08_test_no_questionnaire_needed_current_plan_existing_response",
            "09_test_no_questionnaire_needed_current_plan_no_response_existing_hdhp_wallet_plan",
            "10_test_no_questionnaire_needed_current_plan_multi_plan__no_response_existing_hdhp_wallet_plan",
        ],
    )
    def test_is_questionnaire_needed_for_trad_wallet_plan_year_trad(
        self,
        ff_test_data,
        plan_dates_and_member_plan,
        create_user_resp,
        exp,
    ):
        test_wallet: ReimbursementWallet = ReimbursementWalletFactory.create(
            state=WalletState.QUALIFIED
        )
        test_ros = test_wallet.reimbursement_organization_settings
        test_ros.direct_payment_enabled = False
        test_ros.deductible_accumulation_enabled = False
        test_ros.first_dollar_coverage = True
        test_wallet.primary_expense_type = ReimbursementRequestExpenseTypes.FERTILITY
        for plan_date in plan_dates_and_member_plan:
            start_date = plan_date[0]
            end_date = plan_date[1]
            create_wallet_hdhp_plan = plan_date[2]
            rp = ReimbursementPlanFactory(
                organization_id=test_ros.organization_id,
                start_date=start_date,
                end_date=end_date,
                is_hdhp=True,
            )
            if create_wallet_hdhp_plan:
                ReimbursementWalletPlanHDHPFactory(
                    reimbursement_plan_id=rp.id,
                    reimbursement_wallet_id=test_wallet.id,
                    alegeus_coverage_tier=AlegeusCoverageTier.SINGLE,
                )

        if create_user_resp:
            first_start_date = plan_dates_and_member_plan[0][0]
            _ = AnnualInsuranceQuestionnaireResponseFactory(
                wallet_id=test_wallet.id,
                submitting_user_id=test_wallet.user_id,
                survey_year=first_start_date.year,
            )
        # only really interested in the new behavior
        ff_test_data.update(
            ff_test_data.flag(HEALTH_PLAN_YOY_FLAG).variations(NEW_BEHAVIOR)
        )

        res = is_questionnaire_needed_for_user_and_wallet(
            wallet=test_wallet, user=User.query.get(test_wallet.user_id)
        )
        assert res == exp

    @pytest.mark.parametrize(
        "primary_expense_type,  exp",
        [
            (None, False),
            (ReimbursementRequestExpenseTypes.CHILDCARE, False),
            (ReimbursementRequestExpenseTypes.FERTILITY, True),
        ],
    )
    def test_is_any_questionnaire_needed_for_wallet_primary_expense_type(
        self, primary_expense_type, exp
    ):
        test_wallet: ReimbursementWallet = ReimbursementWalletFactory.create(
            state=WalletState.QUALIFIED
        )
        test_wallet.primary_expense_type = primary_expense_type
        with mock.patch(
            "wallet.services.annual_questionnaire_lib._get_plan_start_date",
            return_value=T,
        ) as mock_get_plan_year, mock.patch(
            "wallet.services.annual_questionnaire_lib.has_survey_been_taken",
            return_value=False,
        ) as mock_has_survey_been_taken:
            res = is_any_questionnaire_needed_for_user_and_wallet(
                wallet=test_wallet, user=User.query.get(test_wallet.user_id)
            )
            assert res == exp
            # check that downstream is not called in case the expense type check failed
            assert mock_get_plan_year.called == exp
            assert mock_has_survey_been_taken.called == exp

    @pytest.mark.parametrize(
        argnames="use_dp_flow, plan_dates, create_user_resp, exp",
        argvalues=[
            (False, [(T_MINUS_10, T_MINUS_5)], False, False),
            (False, [(T_PLUS_5, T_PLUS_10)], False, False),
            (False, [(T_PLUS_5, T_PLUS_100), (T_PLUS_360, T_PLUS_370)], False, True),
            (False, [(T_MINUS_10, T_PLUS_10)], False, True),
            (False, [(T_PLUS_10, T_PLUS_370)], False, True),
            (False, [(T_PLUS_380, T_PLUS_390)], False, False),
            (False, [(T_MINUS_10, T_PLUS_10), (T_MINUS_5, T_PLUS_10)], False, True),
            (False, [(T_MINUS_10, T_PLUS_10), (T_PLUS_5, T_PLUS_10)], False, True),
            (False, [(T_MINUS_10, T_MINUS_5)], True, False),
            (False, [(T_PLUS_5, T_PLUS_10)], True, False),
            (False, [(T_MINUS_10, T_PLUS_10)], True, False),
            (True, [(T_MINUS_10, T_MINUS_5)], False, False),
            (True, [(T_PLUS_5, T_PLUS_10)], False, False),
            (False, [(T_PLUS_5, T_PLUS_100), (T_PLUS_360, T_PLUS_370)], False, True),
            (True, [(T_PLUS_380, T_PLUS_390)], False, False),
            (True, [(T_MINUS_10, T_PLUS_10)], False, True),
            (True, [(T_MINUS_10, T_PLUS_10), (T_MINUS_10, T_PLUS_10)], False, True),
            (True, [(T_MINUS_5, T_PLUS_10), (T_MINUS_10, T_PLUS_10)], False, True),
            (True, [(T_MINUS_10, T_MINUS_5)], True, False),
            (True, [(T_PLUS_5, T_PLUS_10)], True, False),
            (True, [(T_MINUS_10, T_PLUS_10)], True, False),
        ],
        ids=[
            "01. test_no_questionnaire_needed_past_plan_no_direct_payment",
            "02. test_no_questionnaire_needed_future_plan_no_direct_payment",
            "03. test_questionnaire_needed_future_plans_no_direct_payment",
            "04. test_questionnaire_needed_current_plan_no_direct_payment",
            "05. test_questionnaire_needed_far_future_plan_no_direct_payment",
            "06. test_no_questionnaire_needed_very_far_future_plan_no_direct_payment",
            "07. test_questionnaire_needed_overlapping_current_plans_no_direct_payment",
            "08. test_questionnaire_needed_current_and_future_plans_no_direct_payment",
            "09. test_no_questionnaire_needed_past_plan_existing_response_no_direct_payment",
            "10. test_no_questionnaire_needed_future_plan_existing_response_no_direct_payment",
            "11. test_no_questionnaire_needed_current_plan_existing_response_no_direct_payment",
            "12. test_no_questionnaire_needed_past_plan_direct_payment",
            "13. test_no_questionnaire_needed_future_plan_direct_payment",
            "14. test_questionnaire_needed_future_plans_no_direct_payment_duplicate",
            "16. test_no_questionnaire_needed_very_far_future_plan_direct_payment",
            "17. test_questionnaire_needed_current_plan_direct_payment",
            "18. test_questionnaire_needed_overlapping_current_plans_direct_payment",
            "19. test_questionnaire_needed_overlapping_current_plans_different_order_direct_payment",
            "20. test_no_questionnaire_needed_past_plan_existing_response_direct_payment",
            "21. test_no_questionnaire_needed_future_plan_existing_response_direct_payment",
            "22. test_no_questionnaire_needed_current_plan_existing_response_direct_payment",
        ],
    )
    def test_is_any_questionnaire_needed_for_wallet_plan_year(
        self, use_dp_flow, plan_dates, create_user_resp, exp
    ):
        test_wallet: ReimbursementWallet = ReimbursementWalletFactory.create(
            state=WalletState.QUALIFIED
        )
        test_ros = test_wallet.reimbursement_organization_settings
        test_ros.direct_payment_enabled = use_dp_flow
        test_ros.deductible_accumulation_enabled = use_dp_flow
        test_ros.first_dollar_coverage = not use_dp_flow

        test_wallet.primary_expense_type = ReimbursementRequestExpenseTypes.FERTILITY
        for plan_date in plan_dates:
            start_date = plan_date[0]
            end_date = plan_date[1]
            if use_dp_flow:
                _ = EmployerHealthPlanFactory(
                    reimbursement_organization_settings=test_ros,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                _ = ReimbursementPlanFactory(
                    organization_id=test_ros.organization_id,
                    start_date=start_date,
                    end_date=end_date,
                    is_hdhp=True,
                )
        if create_user_resp:
            first_start_date = plan_dates[0][0]
            _ = AnnualInsuranceQuestionnaireResponseFactory(
                wallet_id=test_wallet.id,
                submitting_user_id=test_wallet.user_id,
                survey_year=first_start_date.year,
            )

        res = is_any_questionnaire_needed_for_user_and_wallet(
            wallet=test_wallet, user=User.query.get(test_wallet.user_id)
        )
        assert res == exp

    @pytest.mark.parametrize(
        [
            "use_dp_flow",
            "plans_info",
            "create_user_resp",
            "input_plan_year",
            "input_previous_type",
            "mocked_contentful_json",
            "enrichment",
            "exp",
        ],
        [
            pytest.param(
                False,
                [(T_MINUS_10, T_MINUS_5)],
                False,
                None,
                None,
                None,
                None,
                {STATUS: AnnualQuestionnaireRequestStatus.NOT_REQUIRED.value},
                id="Trad. Survey not required. No current or future plans available.",
            ),
            pytest.param(
                True,
                [(T_MINUS_10, T_MINUS_5, 1101, "Test Plan Name")],
                False,
                None,
                None,
                None,
                None,
                {STATUS: AnnualQuestionnaireRequestStatus.NOT_REQUIRED.value},
                id="DP. Survey not required. No current or future plans available.",
            ),
            pytest.param(
                False,
                [(T_PLUS_370, T_PLUS_380)],
                False,
                None,
                None,
                None,
                None,
                {STATUS: AnnualQuestionnaireRequestStatus.NOT_REQUIRED.value},
                id="Trad. Survey not required. Plan too far in the future.",
            ),
            pytest.param(
                True,
                [(T_PLUS_370, T_PLUS_380, 1101, "Test Plan Name")],
                False,
                None,
                None,
                None,
                None,
                {STATUS: AnnualQuestionnaireRequestStatus.NOT_REQUIRED.value},
                id="DP. Survey not required. Plan too far in the future.",
            ),
            pytest.param(
                False,
                [(T_PLUS_370, T_PLUS_380)],
                False,
                str(T.year),
                None,
                None,
                None,
                {STATUS: AnnualQuestionnaireRequestStatus.NOT_REQUIRED.value},
                id="Trad with plan year. Survey not required. Plan too far in the future.",
            ),
            pytest.param(
                True,
                [(T_PLUS_370, T_PLUS_380, 1101, "Test Plan Name")],
                False,
                str(T.year),
                None,
                None,
                None,
                {STATUS: AnnualQuestionnaireRequestStatus.NOT_REQUIRED.value},
                id="DP with plan year. Survey not required. Plan too far in the future.",
            ),
            pytest.param(
                False,
                [],
                True,
                str(T.year),
                None,
                None,
                None,
                {STATUS: AnnualQuestionnaireRequestStatus.COMPLETED.value},
                id="Trad with plan year.Survey not required. Response already logged.",
            ),
            pytest.param(
                True,
                [],
                True,
                str(T.year),
                None,
                None,
                None,
                {STATUS: AnnualQuestionnaireRequestStatus.COMPLETED.value},
                id="DP with plan year. Survey not required. Response already logged.",
            ),
            pytest.param(
                False,
                [(T, T_PLUS_10)],
                False,
                str(T.year),
                None,
                ANNUAL_INSURANCE_SURVEY_TRAD_WALLET_HDHP_SURVEY_JSON,
                {
                    "subtext": f"Plan start date: {T.strftime('%m/%d/%Y')}",
                    "plan_year": str(T.year),
                    "questionnaire_type": QuestionnaireType.TRADITIONAL_HDHP.value,
                },
                ANNUAL_INSURANCE_SURVEY_TRAD_WALLET_HDHP_SURVEY_OP,
                id="Trad with plan year. Survey required.",
            ),
            pytest.param(
                True,
                [(T, T_PLUS_10, 1101, "Test Plan Name")],
                False,
                str(T.year),
                None,
                ANNUAL_INSURANCE_SURVEY_DP_WALLET_SCREENER,
                {
                    "subtext": f"Plan start date: {T.strftime('%m/%d/%Y')}",
                    "plan_year": str(T.year),
                    "questionnaire_type": QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER.value,
                },
                ANNUAL_INSURANCE_SURVEY_DP_WALLET_SCREENER_OP,
                id="DP with plan year. Screener Survey required.",
            ),
            pytest.param(
                False,
                [(T_PLUS_5, T_PLUS_100)],
                False,
                None,
                None,
                ANNUAL_INSURANCE_SURVEY_TRAD_WALLET_HDHP_SURVEY_JSON,
                {
                    "subtext": f"Plan start date: {T_PLUS_5.strftime('%m/%d/%Y')}",
                    "plan_year": str(T_PLUS_5.year),
                    "questionnaire_type": QuestionnaireType.TRADITIONAL_HDHP.value,
                },
                ANNUAL_INSURANCE_SURVEY_TRAD_WALLET_HDHP_SURVEY_OP,
                id="Trad with no plan year. Survey required.",
            ),
            pytest.param(
                True,
                [(T_PLUS_5, T_PLUS_100, 1101, "Test Plan Name")],
                False,
                None,
                None,
                ANNUAL_INSURANCE_SURVEY_DP_WALLET_SCREENER,
                {
                    "subtext": f"Plan start date: {T_PLUS_5.strftime('%m/%d/%Y')}",
                    "plan_year": str(T_PLUS_5.year),
                    "questionnaire_type": QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER.value,
                },
                ANNUAL_INSURANCE_SURVEY_DP_WALLET_SCREENER_OP,
                id="DP with no plan year. Survey required.",
            ),
            pytest.param(
                True,
                [(T, T_PLUS_10, 1101, "Test Plan Name")],
                False,
                str(T.year),
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
                ANNUAL_INSURANCE_SURVEY_DP_WALLET_SURVEY_JSON,
                {
                    "subtext": f"Plan start date: {T.strftime('%m/%d/%Y')}",
                    "plan_year": str(T.year),
                    "questionnaire_type": QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE.value,
                },
                ANNUAL_INSURANCE_SURVEY_DP_WALLET_SURVEY_OP,
                id="DP with plan year. Survey required.",
            ),
            pytest.param(
                True,
                [(T, T_PLUS_10, 1101, "Test Plan Name")],
                False,
                None,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
                ANNUAL_INSURANCE_SURVEY_DP_WALLET_SURVEY_JSON,
                {
                    "subtext": f"Plan start date: {T.strftime('%m/%d/%Y')}",
                    "plan_year": str(T.year),
                    "questionnaire_type": QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE.value,
                },
                ANNUAL_INSURANCE_SURVEY_DP_WALLET_SURVEY_OP,
                id="DP with no plan year. Survey required.",
            ),
        ],
    )
    def test_create_insurance_questionnaire_dict(
        self,
        mock_hdc_response,
        use_dp_flow,
        plans_info,
        create_user_resp,
        input_plan_year: str,
        input_previous_type: QuestionnaireType,
        mocked_contentful_json,
        enrichment,
        exp: dict,
    ):
        test_wallet: ReimbursementWallet = ReimbursementWalletFactory.create(
            state=WalletState.QUALIFIED
        )
        test_ros = test_wallet.reimbursement_organization_settings
        test_ros.direct_payment_enabled = use_dp_flow
        test_ros.deductible_accumulation_enabled = use_dp_flow
        test_ros.first_dollar_coverage = not use_dp_flow
        test_wallet.primary_expense_type = ReimbursementRequestExpenseTypes.FERTILITY
        for plan_info in plans_info:
            start_date = plan_info[0]
            end_date = plan_info[1]
            if use_dp_flow:
                _ = EmployerHealthPlanFactory(
                    id=plan_info[2],
                    name=plan_info[3],
                    reimbursement_organization_settings=test_ros,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                _ = ReimbursementPlanFactory(
                    organization_id=test_ros.organization_id,
                    start_date=start_date,
                    end_date=end_date,
                    is_hdhp=True,
                )
        if create_user_resp:
            _ = AnnualInsuranceQuestionnaireResponseFactory(
                wallet_id=test_wallet.id,
                submitting_user_id=test_wallet.user_id,
                survey_year=int(input_plan_year),
            )

        with mock.patch(
            "wallet.services.annual_questionnaire_lib.make_hdc_request",
            return_value=mock_hdc_response(mocked_contentful_json),
        ) as mocked_make_hdc_request:
            res = create_insurance_questionnaire_dict(
                wallet=test_wallet,
                user=User.query.get(test_wallet.user_id),
                input_plan_year=input_plan_year,
                previous_type=input_previous_type,
            )
        if enrichment:
            exp["questionnaire"].update(enrichment)
        assert res == exp
        assert mocked_make_hdc_request.called == bool(mocked_contentful_json)

    @pytest.mark.skip(reason="test is currently broken because of EOY issues.")
    @pytest.mark.parametrize(
        [
            "use_dp_flow",
            "plans_info",
            "create_user_resp",
            "input_plan_year",
            "input_survey_response",
            "mocked_contentful_json",
            "enrichment",
            "exp",
            "exp_persisted_response",
        ],
        [
            pytest.param(
                True,
                [(T, T_PLUS_10, 1101, "Test Plan Name")],
                False,
                None,
                {
                    "answers": {
                        "annual_insurance_form_dp_wallet_screener_branching": "yes"
                    },
                    "questionnaire_type": "DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER",
                    "plan_year": str(T_PLUS_5.year),
                },
                ANNUAL_INSURANCE_SURVEY_DP_WALLET_SURVEY_JSON,
                {
                    "subtext": f"Plan start date: {T.strftime('%m/%d/%Y')}",
                    "plan_year": str(T.year),
                    "questionnaire_type": QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE.value,
                },
                (
                    ANNUAL_INSURANCE_SURVEY_DP_WALLET_SURVEY_OP,
                    201,
                ),
                None,
                id="Survey required for current plan year",
            ),
            pytest.param(
                True,
                [(T_PLUS_5, T_PLUS_100, 1101, "Test Plan Name")],
                False,
                None,
                {
                    "answers": {
                        "annual_insurance_form_dp_wallet_screener_branching": "yes"
                    },
                    "questionnaire_type": "DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER",
                    "plan_year": str(T_PLUS_5.year),
                },
                ANNUAL_INSURANCE_SURVEY_DP_WALLET_SURVEY_JSON,
                {
                    "subtext": f"Plan start date: {T_PLUS_5.strftime('%m/%d/%Y')}",
                    "plan_year": str(T_PLUS_5.year),
                    "questionnaire_type": QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE.value,
                },
                (
                    ANNUAL_INSURANCE_SURVEY_DP_WALLET_SURVEY_OP,
                    201,
                ),
                None,
                id="Survey required for future plan year",
            ),
            pytest.param(
                True,
                [(T_PLUS_5, T_PLUS_100, 1101, "Test Plan Name")],
                True,
                str(T_PLUS_5.year),
                {
                    "answers": {
                        "annual_insurance_form_dp_wallet_screener_branching": "yes"
                    },
                    "questionnaire_type": "DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER",
                    "plan_year": str(T_PLUS_5.year),
                },
                None,
                None,
                (
                    "Accepted previous questionnaire.User has already completed the follow up questionnaire.",
                    200,
                ),
                None,
                id="Survey not needed",
            ),
            pytest.param(
                True,
                [(T_PLUS_5, T_PLUS_100, 1101, "Test Plan Name")],
                False,
                None,
                {
                    "answers": {
                        "annual_insurance_form_dp_wallet_screener_branching": "no"
                    },
                    "questionnaire_type": "DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER",
                    "plan_year": str(T_PLUS_5.year),
                },
                None,
                None,
                (
                    "Accepted previous questionnaire. User does not need to complete the follow up questionnaire.",
                    200,
                ),
                AnnualQuestionnaireSyncStatus.MEMBER_HEALTH_PLAN_NOT_NEEDED,
                id="Survey not required. User responded no to screener. No plan for follow up year.",
            ),
            pytest.param(
                True,
                [
                    (T_MINUS_360, T_PLUS_5, 1101, "Test Plan Name"),
                    (T_PLUS_6, T_PLUS_100, 1102, "Test Plan Name 2"),
                ],
                False,
                None,
                {
                    "answers": {"Implemented": "no"},
                    "questionnaire_type": "DIRECT_PAYMENT_HEALTH_INSURANCE",
                    "plan_year": str(T_MINUS_360.year),
                },
                ANNUAL_INSURANCE_SURVEY_DP_WALLET_SCREENER,
                {
                    "subtext": f"Plan start date: {T_PLUS_6.strftime('%m/%d/%Y')}",
                    "plan_year": str(T_PLUS_6.year),
                    "questionnaire_type": QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER.value,
                },
                (
                    ANNUAL_INSURANCE_SURVEY_DP_WALLET_SCREENER_OP,
                    201,
                ),
                AnnualQuestionnaireSyncStatus.RESPONSE_RECORDED,
                id="Follow up to current year. Next years survey screener needed.",
            ),
            pytest.param(
                True,
                [
                    (T_MINUS_360, T_PLUS_5, 1101, "Test Plan Name"),
                    (T_PLUS_6, T_PLUS_100, 1102, "Test Plan Name 2"),
                ],
                False,
                None,
                {
                    "answers": {
                        "annual_insurance_form_dp_wallet_screener_branching": "no"
                    },
                    "questionnaire_type": "DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER",
                    "plan_year": str(T_MINUS_360.year),
                },
                ANNUAL_INSURANCE_SURVEY_DP_WALLET_SCREENER,
                {
                    "subtext": f"Plan start date: {T_PLUS_6.strftime('%m/%d/%Y')}",
                    "plan_year": str(T_PLUS_6.year),
                    "questionnaire_type": QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER.value,
                },
                (
                    ANNUAL_INSURANCE_SURVEY_DP_WALLET_SCREENER_OP,
                    201,
                ),
                AnnualQuestionnaireSyncStatus.MEMBER_HEALTH_PLAN_NOT_NEEDED,
                id="Follow up screener needed. User responded no to current year screener. Following year plan exists.",
            ),
        ],
    )
    def test_handle_insurance_survey_response(
        self,
        mock_hdc_response,
        use_dp_flow,
        plans_info,
        create_user_resp,
        input_plan_year: str,
        input_survey_response: dict,
        mocked_contentful_json,
        enrichment,
        exp: tuple,
        exp_persisted_response: AnnualQuestionnaireSyncStatus,
    ):
        test_wallet: ReimbursementWallet = ReimbursementWalletFactory.create(
            state=WalletState.QUALIFIED
        )
        test_ros = test_wallet.reimbursement_organization_settings
        test_ros.direct_payment_enabled = use_dp_flow
        test_ros.deductible_accumulation_enabled = use_dp_flow
        test_ros.first_dollar_coverage = not use_dp_flow
        test_wallet.primary_expense_type = ReimbursementRequestExpenseTypes.FERTILITY
        for plan_info in plans_info:
            start_date = plan_info[0]
            end_date = plan_info[1]
            if use_dp_flow:
                _ = EmployerHealthPlanFactory(
                    id=plan_info[2],
                    name=plan_info[3],
                    reimbursement_organization_settings=test_wallet.reimbursement_organization_settings,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                _ = ReimbursementPlanFactory(
                    organization_id=test_wallet.reimbursement_organization_settings.organization_id,
                    start_date=start_date,
                    end_date=end_date,
                    is_hdhp=True,
                )
        if create_user_resp:
            _ = AnnualInsuranceQuestionnaireResponseFactory(
                wallet_id=test_wallet.id,
                submitting_user_id=test_wallet.user_id,
                survey_year=int(input_plan_year),
            )

        survey_response = {"id": f"{test_wallet.id}"}
        survey_response.update(input_survey_response)

        with mock.patch(
            "wallet.services.annual_questionnaire_lib.make_hdc_request",
            return_value=mock_hdc_response(mocked_contentful_json),
        ) as mocked_make_hdc_request:
            res = handle_insurance_survey_response(
                wallet=test_wallet,
                user=User.query.get(test_wallet.user_id),
                survey_response=survey_response,
            )
        if enrichment:
            exp[0]["questionnaire"].update(enrichment)
        assert res == exp
        assert mocked_make_hdc_request.called == bool(mocked_contentful_json)
        res_resp = AnnualInsuranceQuestionnaireResponse.query.all()
        if res_resp:
            assert res_resp[0].sync_status == exp_persisted_response
        else:
            assert exp_persisted_response is None

    @pytest.mark.parametrize(
        "direct_payment_enabled, deductible_accumulation_enabled, first_dollar_coverage, inp_org_id, inp_previous_type, "
        "expected_category, expected_type",
        [
            pytest.param(
                True,
                True,
                True,
                133,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
                AnnualQuestionnaireCategory.DP_WALLET_SURVEY_AMAZON,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE,
                id="amazon_org_from_screener",
            ),
            pytest.param(
                True,
                True,
                True,
                867,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
                AnnualQuestionnaireCategory.DP_WALLET_SURVEY_OHIO,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE,
                id="ohio_org_from_screener",
            ),
            pytest.param(
                True,
                True,
                True,
                9999,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
                AnnualQuestionnaireCategory.DP_WALLET_SURVEY,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE,
                id="default_org_from_screener",
            ),
            pytest.param(
                True,
                True,
                True,
                2441,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE,
                AnnualQuestionnaireCategory.DP_WALLET_SCREENER,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
                id="amazon_org_from_insurance_form",
            ),
            pytest.param(
                True,
                True,
                True,
                9999,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE,
                AnnualQuestionnaireCategory.DP_WALLET_SCREENER,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
                id="default_org_from_insurance_form",
            ),
            pytest.param(
                True,
                True,
                True,
                2441,
                None,
                AnnualQuestionnaireCategory.DP_WALLET_SCREENER,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
                id="amazon_org_no_previous_type",
            ),
            pytest.param(
                True,
                True,
                True,
                9999,
                None,
                AnnualQuestionnaireCategory.DP_WALLET_SCREENER,
                QuestionnaireType.DIRECT_PAYMENT_HEALTH_INSURANCE_SCREENER,
                id="default_org_no_previous_type",
            ),
            pytest.param(
                False,
                True,
                False,
                9999,
                QuestionnaireType.TRADITIONAL_HDHP,
                AnnualQuestionnaireCategory.TRAD_WALLET_HDHP_SURVEY,
                QuestionnaireType.TRADITIONAL_HDHP,
                id="dp_disabled_traditional_hdhp",
            ),
            pytest.param(
                True,
                False,
                False,
                9999,
                None,
                AnnualQuestionnaireCategory.TRAD_WALLET_HDHP_SURVEY,
                QuestionnaireType.DIRECT_PAYMENT_HDHP,
                id="dp_enabled_da_disabled_fdc_disabled_direct_payment_hdhp",
            ),
            pytest.param(
                True,
                False,
                True,
                9999,
                None,
                AnnualQuestionnaireCategory.TRAD_WALLET_HDHP_SURVEY,
                QuestionnaireType.DIRECT_PAYMENT_HDHP,
                id="dp_enabled_da_disabled_fdc_enabled_direct_payment_hdhp",
            ),
        ],
    )
    def test_get_followup_questionnaire_category_and_type(
        self,
        direct_payment_enabled,
        deductible_accumulation_enabled,
        first_dollar_coverage,
        inp_org_id,
        inp_previous_type: QuestionnaireType,
        expected_category,
        expected_type,
    ):
        test_wallet: ReimbursementWallet = ReimbursementWalletFactory.create(
            state=WalletState.QUALIFIED
        )
        test_ros = test_wallet.reimbursement_organization_settings
        test_ros.direct_payment_enabled = direct_payment_enabled
        test_ros.deductible_accumulation_enabled = deductible_accumulation_enabled
        test_ros.first_dollar_coverage = not first_dollar_coverage
        test_wallet.reimbursement_organization_settings.organization_id = inp_org_id
        # Act
        category, type_ = get_followup_questionnaire_category_and_type(
            wallet=test_wallet,
            previous_type=inp_previous_type,
        )

        # Assert
        assert category == expected_category
        assert type_ == expected_type


@pytest.fixture
def mock_hdc_response():
    def fn(json_content):
        response = requests.Response()
        response.status_code = 200
        if json_content:
            response.json = lambda: json.loads(json_content)
        return response

    return fn
