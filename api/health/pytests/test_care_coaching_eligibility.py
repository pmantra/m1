from unittest import mock

import pytest

from health.models.risk_enums import RiskFlagName
from health.services.care_coaching_eligibility_service import (
    CareCoachingEligibilityService,
)
from health.services.health_profile_service import HealthProfileService
from models.tracks import TrackName
from models.tracks.client_track import TrackModifiers


@pytest.mark.parametrize(
    "track_name, fertility_treatment_status, risk_flags, country_code, track_modifier, is_eligible, reason",
    [
        (
            TrackName.FERTILITY,
            "undergoing_ivf",
            (),
            "US",
            None,
            True,
            "fertility_status",
        ),
        (
            TrackName.FERTILITY,
            "not_ttc_learning",
            (),
            "US",
            None,
            False,
            "fertility_status",
        ),
        (
            TrackName.MENOPAUSE,
            "undergoing_ivf",
            (),
            "US",
            None,
            False,
            "no_eligible_active_track",
        ),
        (
            TrackName.PREGNANCY,
            None,
            (RiskFlagName.AUTOIMMUNE_DISEASE, RiskFlagName.DIABETES_EXISTING),
            "US",
            None,
            True,
            "pregnancy_risk_flags",
        ),
        (
            TrackName.PREGNANCY,
            None,
            (RiskFlagName.AUTOIMMUNE_DISEASE, RiskFlagName.BLOOD_LOSS),
            "US",
            None,
            False,
            "pregnancy_risk_flags",
        ),
        (
            TrackName.PREGNANCY,
            None,
            (RiskFlagName.AUTOIMMUNE_DISEASE, RiskFlagName.DIABETES_EXISTING),
            "US",
            TrackModifiers.DOULA_ONLY,
            False,
            "pregnancy_is_doula_only",
        ),
        (
            TrackName.MENOPAUSE,
            None,
            (RiskFlagName.DIABETES_EXISTING,),
            "US",
            None,
            False,
            "no_eligible_active_track",
        ),
        (TrackName.FERTILITY, "undergoing_ivf", (), "CA", None, False, "non_us"),
        (
            TrackName.PREGNANCY,
            None,
            (RiskFlagName.LATE_THIRD_TRIMESTER,),
            "US",
            None,
            False,
            "late_third_trimester",
        ),
        (
            TrackName.PREGNANCY,
            None,
            (RiskFlagName.LATE_THIRD_TRIMESTER, RiskFlagName.DIABETES_EXISTING),
            "US",
            None,
            False,
            "late_third_trimester",
        ),
    ],
)
def test_get_care_coaching_eligibility(
    factories,
    client,
    api_helpers,
    track_name,
    fertility_treatment_status,
    risk_flags,
    country_code,
    track_modifier,
    is_eligible,
    reason,
):
    member = factories.MemberFactory.create(
        member_profile__country_code=country_code,
    )
    factories.MemberTrackFactory.create(
        user=member,
        name=track_name,
        client_track=factories.ClientTrackFactory.create(
            track=track_name, track_modifiers=track_modifier
        ),
    )
    if fertility_treatment_status:
        HealthProfileService(member).set_fertility_treatment_status(
            fertility_treatment_status
        )
    for risk_flag in risk_flags:
        factories.MemberRiskFlagFactory.create(
            user_id=member.id,
            risk_flag=factories.RiskFlagFactory.create(name=risk_flag),
        )

    with mock.patch(
        "models.tracks.client_track.should_enable_doula_only_track", return_value=True
    ), mock.patch(
        "health.services.care_coaching_eligibility_service.log.info"
    ) as logger_mock:
        res = client.get(
            "/api/v1/care_coaching_eligibility",
            headers=api_helpers.standard_headers(member),
        )
        json = api_helpers.load_json(res)

        assert res.status_code == 200
        assert json["is_eligible_for_care_coaching"] == is_eligible
        logger_mock.assert_called_once_with(
            "Calculated care coaching eligibility",
            user_id=member.id,
            reason=reason,
            is_eligible_for_care_coaching=is_eligible,
        )


@pytest.mark.parametrize("fertility_treatment_status", ["undergoing_ivf", None])
@mock.patch("health.services.care_coaching_eligibility_service.HealthProfileService")
def test_care_coaching_eligibility_reuses_fertility_treatment_status(
    mock_health_profile_service, factories, fertility_treatment_status
):
    member = factories.MemberFactory.create(
        member_profile__country_code="US",
    )
    factories.MemberTrackFactory.create(user=member, name=TrackName.FERTILITY)
    CareCoachingEligibilityService().is_user_eligible_for_care_coaching(
        user=member, fertility_treatment_status=fertility_treatment_status
    )

    mock_health_profile_service.assert_not_called()


@mock.patch("health.services.care_coaching_eligibility_service.HealthProfileService")
def test_is_user_eligible_for_care_coaching_without_passing_fertility_treatment_status(
    mock_health_profile_service, factories
):
    member = factories.MemberFactory.create(
        member_profile__country_code="US",
    )
    factories.MemberTrackFactory.create(user=member, name=TrackName.FERTILITY)
    CareCoachingEligibilityService().is_user_eligible_for_care_coaching(user=member)

    mock_health_profile_service.assert_called_once()
