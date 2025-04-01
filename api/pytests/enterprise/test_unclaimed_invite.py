from datetime import datetime, timedelta

from models.enterprise import InviteType
from pytests.freezegun import freeze_time


def test_get_unclaimed_invite(client, api_helpers, default_user, factories):
    invite = factories.InviteFactory.create(
        created_by_user=default_user,
        email="test@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=False,
    )

    res = client.get(
        "/api/v1/invite/unclaimed",
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 200
    assert res.json["invite_id"] == invite.id
    assert res.json["type"] == invite.type
    assert res.json["email"] == invite.email


def test_get_unclaimed_invite_when_already_claimed(
    client, api_helpers, default_user, factories
):
    factories.InviteFactory.create(
        created_by_user=default_user,
        email="test@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_EMPLOYEE,
        claimed=True,
    )

    res = client.get(
        "/api/v1/invite/unclaimed",
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 404


def test_get_unclaimed_invite_when_multiple_unclaimed(
    client, api_helpers, default_user, factories
):
    with freeze_time(datetime.now() - timedelta(hours=1)):
        factories.InviteFactory.create(
            created_by_user=default_user,
            email="first@mavenclinic.com",
            name=default_user.first_name,
            type=InviteType.FILELESS_EMPLOYEE,
            claimed=False,
        )

    second_invite = factories.InviteFactory.create(
        created_by_user=default_user,
        email="second@mavenclinic.com",
        name=default_user.first_name,
        type=InviteType.FILELESS_DEPENDENT,
        claimed=False,
    )

    res = client.get(
        "/api/v1/invite/unclaimed",
        headers=api_helpers.standard_headers(default_user),
    )

    assert res.status_code == 200
    assert res.json["invite_id"] == second_invite.id
    assert res.json["type"] == second_invite.type
    assert res.json["email"] == second_invite.email
