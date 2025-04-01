import pytest

from models.tracks import TrackName
from models.tracks.resources import (
    get_connected_content_for_track_phases,
    get_resources_for_track,
    get_resources_for_track_phase,
)


@pytest.mark.parametrize(
    "track_name, expected_resource_num",
    [
        (TrackName.PREGNANCY, 3),
        (TrackName.POSTPARTUM, 2),
    ],
)
def test_get_resources_for_track(track_name, expected_resource_num, factories):
    factories.ResourceFactory.create_batch(expected_resource_num, tracks=[track_name])
    resources = get_resources_for_track(track_name)
    assert len(resources) == expected_resource_num


@pytest.mark.parametrize(
    "track_name, phase_name, expected_resource_num",
    [
        (TrackName.PREGNANCY, "week-33", 1),
        (TrackName.POSTPARTUM, "week-66", 1),
    ],
)
def test_get_resources_for_track_phase(
    track_name, phase_name, expected_resource_num, factories
):
    factories.ResourceFactory.create_batch(
        expected_resource_num,
        phases=[(track_name, phase_name)],
    )
    resources = get_resources_for_track_phase(track_name, phase_name)
    assert len(resources) == expected_resource_num


@pytest.mark.parametrize(
    "track_name, phase_name, expected_resource_num",
    [
        (TrackName.PREGNANCY, "week-11", 1),
        (TrackName.POSTPARTUM, "week-11", 1),
    ],
)
def test_get_connected_content_for_track_phases(
    track_name, phase_name, expected_resource_num, factories
):
    factories.ResourceFactory.create_batch(
        expected_resource_num,
        connected_content_phases=[(track_name, phase_name)],
    )
    resources = get_connected_content_for_track_phases(track_name, phase_name)
    assert len(resources) == expected_resource_num
