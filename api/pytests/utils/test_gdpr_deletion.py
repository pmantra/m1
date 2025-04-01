from datetime import date, datetime, timedelta
from unittest import mock

import pytest as pytest

from models.tracks import TrackName
from models.tracks.member_track import MemberTrack, MemberTrackPhaseReporting
from pytests.utils.conftest import GDPR_INITIATOR_USER_ID
from storage.connection import db
from utils.gdpr_deletion import GDPRDeleteUser
from wallet.models.constants import WalletUserStatus, WalletUserType


def test_gdpr_update_member_track(factories, gdpr_delete_permission, app_context):
    initiator = factories.DefaultUserFactory.create(id=GDPR_INITIATOR_USER_ID)
    user = factories.DefaultUserFactory.create(id=1, email="abc@test.com")
    factories.GDPRUserRequestFactory.create(
        id=GDPR_INITIATOR_USER_ID, user_id=1, user_email="abc@test.com"
    )
    factories.GDPRDeletionBackupFactory.create(user_id=1)

    factories.MemberTrackFactory.create(
        id=1,
        user=user,
        name=TrackName.PREGNANCY,
        transitioning_to=TrackName.POSTPARTUM,
        anchor_date=datetime.utcnow().date() - timedelta(days=400),
    )
    factories.MemberTrackFactory.create(
        id=2,
        user=user,
        name=TrackName.PREGNANCY,
        transitioning_to=TrackName.POSTPARTUM,
        anchor_date=datetime.utcnow().date() - timedelta(days=100),
    )

    factories.MemberTrackPhaseFactory.create(
        member_track_id=1,
        started_at=datetime.utcnow().date() - timedelta(days=100),
        ended_at=datetime.utcnow().date() - timedelta(days=50),
    )

    mts = (
        db.session.query(MemberTrack)
        .filter(MemberTrack.user_id == 1, (MemberTrack.anchor_date is not None))
        .all()
    )
    assert len(mts) > 0
    requested_date = date(2023, 4, 11)
    op = GDPRDeleteUser(initiator, user, requested_date)
    op.delete()
    for mt in mts:
        assert mt.user_id is None
        assert mt.anchor_date is None

    mtps = (
        db.session.query(MemberTrackPhaseReporting)
        .filter(MemberTrackPhaseReporting.member_track_id == 1)
        .all()
    )
    for mtp in mtps:
        assert mtp.ended_at is None


def test_get_head_multiple_users_share_same_image(factories, gdpr_delete_permission):
    initiator = factories.DefaultUserFactory.create(id=GDPR_INITIATOR_USER_ID)
    factories.ImageFactory.create(id=1)
    user1 = factories.DefaultUserFactory.create(id=1, email="u1@test.com", image_id=1)
    factories.DefaultUserFactory.create(id=2, email="u2@test.com", image_id=1)
    factories.GDPRUserRequestFactory.create(
        id=GDPR_INITIATOR_USER_ID, user_id=1, user_email="u1@test.com"
    )
    requested_date = date(2023, 4, 11)
    op = GDPRDeleteUser(initiator, user1, requested_date)
    head = op._get_gdpr_deletion_head_table()
    assert head == "user"


@pytest.fixture(autouse=True, scope="function")
def delete_image_file(factories):
    with mock.patch("utils.gdpr_deletion.delete_image_file") as d:
        yield d


def test_get_head_one_user_one_image(
    factories, gdpr_delete_permission, delete_image_file, app_context
):
    initiator = factories.DefaultUserFactory.create(id=GDPR_INITIATOR_USER_ID)
    factories.ImageFactory.create(id=1)
    user1 = factories.DefaultUserFactory.create(id=1, email="u1@test.com", image_id=1)
    factories.GDPRUserRequestFactory.create(
        id=GDPR_INITIATOR_USER_ID, user_id=1, user_email="u1@test.com"
    )
    requested_date = date(2023, 4, 11)
    op = GDPRDeleteUser(initiator, user1, requested_date)
    head = op._get_gdpr_deletion_head_table()
    assert head == "image"
    op.delete()
    assert delete_image_file.called


def test_get_head_user_image_id_is_none(factories, gdpr_delete_permission):
    initiator = factories.DefaultUserFactory.create(id=GDPR_INITIATOR_USER_ID)
    factories.ImageFactory.create(id=1)
    user1 = factories.DefaultUserFactory.create(
        id=1, email="u1@test.com", image_id=None
    )
    factories.GDPRUserRequestFactory.create(
        id=GDPR_INITIATOR_USER_ID, user_id=1, user_email="u1@test.com"
    )
    requested_date = date(2023, 4, 11)
    op = GDPRDeleteUser(initiator, user1, requested_date)
    head = op._get_gdpr_deletion_head_table()
    assert head == "user"


def test_gdpr_update_organization_employee(factories, gdpr_delete_permission):
    initiator = factories.DefaultUserFactory.create(id=GDPR_INITIATOR_USER_ID)
    user = factories.DefaultUserFactory.create(id=1, email="abc@test.com")
    factories.GDPRUserRequestFactory.create(
        id=GDPR_INITIATOR_USER_ID, user_id=1, user_email="abc@test.com"
    )
    oe = factories.OrganizationEmployeeFactory.create(
        email="abc@test.com", alegeus_id="fake_alegeus_id"
    )
    requested_date = date(2023, 4, 11)
    op = GDPRDeleteUser(initiator, user, requested_date)
    oe_data = op._get_items_dict(oe)
    assert oe.alegeus_id == "fake_alegeus_id"
    original_organization_employees, _ = op._update_organization_employee()
    assert oe.alegeus_id is None
    assert oe.email is None
    assert len(original_organization_employees) == 1
    original_organization_employee = original_organization_employees[0]
    assert original_organization_employee["table"] == "organization_employee"
    assert original_organization_employee["foreign_key"]["column"] == "email"
    assert original_organization_employee["foreign_key"]["value"] == user.email
    assert original_organization_employee["data"] == oe_data[0]


def test_gdpr_update_channel_table(factories, gdpr_delete_permission, app_context):
    initiator = factories.DefaultUserFactory.create(id=GDPR_INITIATOR_USER_ID)
    user = factories.DefaultUserFactory.create(
        id=1, email="abc@test.com", first_name="Alibaba"
    )
    factories.GDPRUserRequestFactory.create(
        id=GDPR_INITIATOR_USER_ID, user_id=1, user_email=user.email
    )
    factories.OrganizationFactory.create(id=1)
    resource = factories.ResourceFactory(id=5)
    reimbursement_organization_settings = (
        factories.ReimbursementOrganizationSettingsFactory(
            id=6,
            organization_id=1,
            benefit_faq_resource_id=resource.id,
            survey_url="fake_url",
        )
    )

    channel_1 = factories.ChannelFactory.create(
        id=1, name=user.first_name + " & Bob", comment="Fake comment."
    )

    channel_2 = factories.ChannelFactory.create(
        id=2, name=user.first_name + " & Bill", comment="Fake comment."
    )

    factories.ReimbursementWalletFactory.create(
        id=1,
        user_id=user.id,
        reimbursement_organization_settings_id=reimbursement_organization_settings.id,
    )

    factories.ReimbursementWalletFactory.create(
        id=2,
        user_id=user.id,
        reimbursement_organization_settings_id=reimbursement_organization_settings.id,
    )

    factories.ReimbursementWalletUsersFactory.create(
        id=1,
        user_id=user.id,
        channel_id=channel_1.id,
        reimbursement_wallet_id=1,
        type=WalletUserType.EMPLOYEE,
        status=WalletUserStatus.PENDING,
    )

    factories.ReimbursementWalletUsersFactory.create(
        id=2,
        user_id=user.id,
        channel_id=channel_2.id,
        reimbursement_wallet_id=2,
        type=WalletUserType.EMPLOYEE,
        status=WalletUserStatus.PENDING,
    )

    requested_date = date(2023, 4, 11)
    op = GDPRDeleteUser(initiator, user, requested_date)
    op.delete()

    assert channel_1.name == "_gdpr_user_name & Bob"
    assert channel_1.comment == "GDPR delete."

    assert channel_2.name == "_gdpr_user_name & Bill"
    assert channel_2.comment == "GDPR delete."


def test_create_dict_for_backup(factories, gdpr_delete_permission):
    initiator = factories.DefaultUserFactory.create(id=GDPR_INITIATOR_USER_ID)
    user = factories.DefaultUserFactory.create(id=1, email="abc@test.com")
    factories.GDPRUserRequestFactory.create(
        id=GDPR_INITIATOR_USER_ID, user_id=1, user_email="abc@test.com"
    )
    requested_date = date(2023, 4, 11)
    op = GDPRDeleteUser(initiator, user, requested_date)
    backup_dict = op._create_dict_for_backup(
        "test_table", "test_column_name", "test_column_value", {}
    )
    assert backup_dict == {
        "table": "test_table",
        "foreign_key": {"column": "test_column_name", "value": "test_column_value"},
        "data": {},
    }
