import json
from unittest import mock

import pytest

from models.profiles import CareTeamTypes
from models.verticals_and_specialties import Vertical
from pytests.db_util import enable_db_performance_warnings
from pytests.factories import (
    DefaultUserFactory,
    EnterpriseUserFactory,
    MemberPractitionerAssociationFactory,
    PractitionerUserFactory,
    VerticalFactory,
)
from storage.connection import db


def test_get_care_team(client, api_helpers, db):
    user_1 = DefaultUserFactory()
    prac1 = PractitionerUserFactory.create()
    prac2 = PractitionerUserFactory.create()
    MemberPractitionerAssociationFactory(
        user_id=user_1.id,
        type=CareTeamTypes.APPOINTMENT,
        practitioner_id=prac1.id,
    )
    MemberPractitionerAssociationFactory(
        user_id=user_1.id,
        type=CareTeamTypes.QUIZ,
        practitioner_id=prac2.id,
    )

    with enable_db_performance_warnings(database=db, failure_threshold=26):
        res = client.get(
            f"/api/v1/users/{user_1.id}/care_team",
            headers=api_helpers.json_headers(user_1),
        )
        assert res.status_code, 200


@pytest.mark.parametrize("is_doula_only_track", [True, False])
@mock.patch("maven.feature_flags.bool_variation")
def test_get_care_team__can_member_interact__doula_member(
    mock_feature_flag,
    is_doula_only_track,
    client,
    api_helpers,
    factories,
):
    # given
    mock_feature_flag.return_value = True
    user = EnterpriseUserFactory()
    track_modifiers = "doula_only" if is_doula_only_track else None
    client_track = factories.ClientTrackFactory.create(
        track="pregnancy", track_modifiers=track_modifiers
    )
    factories.MemberTrackFactory.create(user=user, client_track=client_track)
    prac = PractitionerUserFactory.create(
        practitioner_profile__verticals=[VerticalFactory.create(name="OB-GYN")]
    )

    client_track_id = client_track.id

    # get the assigned care advocate id
    ca_vertical = (
        db.session.query(Vertical).filter(Vertical.name == "Care Advocate").one()
    )

    # create a VerticalAccessByTrack record to allow vertical <> client track interaction
    factories.VerticalAccessByTrackFactory.create(
        client_track_id=client_track_id,
        vertical_id=ca_vertical.id,
        track_modifiers=track_modifiers,
    )

    user.add_practitioner_to_care_team(prac.id, CareTeamTypes.APPOINTMENT)

    # when
    res = client.get(
        f"/api/v1/users/{user.id}/care_team",
        headers=api_helpers.json_headers(user),
    )
    # then
    assert res.status_code, 200
    res_data = json.loads(res.data)
    if is_doula_only_track:
        assert not res_data["data"][0]["profiles"]["practitioner"][
            "can_member_interact"
        ]
        assert res_data["data"][1]["profiles"]["practitioner"]["can_member_interact"]
    else:
        assert res_data["data"][0]["profiles"]["practitioner"]["can_member_interact"]
        assert res_data["data"][1]["profiles"]["practitioner"]["can_member_interact"]


@mock.patch("views.schemas.common.should_enable_can_member_interact")
@pytest.mark.parametrize("can_interact_flag_value", [True, False])
def test_get_care_team__can_member_interact__marketplace_member(
    should_enable_can_member_interact,
    can_interact_flag_value,
    client,
    api_helpers,
):
    # given
    should_enable_can_member_interact.return_value = can_interact_flag_value
    user = DefaultUserFactory.create()
    prac = PractitionerUserFactory.create(
        practitioner_profile__verticals=[VerticalFactory.create(name="OB-GYN")]
    )
    user.add_practitioner_to_care_team(prac.id, CareTeamTypes.APPOINTMENT)

    # when
    res = client.get(
        f"/api/v1/users/{user.id}/care_team",
        headers=api_helpers.json_headers(user),
    )
    # then
    assert res.status_code, 200
    res_data = json.loads(res.data)

    assert res_data["data"][0]["profiles"]["practitioner"]["can_member_interact"]
