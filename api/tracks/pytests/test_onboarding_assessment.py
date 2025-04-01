import pytest

from models.tracks import TrackName
from models.tracks.assessment import AssessmentTrack


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_legacy_onboarding_assessment_id(client, api_helpers, factories):
    factories.AssessmentLifecycleTrackFactory.create(
        track_name=TrackName.PREGNANCY, assessment_versions=[1]
    )
    user = factories.EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)
    expected_assessment = user.active_tracks[
        0
    ].onboarding_assessment_lifecycle.latest_assessment
    response = client.get("/api/v1/me", headers=api_helpers.standard_headers(user))
    res = api_helpers.load_json(response)
    assert res["active_tracks"][0]["onboarding_assessment_slug"] is None
    assert res["active_tracks"][0]["onboarding_assessment_id"] == expected_assessment.id


@pytest.mark.usefixtures("patch_user_id_encoded_token")
def test_assessment_transition_from_legacy_to_hdc(client, api_helpers, factories, db):
    factories.AssessmentLifecycleTrackFactory.create(
        track_name=TrackName.PREGNANCY, assessment_versions=[1]
    )
    user = factories.EnterpriseUserFactory.create(tracks__name=TrackName.PREGNANCY)
    expected_assessment = user.active_tracks[
        0
    ].onboarding_assessment_lifecycle.latest_assessment
    track_relationship = AssessmentTrack(
        assessment_onboarding_slug="test-slug", track_name=TrackName.PREGNANCY
    )
    db.session.add(track_relationship)
    db.session.commit()
    response = client.get("/api/v1/me", headers=api_helpers.standard_headers(user))
    res = api_helpers.load_json(response)
    assert res["active_tracks"][0]["onboarding_assessment_slug"] == "test-slug"
    assert res["active_tracks"][0]["onboarding_assessment_id"] == expected_assessment.id
