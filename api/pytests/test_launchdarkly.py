from datetime import date
from unittest.mock import patch

import pytest
from babel import Locale

from health.data_models.risk_flag import RiskFlag, RiskFlagSeverity
from health.services.health_profile_service import HealthProfileService
from health.services.member_risk_service import MemberRiskService
from models.tracks import TrackName
from pytests import factories

launchdarkly_context_url = "/api/v1/launchdarkly_context"


@pytest.fixture
def practitioner_ob_gyn(factories):
    return factories.PractitionerUserFactory.create()


@pytest.fixture
def practitioner_ca(factories):
    ca = factories.PractitionerUserFactory.create()
    v = factories.VerticalFactory.create_cx_vertical()
    ca.practitioner_profile.verticals = [v]
    return ca


def test_launchdarkly_context_unauthenticated(client):
    # When
    res = client.get(launchdarkly_context_url)
    # Then
    assert res.status_code == 401


@patch(
    "api.user_locale.services.locale_preference_service.LocalePreferenceService.get_preferred_locale_for_user"
)
def test_launchdarkly_context_pregnancy_user(mock_get_locale, client, api_helpers):
    # Given
    user = factories.EnterpriseUserFactory.create()
    org_id = user.organization_v2.id if user.organization_v2 else None
    pregnancy = user.active_tracks[0]
    pregnancy.start_date = date(2024, 5, 4)
    mock_get_locale.return_value = Locale("en", "US")

    # When
    res = client.get(launchdarkly_context_url, headers=api_helpers.json_headers(user))
    # Then
    assert res.status_code == 200
    assert res.json == {
        "kind": "multi",
        "monolith-health-profile": {
            "key": user.esp_id,
            "riskFactors": [],
            "_meta": {
                "privateAttributes": ["riskFactors", "fertilityTreatmentStatus"],
            },
        },
        "user": {
            "key": user.esp_id,
            "userId": user.id,
            "createdAt": user.created_at.isoformat(),
            "name": user.full_name,
            "email": user.email,
            "lowercaseEmail": user.email.lower(),
            "locale": "en",
            "country": "US",
            "roles": ["member"],
            "isEnterprise": True,
            "organizationId": org_id,
            "organizationV2Id": org_id,
            "activeTracks": ["pregnancy"],
            "pregnancyCurrentPhase": "week-1",
            "pregnancyScheduledEndDate": pregnancy.get_scheduled_end_date().isoformat(),
            "pregnancyStartDate": 1714780800000,
            "isMultiTrack": False,
            "_meta": {
                "privateAttributes": [
                    "userId",
                    "createdAt",
                    "name",
                    "email",
                    "lowercaseEmail",
                    "locale",
                    "country",
                    "state",
                    "roles",
                    "verticals",
                    "isEnterprise",
                    "organizationId",
                    "adoptionCurrentPhase",
                    "breastMilkShippingCurrentPhase",
                    "eggFreezingCurrentPhase",
                    "fertilityCurrentPhase",
                    "generalWellnessCurrentPhase",
                    "genericCurrentPhase",
                    "parentingAndPediatricsCurrentPhase",
                    "partnerFertilityCurrentPhase",
                    "partnerNewparentCurrentPhase",
                    "partnerPregnantCurrentPhase",
                    "postpartumCurrentPhase",
                    "pregnancyCurrentPhase",
                    "pregnancylossCurrentPhase",
                    "pregnancyOptionsCurrentPhase",
                    "sponsoredCurrentPhase",
                    "surrogacyCurrentPhase",
                    "tryingToConceiveCurrentPhase",
                    "menopauseCurrentPhase",
                    "adoptionScheduledEndDate",
                    "breastMilkShippingScheduledEndDate",
                    "eggFreezingScheduledEndDate",
                    "fertilityScheduledEndDate",
                    "generalWellnessScheduledEndDate",
                    "genericScheduledEndDate",
                    "parentingAndPediatricsScheduledEndDate",
                    "partnerFertilityScheduledEndDate",
                    "partnerNewparentScheduledEndDate",
                    "partnerPregnantScheduledEndDate",
                    "postpartumScheduledEndDate",
                    "pregnancyScheduledEndDate",
                    "pregnancylossScheduledEndDate",
                    "pregnancyOptionsScheduledEndDate",
                    "sponsoredScheduledEndDate",
                    "surrogacyScheduledEndDate",
                    "tryingToConceiveScheduledEndDate",
                    "menopauseScheduledEndDate",
                    "adoptionStartDate",
                    "breastMilkShippingStartDate",
                    "eggFreezingStartDate",
                    "fertilityStartDate",
                    "generalWellnessStartDate",
                    "genericStartDate",
                    "parentingAndPediatricsStartDate",
                    "partnerFertilityStartDate",
                    "partnerNewparentStartDate",
                    "partnerPregnantStartDate",
                    "postpartumStartDate",
                    "pregnancyStartDate",
                    "pregnancylossStartDate",
                    "pregnancyOptionsStartDate",
                    "sponsoredStartDate",
                    "surrogacyStartDate",
                    "tryingToConceiveStartDate",
                    "menopauseStartDate",
                    "activeTracks",
                    "isMultiTrack",
                ]
            },
        },
    }


@patch(
    "api.user_locale.services.locale_preference_service.LocalePreferenceService.get_preferred_locale_for_user"
)
def test_launchdarkly_context_multi_track_user(mock_get_locale, client, api_helpers):
    # Given
    user = factories.EnterpriseUserNoTracksFactory.create()

    factories.MemberTrackFactory.create(name=TrackName.PREGNANCY, user=user)
    factories.MemberTrackFactory.create(
        name=TrackName.PARENTING_AND_PEDIATRICS,
        user=user,
    )
    pregnancy, parenting_and_pediatrics = user.active_tracks
    pregnancy.start_date = date(2024, 5, 4)
    parenting_and_pediatrics.start_date = date(2024, 5, 4)
    mock_get_locale.return_value = Locale("en", "US")
    org_id_v2 = (
        user.active_client_track.organization_id if user.active_client_track else None
    )

    # When
    res = client.get(launchdarkly_context_url, headers=api_helpers.json_headers(user))
    # Then
    assert res.status_code == 200
    assert res.json == {
        "kind": "multi",
        "monolith-health-profile": {
            "key": user.esp_id,
            "riskFactors": [],
            "_meta": {
                "privateAttributes": ["riskFactors", "fertilityTreatmentStatus"],
            },
        },
        "user": {
            "key": user.esp_id,
            "userId": user.id,
            "createdAt": user.created_at.isoformat(),
            "name": user.full_name,
            "email": user.email,
            "lowercaseEmail": user.email.lower(),
            "locale": "en",
            "country": "US",
            "roles": ["member"],
            "isEnterprise": True,
            "organizationId": user.organization.id,
            "organizationV2Id": org_id_v2,
            "activeTracks": ["pregnancy", "parenting_and_pediatrics"],
            "pregnancyCurrentPhase": "week-1",
            "pregnancyScheduledEndDate": pregnancy.get_scheduled_end_date().isoformat(),
            "pregnancyStartDate": 1714780800000,
            "parentingAndPediatricsCurrentPhase": "week-1",
            "parentingAndPediatricsScheduledEndDate": parenting_and_pediatrics.get_scheduled_end_date().isoformat(),
            "parentingAndPediatricsStartDate": 1714780800000,
            "isMultiTrack": True,
            "_meta": {
                "privateAttributes": [
                    "userId",
                    "createdAt",
                    "name",
                    "email",
                    "lowercaseEmail",
                    "locale",
                    "country",
                    "state",
                    "roles",
                    "verticals",
                    "isEnterprise",
                    "organizationId",
                    "adoptionCurrentPhase",
                    "breastMilkShippingCurrentPhase",
                    "eggFreezingCurrentPhase",
                    "fertilityCurrentPhase",
                    "generalWellnessCurrentPhase",
                    "genericCurrentPhase",
                    "parentingAndPediatricsCurrentPhase",
                    "partnerFertilityCurrentPhase",
                    "partnerNewparentCurrentPhase",
                    "partnerPregnantCurrentPhase",
                    "postpartumCurrentPhase",
                    "pregnancyCurrentPhase",
                    "pregnancylossCurrentPhase",
                    "pregnancyOptionsCurrentPhase",
                    "sponsoredCurrentPhase",
                    "surrogacyCurrentPhase",
                    "tryingToConceiveCurrentPhase",
                    "menopauseCurrentPhase",
                    "adoptionScheduledEndDate",
                    "breastMilkShippingScheduledEndDate",
                    "eggFreezingScheduledEndDate",
                    "fertilityScheduledEndDate",
                    "generalWellnessScheduledEndDate",
                    "genericScheduledEndDate",
                    "parentingAndPediatricsScheduledEndDate",
                    "partnerFertilityScheduledEndDate",
                    "partnerNewparentScheduledEndDate",
                    "partnerPregnantScheduledEndDate",
                    "postpartumScheduledEndDate",
                    "pregnancyScheduledEndDate",
                    "pregnancylossScheduledEndDate",
                    "pregnancyOptionsScheduledEndDate",
                    "sponsoredScheduledEndDate",
                    "surrogacyScheduledEndDate",
                    "tryingToConceiveScheduledEndDate",
                    "menopauseScheduledEndDate",
                    "adoptionStartDate",
                    "breastMilkShippingStartDate",
                    "eggFreezingStartDate",
                    "fertilityStartDate",
                    "generalWellnessStartDate",
                    "genericStartDate",
                    "parentingAndPediatricsStartDate",
                    "partnerFertilityStartDate",
                    "partnerNewparentStartDate",
                    "partnerPregnantStartDate",
                    "postpartumStartDate",
                    "pregnancyStartDate",
                    "pregnancylossStartDate",
                    "pregnancyOptionsStartDate",
                    "sponsoredStartDate",
                    "surrogacyStartDate",
                    "tryingToConceiveStartDate",
                    "menopauseStartDate",
                    "activeTracks",
                    "isMultiTrack",
                ]
            },
        },
    }


@patch(
    "api.user_locale.services.locale_preference_service.LocalePreferenceService.get_preferred_locale_for_user"
)
def test_launchdarkly_context_marketplace_user(mock_get_locale, client, api_helpers):
    # Given
    user = factories.MemberFactory.create()
    mock_get_locale.return_value = Locale("en", "US")
    # When
    res = client.get(launchdarkly_context_url, headers=api_helpers.json_headers(user))
    # Then
    assert res.status_code == 200
    assert res.json == {
        "kind": "multi",
        "monolith-health-profile": {
            "key": user.esp_id,
            "riskFactors": [],
            "_meta": {
                "privateAttributes": ["riskFactors", "fertilityTreatmentStatus"],
            },
        },
        "user": {
            "key": user.esp_id,
            "userId": user.id,
            "createdAt": user.created_at.isoformat(),
            "name": user.full_name,
            "email": user.email,
            "lowercaseEmail": user.email.lower(),
            "locale": "en",
            "country": "US",
            "roles": ["member"],
            "isEnterprise": False,
            "activeTracks": [],
            "isMultiTrack": False,
            "_meta": {
                "privateAttributes": [
                    "userId",
                    "createdAt",
                    "name",
                    "email",
                    "lowercaseEmail",
                    "locale",
                    "country",
                    "state",
                    "roles",
                    "verticals",
                    "isEnterprise",
                    "organizationId",
                    "adoptionCurrentPhase",
                    "breastMilkShippingCurrentPhase",
                    "eggFreezingCurrentPhase",
                    "fertilityCurrentPhase",
                    "generalWellnessCurrentPhase",
                    "genericCurrentPhase",
                    "parentingAndPediatricsCurrentPhase",
                    "partnerFertilityCurrentPhase",
                    "partnerNewparentCurrentPhase",
                    "partnerPregnantCurrentPhase",
                    "postpartumCurrentPhase",
                    "pregnancyCurrentPhase",
                    "pregnancylossCurrentPhase",
                    "pregnancyOptionsCurrentPhase",
                    "sponsoredCurrentPhase",
                    "surrogacyCurrentPhase",
                    "tryingToConceiveCurrentPhase",
                    "menopauseCurrentPhase",
                    "adoptionScheduledEndDate",
                    "breastMilkShippingScheduledEndDate",
                    "eggFreezingScheduledEndDate",
                    "fertilityScheduledEndDate",
                    "generalWellnessScheduledEndDate",
                    "genericScheduledEndDate",
                    "parentingAndPediatricsScheduledEndDate",
                    "partnerFertilityScheduledEndDate",
                    "partnerNewparentScheduledEndDate",
                    "partnerPregnantScheduledEndDate",
                    "postpartumScheduledEndDate",
                    "pregnancyScheduledEndDate",
                    "pregnancylossScheduledEndDate",
                    "pregnancyOptionsScheduledEndDate",
                    "sponsoredScheduledEndDate",
                    "surrogacyScheduledEndDate",
                    "tryingToConceiveScheduledEndDate",
                    "menopauseScheduledEndDate",
                    "adoptionStartDate",
                    "breastMilkShippingStartDate",
                    "eggFreezingStartDate",
                    "fertilityStartDate",
                    "generalWellnessStartDate",
                    "genericStartDate",
                    "parentingAndPediatricsStartDate",
                    "partnerFertilityStartDate",
                    "partnerNewparentStartDate",
                    "partnerPregnantStartDate",
                    "postpartumStartDate",
                    "pregnancyStartDate",
                    "pregnancylossStartDate",
                    "pregnancyOptionsStartDate",
                    "sponsoredStartDate",
                    "surrogacyStartDate",
                    "tryingToConceiveStartDate",
                    "menopauseStartDate",
                    "activeTracks",
                    "isMultiTrack",
                ]
            },
        },
    }


@patch(
    "api.user_locale.services.locale_preference_service.LocalePreferenceService.get_preferred_locale_for_user"
)
def test_launchdarkly_context_marketplace_user_with_state(
    mock_get_locale, client, api_helpers, create_state
):
    # Given
    user = factories.MemberFactory.create()
    user.member_profile.state = create_state("NY")
    mock_get_locale.return_value = Locale("en", "US")
    # When
    res = client.get(launchdarkly_context_url, headers=api_helpers.json_headers(user))
    # Then
    assert res.status_code == 200
    assert res.json == {
        "kind": "multi",
        "monolith-health-profile": {
            "key": user.esp_id,
            "riskFactors": [],
            "_meta": {
                "privateAttributes": ["riskFactors", "fertilityTreatmentStatus"],
            },
        },
        "user": {
            "key": user.esp_id,
            "userId": user.id,
            "createdAt": user.created_at.isoformat(),
            "name": user.full_name,
            "email": user.email,
            "lowercaseEmail": user.email.lower(),
            "locale": "en",
            "country": "US",
            "state": "NY",
            "roles": ["member"],
            "isEnterprise": False,
            "activeTracks": [],
            "isMultiTrack": False,
            "_meta": {
                "privateAttributes": [
                    "userId",
                    "createdAt",
                    "name",
                    "email",
                    "lowercaseEmail",
                    "locale",
                    "country",
                    "state",
                    "roles",
                    "verticals",
                    "isEnterprise",
                    "organizationId",
                    "adoptionCurrentPhase",
                    "breastMilkShippingCurrentPhase",
                    "eggFreezingCurrentPhase",
                    "fertilityCurrentPhase",
                    "generalWellnessCurrentPhase",
                    "genericCurrentPhase",
                    "parentingAndPediatricsCurrentPhase",
                    "partnerFertilityCurrentPhase",
                    "partnerNewparentCurrentPhase",
                    "partnerPregnantCurrentPhase",
                    "postpartumCurrentPhase",
                    "pregnancyCurrentPhase",
                    "pregnancylossCurrentPhase",
                    "pregnancyOptionsCurrentPhase",
                    "sponsoredCurrentPhase",
                    "surrogacyCurrentPhase",
                    "tryingToConceiveCurrentPhase",
                    "menopauseCurrentPhase",
                    "adoptionScheduledEndDate",
                    "breastMilkShippingScheduledEndDate",
                    "eggFreezingScheduledEndDate",
                    "fertilityScheduledEndDate",
                    "generalWellnessScheduledEndDate",
                    "genericScheduledEndDate",
                    "parentingAndPediatricsScheduledEndDate",
                    "partnerFertilityScheduledEndDate",
                    "partnerNewparentScheduledEndDate",
                    "partnerPregnantScheduledEndDate",
                    "postpartumScheduledEndDate",
                    "pregnancyScheduledEndDate",
                    "pregnancylossScheduledEndDate",
                    "pregnancyOptionsScheduledEndDate",
                    "sponsoredScheduledEndDate",
                    "surrogacyScheduledEndDate",
                    "tryingToConceiveScheduledEndDate",
                    "menopauseScheduledEndDate",
                    "adoptionStartDate",
                    "breastMilkShippingStartDate",
                    "eggFreezingStartDate",
                    "fertilityStartDate",
                    "generalWellnessStartDate",
                    "genericStartDate",
                    "parentingAndPediatricsStartDate",
                    "partnerFertilityStartDate",
                    "partnerNewparentStartDate",
                    "partnerPregnantStartDate",
                    "postpartumStartDate",
                    "pregnancyStartDate",
                    "pregnancylossStartDate",
                    "pregnancyOptionsStartDate",
                    "sponsoredStartDate",
                    "surrogacyStartDate",
                    "tryingToConceiveStartDate",
                    "menopauseStartDate",
                    "activeTracks",
                    "isMultiTrack",
                ]
            },
        },
    }


@patch(
    "api.user_locale.services.locale_preference_service.LocalePreferenceService.get_preferred_locale_for_user"
)
def test_launchdarkly_context_marketplace_user_with_risk_flags(
    mock_get_locale, client, api_helpers, db
):
    # Given
    user = factories.MemberFactory.create()
    mock_get_locale.return_value = Locale("en", "US")

    db.session.add(RiskFlag(severity=RiskFlagSeverity.HIGH_RISK, name="High Risk Flag"))
    db.session.add(
        RiskFlag(severity=RiskFlagSeverity.MEDIUM_RISK, name="Medium Risk Flag")
    )
    db.session.add(RiskFlag(severity=RiskFlagSeverity.LOW_RISK, name="Low Risk Flag"))
    db.session.add(RiskFlag(severity=RiskFlagSeverity.NONE, name="None Risk Flag"))
    db.session.commit()
    service = MemberRiskService(user.id)
    service.set_risk("High Risk Flag")
    service.set_risk("Medium Risk Flag")
    service.set_risk("Low Risk Flag")
    service.set_risk("None Risk Flag")
    db.session.refresh(user)
    # When
    res = client.get(launchdarkly_context_url, headers=api_helpers.json_headers(user))
    # Then
    assert res.status_code == 200
    assert res.json == {
        "kind": "multi",
        "monolith-health-profile": {
            "key": user.esp_id,
            "riskFactors": [
                "High Risk Flag",
                "Medium Risk Flag",
                "Low Risk Flag",
                "None Risk Flag",
            ],
            "_meta": {
                "privateAttributes": ["riskFactors", "fertilityTreatmentStatus"],
            },
        },
        "user": {
            "key": user.esp_id,
            "userId": user.id,
            "createdAt": user.created_at.isoformat(),
            "name": user.full_name,
            "email": user.email,
            "lowercaseEmail": user.email.lower(),
            "locale": "en",
            "country": "US",
            "roles": ["member"],
            "isEnterprise": False,
            "activeTracks": [],
            "isMultiTrack": False,
            "_meta": {
                "privateAttributes": [
                    "userId",
                    "createdAt",
                    "name",
                    "email",
                    "lowercaseEmail",
                    "locale",
                    "country",
                    "state",
                    "roles",
                    "verticals",
                    "isEnterprise",
                    "organizationId",
                    "adoptionCurrentPhase",
                    "breastMilkShippingCurrentPhase",
                    "eggFreezingCurrentPhase",
                    "fertilityCurrentPhase",
                    "generalWellnessCurrentPhase",
                    "genericCurrentPhase",
                    "parentingAndPediatricsCurrentPhase",
                    "partnerFertilityCurrentPhase",
                    "partnerNewparentCurrentPhase",
                    "partnerPregnantCurrentPhase",
                    "postpartumCurrentPhase",
                    "pregnancyCurrentPhase",
                    "pregnancylossCurrentPhase",
                    "pregnancyOptionsCurrentPhase",
                    "sponsoredCurrentPhase",
                    "surrogacyCurrentPhase",
                    "tryingToConceiveCurrentPhase",
                    "menopauseCurrentPhase",
                    "adoptionScheduledEndDate",
                    "breastMilkShippingScheduledEndDate",
                    "eggFreezingScheduledEndDate",
                    "fertilityScheduledEndDate",
                    "generalWellnessScheduledEndDate",
                    "genericScheduledEndDate",
                    "parentingAndPediatricsScheduledEndDate",
                    "partnerFertilityScheduledEndDate",
                    "partnerNewparentScheduledEndDate",
                    "partnerPregnantScheduledEndDate",
                    "postpartumScheduledEndDate",
                    "pregnancyScheduledEndDate",
                    "pregnancylossScheduledEndDate",
                    "pregnancyOptionsScheduledEndDate",
                    "sponsoredScheduledEndDate",
                    "surrogacyScheduledEndDate",
                    "tryingToConceiveScheduledEndDate",
                    "menopauseScheduledEndDate",
                    "adoptionStartDate",
                    "breastMilkShippingStartDate",
                    "eggFreezingStartDate",
                    "fertilityStartDate",
                    "generalWellnessStartDate",
                    "genericStartDate",
                    "parentingAndPediatricsStartDate",
                    "partnerFertilityStartDate",
                    "partnerNewparentStartDate",
                    "partnerPregnantStartDate",
                    "postpartumStartDate",
                    "pregnancyStartDate",
                    "pregnancylossStartDate",
                    "pregnancyOptionsStartDate",
                    "sponsoredStartDate",
                    "surrogacyStartDate",
                    "tryingToConceiveStartDate",
                    "menopauseStartDate",
                    "activeTracks",
                    "isMultiTrack",
                ]
            },
        },
    }


@patch(
    "api.user_locale.services.locale_preference_service.LocalePreferenceService.get_preferred_locale_for_user"
)
def test_launchdarkly_context_marketplace_user_with_fertility_treatment_status(
    mock_get_locale, client, api_helpers
):
    # Given
    user = factories.MemberFactory.create()
    HealthProfileService(user).set_fertility_treatment_status("undergoing_ivf")
    mock_get_locale.return_value = Locale("en", "US")
    # When
    res = client.get(launchdarkly_context_url, headers=api_helpers.json_headers(user))
    # Then
    assert res.status_code == 200
    assert res.json == {
        "kind": "multi",
        "monolith-health-profile": {
            "key": user.esp_id,
            "riskFactors": [],
            "fertilityTreatmentStatus": "undergoing_ivf",
            "_meta": {
                "privateAttributes": ["riskFactors", "fertilityTreatmentStatus"],
            },
        },
        "user": {
            "key": user.esp_id,
            "userId": user.id,
            "createdAt": user.created_at.isoformat(),
            "name": user.full_name,
            "email": user.email,
            "lowercaseEmail": user.email.lower(),
            "locale": "en",
            "country": "US",
            "roles": ["member"],
            "isEnterprise": False,
            "activeTracks": [],
            "isMultiTrack": False,
            "_meta": {
                "privateAttributes": [
                    "userId",
                    "createdAt",
                    "name",
                    "email",
                    "lowercaseEmail",
                    "locale",
                    "country",
                    "state",
                    "roles",
                    "verticals",
                    "isEnterprise",
                    "organizationId",
                    "adoptionCurrentPhase",
                    "breastMilkShippingCurrentPhase",
                    "eggFreezingCurrentPhase",
                    "fertilityCurrentPhase",
                    "generalWellnessCurrentPhase",
                    "genericCurrentPhase",
                    "parentingAndPediatricsCurrentPhase",
                    "partnerFertilityCurrentPhase",
                    "partnerNewparentCurrentPhase",
                    "partnerPregnantCurrentPhase",
                    "postpartumCurrentPhase",
                    "pregnancyCurrentPhase",
                    "pregnancylossCurrentPhase",
                    "pregnancyOptionsCurrentPhase",
                    "sponsoredCurrentPhase",
                    "surrogacyCurrentPhase",
                    "tryingToConceiveCurrentPhase",
                    "menopauseCurrentPhase",
                    "adoptionScheduledEndDate",
                    "breastMilkShippingScheduledEndDate",
                    "eggFreezingScheduledEndDate",
                    "fertilityScheduledEndDate",
                    "generalWellnessScheduledEndDate",
                    "genericScheduledEndDate",
                    "parentingAndPediatricsScheduledEndDate",
                    "partnerFertilityScheduledEndDate",
                    "partnerNewparentScheduledEndDate",
                    "partnerPregnantScheduledEndDate",
                    "postpartumScheduledEndDate",
                    "pregnancyScheduledEndDate",
                    "pregnancylossScheduledEndDate",
                    "pregnancyOptionsScheduledEndDate",
                    "sponsoredScheduledEndDate",
                    "surrogacyScheduledEndDate",
                    "tryingToConceiveScheduledEndDate",
                    "menopauseScheduledEndDate",
                    "adoptionStartDate",
                    "breastMilkShippingStartDate",
                    "eggFreezingStartDate",
                    "fertilityStartDate",
                    "generalWellnessStartDate",
                    "genericStartDate",
                    "parentingAndPediatricsStartDate",
                    "partnerFertilityStartDate",
                    "partnerNewparentStartDate",
                    "partnerPregnantStartDate",
                    "postpartumStartDate",
                    "pregnancyStartDate",
                    "pregnancylossStartDate",
                    "pregnancyOptionsStartDate",
                    "sponsoredStartDate",
                    "surrogacyStartDate",
                    "tryingToConceiveStartDate",
                    "menopauseStartDate",
                    "activeTracks",
                    "isMultiTrack",
                ]
            },
        },
    }


@patch(
    "api.user_locale.services.locale_preference_service.LocalePreferenceService.get_preferred_locale_for_user"
)
def test_launchdarkly_context_practitioner_ob_gyn_verticals(
    mock_get_locale, client, api_helpers, practitioner_ob_gyn
):
    # Given
    user = practitioner_ob_gyn
    mock_get_locale.return_value = Locale("en", "US")
    # When
    res = client.get(launchdarkly_context_url, headers=api_helpers.json_headers(user))
    # Then
    assert res.status_code == 200
    assert res.json == {
        "kind": "multi",
        "monolith-health-profile": {
            "key": user.esp_id,
            "riskFactors": [],
            "_meta": {
                "privateAttributes": ["riskFactors", "fertilityTreatmentStatus"],
            },
        },
        "user": {
            "key": user.esp_id,
            "userId": user.id,
            "createdAt": user.created_at.isoformat(),
            "name": user.full_name,
            "email": user.email,
            "lowercaseEmail": user.email.lower(),
            "locale": "en",
            "country": "US",
            "roles": ["practitioner"],
            "verticals": ["OB-GYN"],
            "isEnterprise": False,
            "activeTracks": [],
            "isMultiTrack": False,
            "_meta": {
                "privateAttributes": [
                    "userId",
                    "createdAt",
                    "name",
                    "email",
                    "lowercaseEmail",
                    "locale",
                    "country",
                    "state",
                    "roles",
                    "verticals",
                    "isEnterprise",
                    "organizationId",
                    "adoptionCurrentPhase",
                    "breastMilkShippingCurrentPhase",
                    "eggFreezingCurrentPhase",
                    "fertilityCurrentPhase",
                    "generalWellnessCurrentPhase",
                    "genericCurrentPhase",
                    "parentingAndPediatricsCurrentPhase",
                    "partnerFertilityCurrentPhase",
                    "partnerNewparentCurrentPhase",
                    "partnerPregnantCurrentPhase",
                    "postpartumCurrentPhase",
                    "pregnancyCurrentPhase",
                    "pregnancylossCurrentPhase",
                    "pregnancyOptionsCurrentPhase",
                    "sponsoredCurrentPhase",
                    "surrogacyCurrentPhase",
                    "tryingToConceiveCurrentPhase",
                    "menopauseCurrentPhase",
                    "adoptionScheduledEndDate",
                    "breastMilkShippingScheduledEndDate",
                    "eggFreezingScheduledEndDate",
                    "fertilityScheduledEndDate",
                    "generalWellnessScheduledEndDate",
                    "genericScheduledEndDate",
                    "parentingAndPediatricsScheduledEndDate",
                    "partnerFertilityScheduledEndDate",
                    "partnerNewparentScheduledEndDate",
                    "partnerPregnantScheduledEndDate",
                    "postpartumScheduledEndDate",
                    "pregnancyScheduledEndDate",
                    "pregnancylossScheduledEndDate",
                    "pregnancyOptionsScheduledEndDate",
                    "sponsoredScheduledEndDate",
                    "surrogacyScheduledEndDate",
                    "tryingToConceiveScheduledEndDate",
                    "menopauseScheduledEndDate",
                    "adoptionStartDate",
                    "breastMilkShippingStartDate",
                    "eggFreezingStartDate",
                    "fertilityStartDate",
                    "generalWellnessStartDate",
                    "genericStartDate",
                    "parentingAndPediatricsStartDate",
                    "partnerFertilityStartDate",
                    "partnerNewparentStartDate",
                    "partnerPregnantStartDate",
                    "postpartumStartDate",
                    "pregnancyStartDate",
                    "pregnancylossStartDate",
                    "pregnancyOptionsStartDate",
                    "sponsoredStartDate",
                    "surrogacyStartDate",
                    "tryingToConceiveStartDate",
                    "menopauseStartDate",
                    "activeTracks",
                    "isMultiTrack",
                ]
            },
        },
    }


@patch(
    "api.user_locale.services.locale_preference_service.LocalePreferenceService.get_preferred_locale_for_user"
)
def test_launchdarkly_context_practitioner_ca_verticals(
    mock_get_locale, client, api_helpers, practitioner_ca
):
    # Given
    user = practitioner_ca
    mock_get_locale.return_value = Locale("en", "US")
    # When
    res = client.get(launchdarkly_context_url, headers=api_helpers.json_headers(user))
    # Then
    assert res.status_code == 200
    assert res.json == {
        "kind": "multi",
        "monolith-health-profile": {
            "key": user.esp_id,
            "riskFactors": [],
            "_meta": {
                "privateAttributes": ["riskFactors", "fertilityTreatmentStatus"],
            },
        },
        "user": {
            "key": user.esp_id,
            "userId": user.id,
            "createdAt": user.created_at.isoformat(),
            "name": user.full_name,
            "email": user.email,
            "lowercaseEmail": user.email.lower(),
            "locale": "en",
            "country": "US",
            "roles": ["practitioner"],
            "verticals": ["Care Advocate"],
            "isEnterprise": False,
            "activeTracks": [],
            "isMultiTrack": False,
            "_meta": {
                "privateAttributes": [
                    "userId",
                    "createdAt",
                    "name",
                    "email",
                    "lowercaseEmail",
                    "locale",
                    "country",
                    "state",
                    "roles",
                    "verticals",
                    "isEnterprise",
                    "organizationId",
                    "adoptionCurrentPhase",
                    "breastMilkShippingCurrentPhase",
                    "eggFreezingCurrentPhase",
                    "fertilityCurrentPhase",
                    "generalWellnessCurrentPhase",
                    "genericCurrentPhase",
                    "parentingAndPediatricsCurrentPhase",
                    "partnerFertilityCurrentPhase",
                    "partnerNewparentCurrentPhase",
                    "partnerPregnantCurrentPhase",
                    "postpartumCurrentPhase",
                    "pregnancyCurrentPhase",
                    "pregnancylossCurrentPhase",
                    "pregnancyOptionsCurrentPhase",
                    "sponsoredCurrentPhase",
                    "surrogacyCurrentPhase",
                    "tryingToConceiveCurrentPhase",
                    "menopauseCurrentPhase",
                    "adoptionScheduledEndDate",
                    "breastMilkShippingScheduledEndDate",
                    "eggFreezingScheduledEndDate",
                    "fertilityScheduledEndDate",
                    "generalWellnessScheduledEndDate",
                    "genericScheduledEndDate",
                    "parentingAndPediatricsScheduledEndDate",
                    "partnerFertilityScheduledEndDate",
                    "partnerNewparentScheduledEndDate",
                    "partnerPregnantScheduledEndDate",
                    "postpartumScheduledEndDate",
                    "pregnancyScheduledEndDate",
                    "pregnancylossScheduledEndDate",
                    "pregnancyOptionsScheduledEndDate",
                    "sponsoredScheduledEndDate",
                    "surrogacyScheduledEndDate",
                    "tryingToConceiveScheduledEndDate",
                    "menopauseScheduledEndDate",
                    "adoptionStartDate",
                    "breastMilkShippingStartDate",
                    "eggFreezingStartDate",
                    "fertilityStartDate",
                    "generalWellnessStartDate",
                    "genericStartDate",
                    "parentingAndPediatricsStartDate",
                    "partnerFertilityStartDate",
                    "partnerNewparentStartDate",
                    "partnerPregnantStartDate",
                    "postpartumStartDate",
                    "pregnancyStartDate",
                    "pregnancylossStartDate",
                    "pregnancyOptionsStartDate",
                    "sponsoredStartDate",
                    "surrogacyStartDate",
                    "tryingToConceiveStartDate",
                    "menopauseStartDate",
                    "activeTracks",
                    "isMultiTrack",
                ]
            },
        },
    }


@patch(
    "api.user_locale.services.locale_preference_service.LocalePreferenceService.get_preferred_locale_for_user"
)
def test_launchdarkly_context_practitioner_with_prac_role_but_no_practitioner_profile(
    mock_get_locale, client, api_helpers, practitioner_ob_gyn, factories
):
    # Given
    user = practitioner_ob_gyn
    user.practitioner_profile = None
    user.roles = [factories.RoleFactory(name="practitioner")]
    mock_get_locale.return_value = Locale("en", "US")

    # When
    res = client.get(launchdarkly_context_url, headers=api_helpers.json_headers(user))

    # Then, verticals is not returned in the user context (see commented line for "verticals")
    assert res.status_code == 200
    assert res.json == {
        "kind": "multi",
        "monolith-health-profile": {
            "key": user.esp_id,
            "riskFactors": [],
            "_meta": {
                "privateAttributes": ["riskFactors", "fertilityTreatmentStatus"],
            },
        },
        "user": {
            "key": user.esp_id,
            "userId": user.id,
            "createdAt": user.created_at.isoformat(),
            "name": user.full_name,
            "email": user.email,
            "lowercaseEmail": user.email.lower(),
            "locale": "en",
            "country": "US",
            "roles": ["practitioner"],
            # "verticals": ["OB-GYN"],
            "isEnterprise": False,
            "activeTracks": [],
            "isMultiTrack": False,
            "_meta": {
                "privateAttributes": [
                    "userId",
                    "createdAt",
                    "name",
                    "email",
                    "lowercaseEmail",
                    "locale",
                    "country",
                    "state",
                    "roles",
                    "verticals",
                    "isEnterprise",
                    "organizationId",
                    "adoptionCurrentPhase",
                    "breastMilkShippingCurrentPhase",
                    "eggFreezingCurrentPhase",
                    "fertilityCurrentPhase",
                    "generalWellnessCurrentPhase",
                    "genericCurrentPhase",
                    "parentingAndPediatricsCurrentPhase",
                    "partnerFertilityCurrentPhase",
                    "partnerNewparentCurrentPhase",
                    "partnerPregnantCurrentPhase",
                    "postpartumCurrentPhase",
                    "pregnancyCurrentPhase",
                    "pregnancylossCurrentPhase",
                    "pregnancyOptionsCurrentPhase",
                    "sponsoredCurrentPhase",
                    "surrogacyCurrentPhase",
                    "tryingToConceiveCurrentPhase",
                    "menopauseCurrentPhase",
                    "adoptionScheduledEndDate",
                    "breastMilkShippingScheduledEndDate",
                    "eggFreezingScheduledEndDate",
                    "fertilityScheduledEndDate",
                    "generalWellnessScheduledEndDate",
                    "genericScheduledEndDate",
                    "parentingAndPediatricsScheduledEndDate",
                    "partnerFertilityScheduledEndDate",
                    "partnerNewparentScheduledEndDate",
                    "partnerPregnantScheduledEndDate",
                    "postpartumScheduledEndDate",
                    "pregnancyScheduledEndDate",
                    "pregnancylossScheduledEndDate",
                    "pregnancyOptionsScheduledEndDate",
                    "sponsoredScheduledEndDate",
                    "surrogacyScheduledEndDate",
                    "tryingToConceiveScheduledEndDate",
                    "menopauseScheduledEndDate",
                    "adoptionStartDate",
                    "breastMilkShippingStartDate",
                    "eggFreezingStartDate",
                    "fertilityStartDate",
                    "generalWellnessStartDate",
                    "genericStartDate",
                    "parentingAndPediatricsStartDate",
                    "partnerFertilityStartDate",
                    "partnerNewparentStartDate",
                    "partnerPregnantStartDate",
                    "postpartumStartDate",
                    "pregnancyStartDate",
                    "pregnancylossStartDate",
                    "pregnancyOptionsStartDate",
                    "sponsoredStartDate",
                    "surrogacyStartDate",
                    "tryingToConceiveStartDate",
                    "menopauseStartDate",
                    "activeTracks",
                    "isMultiTrack",
                ]
            },
        },
    }
