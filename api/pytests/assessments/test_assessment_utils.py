import pytest

from models.tracks.track import TrackName
from utils.user_assessments import (
    get_latest_track_assessments_for_user,
    get_user_track_and_started_needs_assessments,
)

TRACK_1 = TrackName.PREGNANCY
TRACK_2 = TrackName.BREAST_MILK_SHIPPING
SEPARATE_TRACK = TrackName.SURROGACY


@pytest.fixture()
def multiple_test_track(factories, track_1):
    return factories.AssessmentLifecycleTrackFactory.create(
        track_name=track_1.name, assessment_versions=[1, 2]
    )


@pytest.fixture()
def single_test_track(factories, track_2):
    return factories.AssessmentLifecycleTrackFactory.create(
        track_name=track_2.name, assessment_versions=[4]
    )


@pytest.fixture()
def unrelated_track(factories):
    return factories.AssessmentLifecycleTrackFactory.create(
        track_name=SEPARATE_TRACK, assessment_versions=[1]
    )


@pytest.fixture()
def track_1(factories):
    user = factories.DefaultUserFactory.create()
    return factories.MemberTrackFactory(user=user, name=TRACK_1)


@pytest.fixture()
def track_2(factories, track_1):
    return factories.MemberTrackFactory(
        name=TRACK_2,
        user=track_1.user,
        client_track=track_1.client_track,
    )


@pytest.fixture()
def two_track_user(factories, track_2):
    return track_2.user


class TestLatestTrackAssessment:
    def test_latest_track_assessments(
        self, two_track_user, single_test_track, multiple_test_track
    ):

        latest_track_assessments = get_latest_track_assessments_for_user(two_track_user)
        latest_user_assessments = [
            lc.assessment_lifecycle.latest_assessment
            for lc in [single_test_track, multiple_test_track]
        ]
        assert set(latest_user_assessments) == set(latest_track_assessments)

    def test_user_track_assessments(
        self,
        factories,
        two_track_user,
        single_test_track,
        multiple_test_track,
        unrelated_track,
    ):
        # Create an assessment that is not associated with the existing tracks

        additional_needs_assessment = factories.NeedsAssessmentFactory(
            user=two_track_user,
            assessment_template=unrelated_track.assessment_lifecycle.latest_assessment,
        )

        # Add a completed version of an earlier assessment
        early_version_assessment = multiple_test_track.assessment_lifecycle.assessments[
            0
        ]
        early_version_needs_assessment = factories.NeedsAssessmentFactory(
            user=two_track_user, assessment_template=early_version_assessment
        )

        (
            started_assessments,
            track_assessments,
        ) = get_user_track_and_started_needs_assessments(two_track_user)
        expected_track_list = [single_test_track.assessment_lifecycle.latest_assessment]
        expected_started_assessment = [
            early_version_needs_assessment,
            additional_needs_assessment,
        ]

        assert set(started_assessments) == set(expected_started_assessment)
        assert set(expected_track_list) == set(track_assessments)
