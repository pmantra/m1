from __future__ import annotations

import dataclasses

import pytest
import wtforms

from admin.views.base import AdminCategory
from admin.views.models.enterprise import OrganizationView
from models.tracks import ClientTrack, TrackName


@dataclasses.dataclass
class FakeOrganizationModel:
    __slots__ = ("client_tracks",)

    client_tracks: list[ClientTrack]


def test_organization_prevents_deprecated_client_tracks(factories):
    deprecated_client_track = factories.ClientTrackFactory(
        track=TrackName.TRYING_TO_CONCEIVE,
        active=True,
    )
    view = OrganizationView.factory(category=AdminCategory.ENTERPRISE.value)
    form = view.create_form()
    fake_model = FakeOrganizationModel(client_tracks=[deprecated_client_track])

    with pytest.raises(wtforms.validators.ValidationError):
        view.on_model_change(form, fake_model, True)


def test_organization_allows_available_client_tracks(factories):
    deprecated_client_track = factories.ClientTrackFactory(
        track=TrackName.PREGNANCY,
        active=True,
    )
    view = OrganizationView.factory(category=AdminCategory.ENTERPRISE.value)
    form = view.create_form()
    fake_model = FakeOrganizationModel(client_tracks=[deprecated_client_track])

    with pytest.raises(Exception) as e:
        view.on_model_change(form, fake_model, True)

        assert e is not wtforms.validators.ValidationError


def test_organization_populates_expected_client_tracks():
    view = OrganizationView.factory(category=AdminCategory.ENTERPRISE.value)
    form = view.create_form()

    default_client_tracks = [ct["track"] for ct in form.client_tracks.data]

    assert TrackName.ADOPTION in default_client_tracks
    assert TrackName.PARTNER_FERTILITY not in default_client_tracks
    assert TrackName.TRYING_TO_CONCEIVE not in default_client_tracks
