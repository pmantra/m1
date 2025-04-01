import pytest

from models.tracks import TrackConfig, TrackName


@pytest.mark.parametrize(argnames="name", argvalues=[*TrackName])
def test_from_name(name: TrackName):
    TrackConfig.from_name(name)
