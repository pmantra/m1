from datetime import datetime
from unittest.mock import patch

import pytest

from admin.views.base import AdminCategory
from admin.views.models.users import VerticalView
from models.tracks.client_track import TrackModifiers
from models.verticals_and_specialties import Vertical
from pytests.freezegun import freeze_time
from storage.connection import db


@freeze_time("2023-11-16", tick=False)
@patch("flask_login.current_user")
def test_soft_delete(mock_current_user, client):
    vertical = Vertical(
        products=[{"minutes": 10, "price": 5}],
        name="foobar",
        pluralized_display_name="Foobar",
        long_description="desc",
    )
    db.session.add(vertical)
    db.session.commit()

    view = VerticalView.factory(category=AdminCategory.PRACTITIONER.value)
    view.delete_model(vertical)

    vertical = Vertical.query.get(vertical.id)
    assert datetime(2023, 11, 16) == vertical.deleted_at
    assert vertical.name.startswith("Deleted at 2023-11-16")

    view.delete_model(vertical)

    # Test idempotency
    vertical = Vertical.query.get(vertical.id)
    assert datetime(2023, 11, 16) == vertical.deleted_at
    assert vertical.name.startswith("Deleted at 2023-11-16")


@pytest.mark.parametrize(
    "vertical_name,track_modifiers,is_doula_only_accessible",
    [
        ("Fake Vertical", None, False),
        ("doula and childbirth educator", TrackModifiers.DOULA_ONLY, True),
        ("DOULA AND CHILDBIRTH EDUCATOR", TrackModifiers.DOULA_ONLY, True),
        ("Good Doula", None, False),
    ],
)
def test_has_access_with_track_modifiers(
    vertical_name,
    track_modifiers,
    is_doula_only_accessible,
    factories,
):
    # given
    vertical = Vertical(
        products=[{"minutes": 10, "price": 5}],
        name=vertical_name,
        pluralized_display_name=vertical_name,
        long_description="desc",
    )
    db.session.add(vertical)
    db.session.commit()

    # create a VerticalAccessByTrack record to allow vertical <> client track interaction
    client_track_id = 1

    factories.VerticalAccessByTrackFactory.create(
        client_track_id=client_track_id,
        vertical_id=vertical.id,
        track_modifiers=track_modifiers,
    )

    # when / then
    assert (
        vertical.has_access_with_track_modifiers(
            track_modifiers=[track_modifiers], client_track_id=client_track_id
        )
        == is_doula_only_accessible
    )
