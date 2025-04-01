import json
from unittest import mock

import pytest

from direct_payment.clinic.pytests.factories import FertilityClinicUserProfileFactory
from eligibility.pytests import factories as e9y_factories
from pytests.factories import DefaultUserFactory, EnterpriseUserFactory
from wallet.models.constants import (
    ReimbursementMethod,
    ReimbursementRequestExpenseTypes,
    WalletState,
)
from wallet.models.models import AnnualInsuranceQuestionnaireHDHPData
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.resources.annual_questionnaire import AnnualQuestionnaireNeededResource


@pytest.fixture(scope="function")
def reimbursement_wallet_user(enterprise_user) -> ReimbursementWalletUsers:
    wallet = ReimbursementWalletFactory.create(
        state=WalletState.QUALIFIED,
        reimbursement_organization_settings__allowed_reimbursement_categories=[
            ("fertility", 5000, None),
            ("other", 3000, None),
        ],
        reimbursement_method=ReimbursementMethod.PAYROLL,
    )
    return ReimbursementWalletUsersFactory.create(
        user_id=enterprise_user.id,
        reimbursement_wallet_id=wallet.id,
    )


def test_annual_questionnaire_get_404(
    client,
    enterprise_user,
    api_helpers,
    questionnaire_wallet_user,
):
    wrong_wallet_id = questionnaire_wallet_user.wallet.id + 1000
    res = client.get(
        f"/api/v1/reimbursement_wallets/{wrong_wallet_id}/insurance/annual_questionnaire",
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 404


def test_annual_questionnaire_get_403(
    client,
    enterprise_user,
    api_helpers,
    questionnaire_wallet_user,
):
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=None,
    ):
        res = client.get(
            f"/api/v1/reimbursement_wallets/{questionnaire_wallet_user.wallet.id}/insurance/annual_questionnaire",
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 403


@pytest.mark.parametrize(
    "survey_response, survey_not_done, exp_msg, exp_code, exp_process_ins, exp_process_param",
    [
        (
            {
                "id": "d2b1cfd",
                "plan_year": "2025",
                "questionnaire_type": "TRADITIONAL_HDHP",
                "answers": {
                    "annual_insurance_survey_trad_wallet_hdhp_survey_self_q": "yes",
                    "annual_insurance_survey_trad_wallet_hdhp_survey_partner_q": "no",
                    "annual_insurance_survey_trad_wallet_hdhp_survey_q_health_pla_thru_employer": "self_only",
                },
            },
            True,
            "Accepted previous questionnaire. User does not need to complete the follow up questionnaire.",
            200,
            True,
            AnnualInsuranceQuestionnaireHDHPData(True, False),
        ),
        (
            {
                "bad_id": "d2b1cfd",
                "plan_year": "2025",
                "questionnaire_type": "TRADITIONAL_HDHP",
                "answers": {
                    "annual_insurance_survey_trad_wallet_hdhp_survey_self_q": "yes",
                    "annual_insurance_survey_trad_wallet_hdhp_survey_partner_q": "no",
                    "annual_insurance_survey_trad_wallet_hdhp_survey_q_health_pla_thru_employer": "self_only",
                },
            },
            True,
            "Request body does not match schema. Reason:  Keys: {'id'} are missing from payload",
            404,
            False,
            None,
        ),
        (
            {
                "plan_year": "2025",
                "questionnaire_type": "TRADITIONAL_HDHP",
                "answers": {
                    "annual_insurance_survey_trad_wallet_hdhp_survey_self_q": "yes",
                    "annual_insurance_survey_trad_wallet_hdhp_survey_partner_q": "no",
                    "annual_insurance_survey_trad_wallet_hdhp_survey_q_health_pla_thru_employer": "self_only",
                },
            },
            True,
            "Request body does not match schema. Reason:  Keys: {'id'} are missing from payload",
            404,
            False,
            None,
        ),
    ],
)
def test_annual_questionnaire_post(
    client,
    enterprise_user,
    api_helpers,
    questionnaire_wallet_user,
    annual_insurance_questionnaire_response,
    survey_response,
    survey_not_done,
    exp_msg,
    exp_code,
    exp_process_ins,
    exp_process_param,
):
    _ = annual_insurance_questionnaire_response(
        wallet_id=questionnaire_wallet_user.wallet.id + int(survey_not_done),
        submitting_user_id=questionnaire_wallet_user.id + int(survey_not_done),
    )
    verification = e9y_factories.build_verification_from_oe(
        enterprise_user.id, enterprise_user.organization_employee
    )
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ), mock.patch(
        "wallet.tasks.insurance.process_annual_questionnaire.delay"
    ) as mock_process_ins:
        res = client.post(
            f"/api/v1/reimbursement_wallets/{questionnaire_wallet_user.wallet.id}/insurance/annual_questionnaire",
            data=json.dumps(survey_response),
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == exp_code
    assert res.json == exp_msg
    if exp_process_ins:
        assert (
            mock_process_ins.call_args.kwargs["wallet_id"]
            == questionnaire_wallet_user.wallet.id
        )
        assert (
            mock_process_ins.call_args.kwargs["questionnaire_data"] == exp_process_param
        )


@pytest.mark.parametrize("fake_the_wallet, fake_the_user", ([1, False], [0, True]))
def test_annual_questionnaire_post_404(
    client,
    enterprise_user,
    api_helpers,
    questionnaire_wallet_user,
    annual_insurance_questionnaire_response,
    fake_the_wallet,
    fake_the_user,
):
    _ = annual_insurance_questionnaire_response(
        wallet_id=questionnaire_wallet_user.wallet.id,
        submitting_user_id=questionnaire_wallet_user.id,
    )
    wallet_id = questionnaire_wallet_user.wallet.id + fake_the_wallet
    user = EnterpriseUserFactory.create() if fake_the_user else enterprise_user
    verification = e9y_factories.build_verification_from_oe(
        enterprise_user.id, enterprise_user.organization_employee
    )
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=verification,
    ):
        res = client.post(
            f"/api/v1/reimbursement_wallets/{wallet_id}/insurance/annual_questionnaire",
            data=json.dumps(
                {"id": "d2b1cfd", "answers": {"b1c54fa": "yes", "cf164ee": "no"}}
            ),
            headers=api_helpers.json_headers(user),
        )
        assert res.status_code == 404
        assert res.json["message"] == f"ReimbursementWallet {wallet_id} is invalid."


def test_annual_questionnaire_post_403(
    client,
    enterprise_user,
    api_helpers,
    questionnaire_wallet_user,
    annual_insurance_questionnaire_response,
):
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=None,
    ):
        res = client.post(
            f"/api/v1/reimbursement_wallets/{questionnaire_wallet_user.wallet.id}/insurance/annual_questionnaire",
            data=json.dumps(
                {"id": "d2b1cfd", "answers": {"b1c54fa": "yes", "cf164ee": "no"}}
            ),
            headers=api_helpers.json_headers(enterprise_user),
        )
        assert res.status_code == 403
        assert res.json["message"] == "Not Authorized for Wallet"


def test_annual_questionnaire_needed_403_check(
    client,
    enterprise_user,
    monkeypatch,
    api_helpers,
    reimbursement_wallet_user,
):
    AnnualQuestionnaireNeededResource.current_year = 2020
    reimbursement_wallet_user.wallet.primary_expense_type = (
        ReimbursementRequestExpenseTypes.FERTILITY
    )
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=None,
    ):
        res = client.get(
            f"/api/v1/reimbursement_wallets/{reimbursement_wallet_user.wallet.id}"
            "/insurance/annual_questionnaire/needs_survey",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == {"needs_survey": False, "needs_any_survey": False}


@pytest.mark.parametrize(
    "any_survey, mocked_e9y, mocked_is_questionnaire_needed_for_user_and_wallet, "
    "mocked_is_any_questionnaire_needed_for_user_and_wallet, expected",
    [
        pytest.param(
            None,
            True,
            True,
            True,
            {"needs_survey": True, "needs_any_survey": False},
            id="Current survey needed. Any survey arg missing ",
        ),
        pytest.param(
            False,
            True,
            True,
            True,
            {"needs_survey": True, "needs_any_survey": False},
            id="Current survey needed. Any survey arg False ",
        ),
        pytest.param(
            True,
            True,
            True,
            None,
            {"needs_survey": True, "needs_any_survey": True},
            id="Current survey needed. Any survey arg True ",
        ),
        pytest.param(
            True,
            True,
            False,
            False,
            {"needs_survey": False, "needs_any_survey": False},
            id="No surveys needed. Any survey arg True ",
        ),
        pytest.param(
            True,
            True,
            False,
            True,
            {"needs_survey": False, "needs_any_survey": True},
            id="Current survey not needed. Any survey needed, Any survey arg True ",
        ),
    ],
)
def test_annual_questionnaire_needed_check_new(
    ff_test_data,
    client,
    enterprise_user,
    api_helpers,
    reimbursement_wallet_user,
    any_survey,
    mocked_e9y,
    mocked_is_questionnaire_needed_for_user_and_wallet,
    mocked_is_any_questionnaire_needed_for_user_and_wallet,
    expected,
):
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
        return_value=mocked_e9y,
    ), mock.patch(
        "wallet.resources.annual_questionnaire.is_questionnaire_needed_for_user_and_wallet",
        return_value=mocked_is_questionnaire_needed_for_user_and_wallet,
    ), mock.patch(
        "wallet.resources.annual_questionnaire.is_any_questionnaire_needed_for_user_and_wallet",
        return_value=mocked_is_any_questionnaire_needed_for_user_and_wallet,
    ) as mocked_is_any:
        base_url = (
            f"/api/v1/reimbursement_wallets/{reimbursement_wallet_user.wallet.id}"
            f"/insurance/annual_questionnaire/needs_survey"
        )
        if any_survey is not None:
            base_url = f"{base_url}?any_survey={any_survey}"
        res = client.get(
            base_url,
            headers=api_helpers.json_headers(enterprise_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == expected
    if mocked_is_any_questionnaire_needed_for_user_and_wallet is None:
        assert not mocked_is_any.called


@pytest.mark.parametrize(
    "mocked_is_questionnaire_needed_for_user_and_wallet, mocked_is_any_questionnaire_needed_for_user_and_wallet,"
    "expected",
    [
        pytest.param(
            True,
            None,
            {"needs_survey": True, "needs_any_survey": True},
            id="FFlag On. Current survey needed - any true by default  ",
        ),
        pytest.param(
            False,
            False,
            {"needs_survey": False, "needs_any_survey": False},
            id="FFlag On. Current and future surveys not needed ",
        ),
        pytest.param(
            False,
            True,
            {"needs_survey": False, "needs_any_survey": True},
            id="FFlag On. Current not needed. Future surveys needed ",
        ),
    ],
)
def test_annual_questionnaire_needed_in_clinic_check(
    client,
    api_helpers,
    qualified_wallet,
    mocked_is_questionnaire_needed_for_user_and_wallet,
    mocked_is_any_questionnaire_needed_for_user_and_wallet,
    expected,
):
    with mock.patch(
        "wallet.resources.annual_questionnaire.is_questionnaire_needed_for_user_and_wallet",
        return_value=mocked_is_questionnaire_needed_for_user_and_wallet,
    ) as mocked_is_needed, mock.patch(
        "wallet.resources.annual_questionnaire.is_any_questionnaire_needed_for_user_and_wallet",
        return_value=mocked_is_any_questionnaire_needed_for_user_and_wallet,
    ) as mocked_is_any_needed, mock.patch(
        "wallet.resources.common.WalletResourceMixin._wallet_or_404",
        return_value=qualified_wallet,
    ):
        base_url = (
            f"/api/v1/reimbursement_wallets/{qualified_wallet.id}"
            f"/insurance/annual_questionnaire/clinic_portal/needs_survey?member_user_id={qualified_wallet.user_id}"
        )

        clinic_user = DefaultUserFactory.create(id=123456)
        _ = FertilityClinicUserProfileFactory.create(user_id=clinic_user.id)

        res = client.get(
            base_url,
            headers=api_helpers.json_headers(clinic_user),
        )
    assert res.status_code == 200
    content = api_helpers.load_json(res)
    assert content == expected
    for (mock_value, mock_obj) in [
        (mocked_is_questionnaire_needed_for_user_and_wallet, mocked_is_needed),
        (mocked_is_any_questionnaire_needed_for_user_and_wallet, mocked_is_any_needed),
    ]:
        if mock_value is not None:
            assert mock_obj.called is True
            assert mock_obj.call_args[0][0].id == qualified_wallet.user_id
            assert mock_obj.call_args[0][0].id != clinic_user.id
            assert mock_obj.call_args[0][1] == qualified_wallet
        else:
            assert mock_obj.called is False


def test_annual_questionnaire_needed_in_clinic_check_error(
    client, api_helpers, qualified_wallet
):
    base_url = (
        f"/api/v1/reimbursement_wallets/{qualified_wallet.id}"
        f"/insurance/annual_questionnaire/clinic_portal/needs_survey?member_user_id=abc"
    )
    clinic_user = DefaultUserFactory.create(id=123456)
    _ = FertilityClinicUserProfileFactory.create(user_id=clinic_user.id)
    res = client.get(
        base_url,
        headers=api_helpers.json_headers(clinic_user),
    )
    assert res.status_code == 400
