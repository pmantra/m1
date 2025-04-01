from unittest import mock

import pytest

from health.models.risk_enums import RiskFlagName
from health.services.member_health_cohorts_service import MemberHealthCohortsService
from pytests.factories import EnterpriseUserFactory


@pytest.mark.parametrize(
    ("health_profile_value", "expected_result"),
    (("Male", "male"), ("male", "male"), (None, None), ("FeMALE", "female")),
)
def test_sex_at_birth(factories, health_profile_value, expected_result):
    user = factories.EnterpriseUserFactory()
    cohorts_service = MemberHealthCohortsService(user)
    cohorts_service._health_profile_service.set_json_field(
        "sex_at_birth", health_profile_value
    )

    assert cohorts_service.sex_at_birth == expected_result


@pytest.mark.parametrize(
    ("sex_at_birth", "allowed_sex_at_birth"),
    (
        ("male", False),
        ("female", True),
        ("FEMALE", True),
        (None, False),
    ),
)
@pytest.mark.parametrize(
    "fertility_treatment_status",
    ["not_ttc_learning", "ttc_in_six_months", "ttc_no_treatment", "ttc_no_iui_ivf"],
)
@mock.patch("health.services.health_profile_service.HealthProfileServiceClient")
def test_is_targeted_for_cycle_tracking(
    _,
    factories,
    risk_flags,
    fertility_treatment_status,
    sex_at_birth,
    allowed_sex_at_birth,
):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    cohorts_service = MemberHealthCohortsService(user)
    cohorts_service._health_profile_service.set_fertility_treatment_status(
        fertility_treatment_status
    )
    cohorts_service._health_profile_service.set_json_field("sex_at_birth", sex_at_birth)
    is_targeted_for_ovulation_tracking = (
        cohorts_service.is_targeted_for_ovulation_tracking()
    )
    if allowed_sex_at_birth:
        assert is_targeted_for_ovulation_tracking is True
    else:
        assert is_targeted_for_ovulation_tracking is False


@pytest.mark.parametrize(
    ("sex_at_birth", "allowed_sex_at_birth"),
    (
        ("male", False),
        ("female", True),
        ("FEMALE", True),
        (None, False),
    ),
)
@pytest.mark.parametrize(
    "fertility_treatment_status",
    ["not_ttc_learning", "ttc_in_six_months", "ttc_no_treatment", "ttc_no_iui_ivf"],
)
@pytest.mark.parametrize(
    ("user_risk_flags", "allowed_risk_flags"),
    (
        ([RiskFlagName.FEMALE_FEMALE_COUPLE], False),
        ([RiskFlagName.SINGLE_PARENT], False),
        ([RiskFlagName.FEMALE_FEMALE_COUPLE, RiskFlagName.SINGLE_PARENT], False),
        ([], True),
        ([RiskFlagName.KIDNEY_DISEASE], True),
    ),
)
@mock.patch("health.services.health_profile_service.HealthProfileServiceClient")
def test_is_targeted_for_ovulation_tracking(
    _,
    factories,
    risk_flags,
    user_risk_flags,
    allowed_risk_flags,
    fertility_treatment_status,
    sex_at_birth,
    allowed_sex_at_birth,
):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    cohorts_service = MemberHealthCohortsService(user)
    cohorts_service._health_profile_service.set_fertility_treatment_status(
        fertility_treatment_status
    )
    cohorts_service._health_profile_service.set_json_field("sex_at_birth", sex_at_birth)
    for risk_flag in user_risk_flags:
        cohorts_service._risk_service.set_risk(risk_flag)

    is_targeted_for_ovulation_tracking = (
        cohorts_service.is_targeted_for_ovulation_tracking()
    )
    if allowed_sex_at_birth and allowed_risk_flags:
        assert is_targeted_for_ovulation_tracking is True
    else:
        assert is_targeted_for_ovulation_tracking is False


@pytest.mark.parametrize(
    ("sex_at_birth", "allowed_sex_at_birth"),
    (("male", False), ("female", True)),
)
@pytest.mark.parametrize(
    "fertility_treatment_status",
    ["ttc_no_treatment", "ttc_no_iui_ivf", "considering_fertility_treatment"],
)
@pytest.mark.parametrize(
    ("user_risk_flags", "allowed_risk_flags"),
    (
        ([RiskFlagName.POLYCYSTIC_OVARIAN_SYNDROME], True),
        ([RiskFlagName.UNEXPLAINED_INFERTILITY], True),
        ([RiskFlagName.SINGLE_PARENT], False),
        ([], False),
        (
            [
                RiskFlagName.POLYCYSTIC_OVARIAN_SYNDROME,
                RiskFlagName.UNEXPLAINED_INFERTILITY,
            ],
            True,
        ),
        (
            [
                RiskFlagName.POLYCYSTIC_OVARIAN_SYNDROME,
                RiskFlagName.CONGENITAL_ABNORMALITY_AFFECTING_FERTILITY,
            ],
            False,
        ),
        ([RiskFlagName.UNEXPLAINED_INFERTILITY, RiskFlagName.HIV_AIDS], False),
    ),
)
@mock.patch("health.services.health_profile_service.HealthProfileServiceClient")
def test_is_targeted_for_ovulation_medication(
    _,
    factories,
    risk_flags,
    user_risk_flags,
    allowed_risk_flags,
    fertility_treatment_status,
    sex_at_birth,
    allowed_sex_at_birth,
):
    user = factories.EnterpriseUserFactory(tracks__name="fertility")
    cohorts_service = MemberHealthCohortsService(user)
    cohorts_service._health_profile_service.set_fertility_treatment_status(
        fertility_treatment_status
    )
    cohorts_service._health_profile_service.set_json_field("sex_at_birth", sex_at_birth)
    for risk_flag in user_risk_flags:
        cohorts_service._risk_service.set_risk(risk_flag)

    is_targeted_for_ovulation_medication = (
        cohorts_service.is_targeted_for_ovulation_medication()
    )
    if allowed_sex_at_birth and allowed_risk_flags:
        assert is_targeted_for_ovulation_medication is True
    else:
        assert is_targeted_for_ovulation_medication is False


@mock.patch("health.services.member_health_cohorts_service.HealthProfileService")
def test_cohorts_uses_cached_values(mock_health_profile, factories):
    user = EnterpriseUserFactory.create(tracks__name="fertility")
    cohorts_service = MemberHealthCohortsService(user)
    mock_health_profile.return_value.get_fertility_treatment_status.return_value = (
        "ttc_learning"
    )
    mock_health_profile.return_value.get_sex_at_birth.return_value = "female"

    cohorts_service.is_targeted_for_ovulation_tracking()
    cohorts_service.is_targeted_for_cycle_tracking()

    mock_health_profile.return_value.get_fertility_treatment_status.assert_called_once()
    mock_health_profile.return_value.get_sex_at_birth.assert_called_once()
