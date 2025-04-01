from unittest import mock
from unittest.mock import MagicMock, call, patch

import pytest
from redset.locks import LockTimeout
from zenpy.lib.api_objects import Organization as ZDOrganization
from zenpy.lib.api_objects import Ticket as ZDTicket
from zenpy.lib.api_objects import User as ZDUser

from common.constants import Environment
from messaging.services.zendesk import (
    EnterpriseValidationZendeskTicket,
    MessagingZendeskTicket,
    PostSessionZendeskTicket,
    ReconciliationZendeskTicket,
    SynchronizedZendeskTicket,
    _generate_cx_channel_id_tag,
    _generate_org_name_tag,
    enable_set_user_need_if_solving_ticket,
    filter_client_tracks,
    find_zendesk_comment_that_matches_message,
    get_cx_tags,
    get_or_create_zenpy_user,
    get_user_need_custom_field_id,
    merge_zendesk_profiles,
    namespace_subject,
    reconcile_zendesk_comment_id,
    reconcile_zendesk_comment_id_job_locks,
    send_general_ticket_to_zendesk,
    update_zendesk_org,
    update_zendesk_user,
    update_zendesk_user_job_lock,
)
from messaging.services.zendesk_client import (
    IdentityType,
    ZendeskAPIEmailAlreadyExistsException,
)
from messaging.services.zendesk_models import ZendeskClientTrack, ZendeskTrackName
from storage.connection import db


class TestGetOrCreateZenpyUser:
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.create_or_update_user")
    def test_get_or_create_zenpy_user__user_has_no_zendesk_user_id(
        self, mock_zd_client_create_or_update, default_user, factories
    ):

        # Mock response of create_or_update_user
        mocked_zd_user_id = 100
        mocked_zd_user = mock.MagicMock(id=mocked_zd_user_id)
        mock_zd_client_create_or_update.return_value = mocked_zd_user

        # Given a user with no zendesk_user_id
        default_user.zendesk_user_id = None
        # and given a user that already has mocked_zd_user as their zd user
        another_user = factories.DefaultUserFactory()
        another_user.zendesk_user_id = mocked_zd_user_id

        # When calling get or create
        returned_zd_user = get_or_create_zenpy_user(default_user)

        # Then the mocked zd user is returned, the another user looses the reference to it
        mock_zd_client_create_or_update.assert_called_once_with(
            default_user, called_by="Not set"
        )
        assert not another_user.zendesk_user_id
        assert default_user.zendesk_user_id == mocked_zd_user_id
        assert returned_zd_user == mocked_zd_user

    @mock.patch("messaging.services.zendesk_client.ZendeskClient.create_or_update_user")
    def test_get_or_create_zenpy_user__user_has_zendesk_user_id_and_not_validating_it(
        self, mock_zd_client_create_or_update, default_user, factories
    ):

        # Given a user with zendesk_user_id
        zendesk_user_id = 100
        default_user.zendesk_user_id = zendesk_user_id

        # When calling get or create with no validation
        returned_zd_user = get_or_create_zenpy_user(default_user)

        # Then
        # Returned zd user's id has same id as the user's zendesk_user_id
        assert default_user.zendesk_user_id == returned_zd_user.id
        # Reference to zd user does not change
        assert default_user.zendesk_user_id == zendesk_user_id
        # Create or update mock is not called
        assert not mock_zd_client_create_or_update.called

    @mock.patch(
        "messaging.services.zendesk.enable_validate_existing_zendesk_user_id",
        return_value=True,
    )
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.get_zendesk_user")
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.create_or_update_user")
    def test_get_or_create_zenpy_user__user_has_zendesk_user_id_and_id_validation_passes(
        self,
        mock_zd_client_create_or_update,
        mock_zd_client_get_zendesk_user,
        default_user,
        factories,
    ):

        # Given a user with zendesk_user_id, get_zendesk_user finds user
        zendesk_user_id = 100
        default_user.zendesk_user_id = zendesk_user_id
        mocked_zd_user = mock.MagicMock(id=zendesk_user_id)
        mock_zd_client_get_zendesk_user.return_value = mocked_zd_user

        # When calling get or create with validation
        returned_zd_user = get_or_create_zenpy_user(
            default_user, validate_existing_zendesk_user_id=True
        )

        # Then
        mock_zd_client_get_zendesk_user.assert_called_once_with(
            zendesk_user_id=str(default_user.zendesk_user_id)
        )
        # Returned zd user's id has same id as the user's zendesk_user_id
        assert default_user.zendesk_user_id == returned_zd_user.id
        # Reference to zd user does not change
        assert default_user.zendesk_user_id == zendesk_user_id
        # Create or update mock is not called
        assert not mock_zd_client_create_or_update.called

    @mock.patch(
        "messaging.services.zendesk.enable_validate_existing_zendesk_user_id",
        return_value=True,
    )
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.get_zendesk_user")
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.create_or_update_user")
    def test_get_or_create_zenpy_user__user_has_zendesk_user_id_and_only_email_validation_passes(
        self,
        mock_zd_client_create_or_update,
        mock_zd_client_get_zendesk_user,
        default_user,
        factories,
    ):

        # Given a user with wrong zendesk_user_id
        old_zendesk_user_id = 99
        new_zendesk_user_id = 100
        default_user.zendesk_user_id = old_zendesk_user_id
        mocked_zd_user = mock.MagicMock(id=new_zendesk_user_id)
        # get_zendesk_user fails on first try (search by id), but finds ZD user by email (second try)
        mock_zd_client_get_zendesk_user.side_effect = [None, mocked_zd_user]
        # and given a user that already has mocked_zd_user as their zd user
        another_user = factories.DefaultUserFactory()
        another_user.zendesk_user_id = mocked_zd_user.id

        # When calling get or create with validation
        returned_zd_user = get_or_create_zenpy_user(
            default_user, validate_existing_zendesk_user_id=True
        )

        # Then
        assert mock_zd_client_get_zendesk_user.call_count == 2
        mock_zd_client_get_zendesk_user.assert_has_calls(
            [
                call(zendesk_user_id=str(old_zendesk_user_id)),
                call(zendesk_user_email=default_user.email),
            ],
            any_order=False,
        )
        # another_user looses the reference to the zendesk_user_id
        assert not another_user.zendesk_user_id
        # default_user has reference to the new zendesk_user_id
        assert default_user.zendesk_user_id == new_zendesk_user_id
        # and its the same as the zd user returned
        assert default_user.zendesk_user_id == returned_zd_user.id
        # and create or update mock is not called
        assert not mock_zd_client_create_or_update.called

    @mock.patch(
        "messaging.services.zendesk.enable_validate_existing_zendesk_user_id",
        return_value=True,
    )
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.get_zendesk_user")
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.create_or_update_user")
    def test_get_or_create_zenpy_user__user_has_zendesk_user_id_and_id_and_email_validation_fail(
        self,
        mock_zd_client_create_or_update,
        mock_zd_client_get_zendesk_user,
        default_user,
        factories,
    ):

        # Given a user with wrong zendesk_user_id
        old_zendesk_user_id = 99
        new_zendesk_user_id = 100
        default_user.zendesk_user_id = old_zendesk_user_id
        mocked_zd_user = mock.MagicMock(id=new_zendesk_user_id)
        # get_zendesk_user fails on all tries
        mock_zd_client_get_zendesk_user.return_value = None
        mock_zd_client_create_or_update.return_value = mocked_zd_user
        # and given a user that already has mocked_zd_user as their zd user
        another_user = factories.DefaultUserFactory()
        another_user.zendesk_user_id = mocked_zd_user.id

        # When calling get or create with validation
        returned_zd_user = get_or_create_zenpy_user(
            default_user, validate_existing_zendesk_user_id=True
        )

        # Then
        assert mock_zd_client_get_zendesk_user.call_count == 2
        mock_zd_client_get_zendesk_user.assert_has_calls(
            [
                call(zendesk_user_id=str(old_zendesk_user_id)),
                call(zendesk_user_email=default_user.email),
            ],
            any_order=False,
        )
        # create or update mock is called
        mock_zd_client_create_or_update.assert_called_once_with(
            default_user,
            called_by="Not set",
        )
        # another_user looses the reference to the zendesk_user_id
        assert not another_user.zendesk_user_id
        # default_user has reference to the new zendesk_user_id
        assert default_user.zendesk_user_id == new_zendesk_user_id
        # and its the same as the zd user returned
        assert default_user.zendesk_user_id == returned_zd_user.id


class TestZendesk:
    def test_subclass_setter_override(self, factories):
        member = factories.MemberFactory.create()
        message = factories.MessageFactory.create()

        mzdt = MessagingZendeskTicket(
            message=message,
            initial_cx_message=False,
        )
        with pytest.raises(AttributeError):
            mzdt.member = member

    def test_enable_set_user_need_if_solving_ticket__ff_on(
        self, enable_set_user_need_if_solving_ticket_ff_on
    ):
        # Given
        ticket = ZDTicket()

        # When
        ff_on = enable_set_user_need_if_solving_ticket(ticket)

        assert ff_on

    def test_enable_set_user_need_if_solving_ticket__ff_off(
        self, enable_set_user_need_if_solving_ticket_ff_off
    ):
        # Given
        ticket = ZDTicket()

        # When
        ff_on = enable_set_user_need_if_solving_ticket(ticket)

        assert not ff_on

    @pytest.mark.parametrize(
        argnames="env", argvalues=[Environment.QA2, Environment.PRODUCTION]
    )
    @patch("messaging.services.zendesk.Environment.current")
    def test_get_user_need_custom_field_id(self, mock_current_env, env):

        # Given
        mock_current_env.return_value = env

        # When
        need_custom_field_id = get_user_need_custom_field_id()

        # Then
        expected_need_custom_field_id = (
            31873516408723 if env == Environment.PRODUCTION else 32089765770643
        )

        assert need_custom_field_id == expected_need_custom_field_id

    @mock.patch("messaging.services.zendesk_client.ZendeskClient.get_zendesk_user")
    @mock.patch("messaging.services.zendesk.log.warning")
    def test_update_zendesk_user__user_does_not_exists(
        self,
        mock_log_warn,
        mock_get_zendesk_user,
        factories,
    ):
        # Given
        invalid_user_id = 10

        # When
        update_zendesk_user(user_id=invalid_user_id)

        # Then
        mock_log_warn.assert_called_once_with(
            "Could not updated Zendesk User Profile. Could not find user.",
            user_id=invalid_user_id,
        )
        mock_get_zendesk_user.assert_not_called()

    @pytest.mark.parametrize("identity", [IdentityType.EMAIL, IdentityType.PHONE, "NA"])
    @mock.patch("messaging.services.zendesk.log.info")
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.get_zendesk_user")
    @mock.patch(
        "messaging.services.zendesk_client.ZendeskClient.update_primary_identity"
    )
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.update_user")
    def test_update_zendesk_user__zd_user_exists(
        self,
        mock_update_user,
        mock_update_primary_identity,
        mock_get_zendesk_user,
        mock_log_info,
        identity,
        factories,
    ):
        # Given a user with updated attributes
        zendesk_user_id = 100
        new_email = "new_EmaiL@gmail.com"
        new_phone = "tel:773-322-0947"
        new_first_name = "new"
        new_last_name = "name"

        user = factories.MemberFactory.create(
            email=new_email,
            first_name=new_first_name,
            last_name=new_last_name,
            zendesk_user_id=zendesk_user_id,
        )
        user.member_profile.phone_number = new_phone

        # and a respective ZD account that has old user data
        old_external_id = None
        old_email = "old_email@gmail.com"
        old_phone = "tel:555-555-5555"
        old_name = "old name"
        zd_user = ZDUser(
            id=zendesk_user_id,
            external_id=old_external_id,
            email=old_email,
            phone=old_phone,
            name=old_name,
        )

        # mock the response of ZD API to get this zd user
        mock_get_zendesk_user.return_value = zd_user

        # When
        update_zendesk_user(user_id=user.id, update_identity=identity)

        # Then
        # The attrs are updated in the zd user object
        assert zd_user.external_id == user.id
        assert zd_user.email == new_email.lower()
        assert zd_user.name == user.full_name
        assert zd_user.phone == "+17733220947"  # new phone in ZD format

        # If the update is relative to an email update, we update the primary identity
        if identity == IdentityType.EMAIL:
            mock_update_primary_identity.assert_called_once()
        else:
            mock_update_primary_identity.assert_not_called()

        # The call to ZD to make the update happens
        mock_update_user.assert_called_once_with(
            user_id=str(user.id),
            zendesk_user=zd_user,
        )
        mock_log_info.assert_called_once_with(
            "Zendesk Profile updated for user",
            user_id=user.id,
            zendesk_user_id=user.zendesk_user_id,
            update_identity=identity,
        )

    @mock.patch("messaging.services.zendesk.log.warning")
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.get_zendesk_user")
    @mock.patch(
        "messaging.services.zendesk_client.ZendeskClient.update_primary_identity"
    )
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.update_user")
    def test_update_zendesk_user__zd_user_does_not_exist(
        self,
        mock_update_user,
        mock_update_primary_identity,
        mock_get_zendesk_user,
        mock_log_warning,
        factories,
    ):
        # Given

        user = factories.DefaultUserFactory.create()
        zd_user = ZDUser(id=1)
        user.zendesk_user_id = zd_user.id
        db.session.commit()

        mock_get_zendesk_user.return_value = None

        # When
        update_zendesk_user(user_id=user.id)

        # Then
        mock_update_user.assert_not_called()
        mock_log_warning.assert_called_once_with(
            "Zendesk User Profile not found for User model's `zendesk_user_id` field",
            user_id=user.id,
            zendesk_user_id=user.zendesk_user_id,
        )

    @pytest.mark.parametrize(
        "should_enable_merge_duplicate_zendesk_profiles", [True, False]
    )
    @mock.patch("messaging.services.zendesk.log.info")
    @mock.patch("messaging.services.zendesk.enable_merge_duplicate_zendesk_profiles")
    @mock.patch("messaging.services.zendesk.merge_zendesk_profiles")
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.get_zendesk_user")
    @mock.patch(
        "messaging.services.zendesk_client.ZendeskClient.update_primary_identity"
    )
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.update_user")
    def test_update_zendesk_user__merge_duplicate_zendesk_profiles(
        self,
        mock_update_user,
        mock_update_primary_identity,
        mock_get_zendesk_user,
        mock_merge_zendesk_profiles,
        mock_enable_merge_duplicate_zendesk_profiles,
        mock_log_info,
        should_enable_merge_duplicate_zendesk_profiles,
        factories,
    ):

        # Given
        mock_enable_merge_duplicate_zendesk_profiles.return_value = (
            should_enable_merge_duplicate_zendesk_profiles
        )

        # when we call `zenpy_client.update_user` the first time, raise an exception to signify that a Zendesk profile already exists with the User's email
        mock_update_user.side_effect = [ZendeskAPIEmailAlreadyExistsException, None]

        user = factories.DefaultUserFactory.create()
        zd_user = ZDUser(id=1)
        user.zendesk_user_id = zd_user.id
        db.session.commit()

        # When
        update_zendesk_user(user_id=user.id, update_identity=IdentityType.EMAIL)

        # Then
        if should_enable_merge_duplicate_zendesk_profiles:
            mock_log_info.assert_called_once_with(
                "Found existing Zendesk Profile with duplicate email. Will attempt to merge duplicate profiles for user.",
                user_id=user.id,
                zendesk_user_id=user.zendesk_user_id,
                duplicate_zd_profile_zendesk_user_id=mock_get_zendesk_user.return_value.id,
                exception=mock.ANY,
            )
        else:
            mock_log_info.assert_called_once_with(
                "Duplicate Zendesk profiles found, but flag to merge duplicate profiles is disabled.",
                user_id=user.id,
                zendesk_user_id=user.zendesk_user_id,
                duplicate_zd_profile_zendesk_user_id=mock_get_zendesk_user.return_value.id,
                exception=mock.ANY,
            )

    @mock.patch(
        "messaging.services.zendesk_client.ZendeskClient.merge_zendesk_profiles"
    )
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.get_zendesk_user")
    def test_merge_zendesk_profiles(
        self, mock_get_zendesk_user, mock_merge_zendesk_profiles, factories
    ):
        # Given

        # A Zendesk User Profile is returned when we call `get_zendesk_user`
        source_destination_user = ZDUser(id=1)
        mock_get_zendesk_user.return_value = source_destination_user

        # A Zendesk User Profile that we want to merge the source ZD Profile into
        destination_zendesk_user = ZDUser(id=2)

        user = factories.DefaultUserFactory.create()

        # When
        merge_zendesk_profiles(
            user_id=str(user.id),
            source_zendesk_user=source_destination_user,
            destination_zendesk_user=destination_zendesk_user,
        )

        # Then
        mock_merge_zendesk_profiles.assert_called_once_with(
            user_id=str(user.id),
            source_zendesk_user=source_destination_user,
            destination_zendesk_user=destination_zendesk_user,
        )

    @pytest.mark.parametrize(
        "active_tracks,expected_zendesk_tracks",
        [
            (["pregnancy"], "pregnancy"),
            (["pregnancy", "menopause"], "pregnancy, menopause"),
        ],
    )
    @mock.patch("messaging.services.zendesk.log.info")
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.get_zendesk_user")
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.update_user")
    @mock.patch(
        "messaging.services.zendesk_client.ZendeskClient.get_zendesk_organization"
    )
    def test_update_zendesk_user__update_tracks(
        self,
        mock_get_org,
        mock_update_user,
        mock_get_zendesk_user,
        mock_log_info,
        active_tracks,
        expected_zendesk_tracks,
        factories,
    ):
        # Given
        user = factories.DefaultUserFactory.create()
        zd_user = ZDUser(id=1)
        user.zendesk_user_id = zd_user.id
        for track_name in active_tracks:
            factories.MemberTrackFactory.create(name=track_name, user=user)
        db.session.commit()

        mock_get_zendesk_user.return_value = zd_user
        mock_get_org.return_value = ZDOrganization(id=123)
        # When
        update_zendesk_user(user_id=user.id, update_identity=IdentityType.TRACK)

        # Then
        mock_update_user.assert_called_once_with(
            user_id=str(user.id),
            zendesk_user=zd_user,
        )
        mock_get_org.assert_called_once_with(user.organization_v2.id)
        mock_log_info.assert_called_once_with(
            "Zendesk Profile updated for user",
            user_id=user.id,
            zendesk_user_id=user.zendesk_user_id,
            update_identity=IdentityType.TRACK,
        )
        assert zd_user.user_fields["track"] == expected_zendesk_tracks
        assert zd_user.organization_id == 123

    @pytest.mark.parametrize(
        "multiple_tracks,expected_zendesk_tracks",
        [
            (False, "pregnancy - ['doula_only']"),
            (True, "pregnancy - ['doula_only'], menopause"),
        ],
    )
    @mock.patch("messaging.services.zendesk.log.info")
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.get_zendesk_user")
    @mock.patch("messaging.services.zendesk_client.ZendeskClient.update_user")
    @mock.patch(
        "models.tracks.client_track.should_enable_doula_only_track", return_value=True
    )
    @mock.patch(
        "messaging.services.zendesk_client.ZendeskClient.get_zendesk_organization"
    )
    def test_update_zendesk_user__update_tracks_doula_member(
        self,
        mock_get_org,
        mock_enable_doula_only_track,
        mock_update_user,
        mock_get_zendesk_user,
        mock_log_info,
        multiple_tracks,
        expected_zendesk_tracks,
        create_doula_only_member,
        factories,
    ):
        # Given
        user = create_doula_only_member
        zd_user = ZDUser(id=1, organization_id=123)
        user.zendesk_user_id = zd_user.id
        if multiple_tracks and len(user.active_tracks) < 2:
            track = factories.MemberTrackFactory.create(name="menopause", user=user)
            user.active_tracks.append(track)
        db.session.commit()

        mock_get_zendesk_user.return_value = zd_user
        mock_get_org.return_value = None

        # When
        update_zendesk_user(user_id=user.id, update_identity=IdentityType.TRACK)

        # Then
        mock_update_user.assert_called_once_with(
            user_id=str(user.id),
            zendesk_user=zd_user,
        )

        mock_log_info.assert_called_once_with(
            "Zendesk Profile updated for user",
            user_id=user.id,
            zendesk_user_id=user.zendesk_user_id,
            update_identity=IdentityType.TRACK,
        )
        assert zd_user.user_fields["track"] == expected_zendesk_tracks
        mock_get_org.assert_called_once_with(user.organization_v2.id)
        # assert org ID isn't overridden when get_zd_org returns None
        assert zd_user.organization_id == 123


class TestReconcileZendeskCommentIdJobLocks:
    def test_reconcile_zendesk_comment_id_job_locks_timeout(self, factories):
        ticket_id = 123
        message_id = 456
        # first hold the lock
        with reconcile_zendesk_comment_id_job_locks(
            ticket_id=ticket_id,
            message_id=message_id,
        ):
            # lets try to grab the lock multiple times this validates
            # that lock timeouts don't affect the original lock
            for _ in range(3):
                # now we expect if someone else tries to get the lock (and timeout)
                # with either the same ticket_id or message_id,
                # before we release the first lock we should except
                with pytest.raises(LockTimeout):
                    with reconcile_zendesk_comment_id_job_locks(
                        ticket_id=ticket_id,
                        message_id=message_id,
                        lock_timeout_sec=0.1,
                    ):
                        pass
                with pytest.raises(LockTimeout):
                    with reconcile_zendesk_comment_id_job_locks(
                        ticket_id=ticket_id,
                        message_id=0,
                        # we have this value low to increase the speed of the test.
                        # we are only testing that this lock grab fails because of upper
                        # scope lock
                        lock_timeout_sec=0.1,
                    ):
                        pass
                with pytest.raises(LockTimeout):
                    with reconcile_zendesk_comment_id_job_locks(
                        ticket_id=0,
                        message_id=message_id,
                        lock_timeout_sec=0.1,
                    ):
                        pass


class TestReconcileZendeskCommentId:
    @mock.patch("messaging.services.zendesk.log.info")
    @mock.patch("tasks.zendesk_v2.public_comments_for_ticket_id")
    def test_reconcile_zendesk_comment_id__message_not_found(
        self,
        mock_public_comments_for_ticket_id,
        mock_log_info,
        factories,
    ):
        ticket_id = 1
        message_id = 1
        # When
        reconcile_zendesk_comment_id(ticket_id, message_id)
        # Then
        mock_log_info.assert_called_with(
            "Could not find message, aborting zendesk_comment_id reconciliation",
            message_id=message_id,
            ticket_id=ticket_id,
        )
        assert not mock_public_comments_for_ticket_id.called

    @mock.patch("messaging.services.zendesk.log.info")
    @mock.patch("tasks.zendesk_v2.public_comments_for_ticket_id")
    def test_reconcile_zendesk_comment_id__message_has_zendesk_comment_id(
        self,
        mock_public_comments_for_ticket_id,
        mock_log_info,
        factories,
    ):
        ticket_id = 1
        message = factories.MessageFactory()
        message.zendesk_comment_id = "best_comment_id"
        message_id = message.id
        # When
        reconcile_zendesk_comment_id(ticket_id, message_id)
        # Then
        mock_log_info.assert_called_with(
            "Message already has a zendesk_comment_id, no need to reconcile it",
            message_id=message_id,
        )
        assert not mock_public_comments_for_ticket_id.called

    @mock.patch("messaging.services.zendesk.log.info")
    @mock.patch("messaging.services.zendesk.find_zendesk_comment_that_matches_message")
    @mock.patch("tasks.zendesk_v2.has_zendesk_comment_id_been_processed")
    @mock.patch("tasks.zendesk_v2.public_comments_for_ticket_id")
    def test_reconcile_zendesk_comment_id__all_comments_already_processed(
        self,
        mock_public_comments_for_ticket_id,
        mock_has_zendesk_comment_id_been_processed,
        mock_find_zendesk_comment_that_matches_message,
        mock_log_info,
        factories,
    ):
        message = factories.MessageFactory()
        message_id = message.id
        ticket_id = 1

        comment_1 = MagicMock(id=1)
        comment_2 = MagicMock(id=2)

        comments = [comment_1, comment_2]
        mock_public_comments_for_ticket_id.return_value = comments
        mock_has_zendesk_comment_id_been_processed.side_effect = [True, True]

        # When
        reconcile_zendesk_comment_id(ticket_id, message_id)

        # Then
        mock_public_comments_for_ticket_id.assert_called_once_with(ticket_id=ticket_id)
        ids_used_for_calling_haz_zendesk_comment_id_been_processed = [
            call_args[1]["comment_id"]
            for call_args in mock_has_zendesk_comment_id_been_processed.call_args_list
        ]
        assert [
            comment_1.id,
            comment_2.id,
        ] == ids_used_for_calling_haz_zendesk_comment_id_been_processed
        mock_log_info.assert_called_with(
            "ZD Ticket has no comments with ids not found in mono db. It seems like the message did not make it to ZD.",
            ticket_id=ticket_id,
            message_id=message_id,
            zd_comments_ids=[c.id for c in comments],
        )
        assert not mock_find_zendesk_comment_that_matches_message.called

    @mock.patch("messaging.services.zendesk.db.session.commit")
    @mock.patch("messaging.services.zendesk.log.info")
    @mock.patch("messaging.services.zendesk.find_zendesk_comment_that_matches_message")
    @mock.patch("tasks.zendesk_v2.has_zendesk_comment_id_been_processed")
    @mock.patch("tasks.zendesk_v2.public_comments_for_ticket_id")
    def test_reconcile_zendesk_comment_id__no_comments_matched(
        self,
        mock_public_comments_for_ticket_id,
        mock_has_zendesk_comment_id_been_processed,
        mock_find_zendesk_comment_that_matches_message,
        mock_log_info,
        mock_db_session_commit,
        factories,
    ):
        message = factories.MessageFactory()
        message_id = message.id
        ticket_id = 1

        comment_1 = MagicMock(id=1)
        comment_2 = MagicMock(id=2)

        comments = [comment_1, comment_2]
        mock_public_comments_for_ticket_id.return_value = comments
        mock_has_zendesk_comment_id_been_processed.side_effect = [False, False]
        mock_find_zendesk_comment_that_matches_message.return_value = None

        # When
        reconcile_zendesk_comment_id(ticket_id, message_id)

        # Then
        mock_public_comments_for_ticket_id.assert_called_once_with(ticket_id=ticket_id)
        ids_used_for_calling_haz_zendesk_comment_id_been_processed = [
            call_args[1]["comment_id"]
            for call_args in mock_has_zendesk_comment_id_been_processed.call_args_list
        ]
        assert [
            comment_1.id,
            comment_2.id,
        ] == ids_used_for_calling_haz_zendesk_comment_id_been_processed
        mock_find_zendesk_comment_that_matches_message.assert_called_once_with(
            zendesk_comments_list=comments, message=message
        )
        mock_log_info.assert_called_with(
            "Could not find a zd comment that matches the mono message",
            ticket_id=ticket_id,
            message_id=message_id,
            zd_comments_ids=[c.id for c in comments],
        )
        assert not mock_db_session_commit.called

    @mock.patch("messaging.services.zendesk.db.session.commit")
    @mock.patch("messaging.services.zendesk.find_zendesk_comment_that_matches_message")
    @mock.patch("tasks.zendesk_v2.has_zendesk_comment_id_been_processed")
    @mock.patch("tasks.zendesk_v2.public_comments_for_ticket_id")
    def test_reconcile_zendesk_comment_id__happy_path(
        self,
        mock_public_comments_for_ticket_id,
        mock_has_zendesk_comment_id_been_processed,
        mock_find_zendesk_comment_that_matches_message,
        mock_db_session_commit,
        factories,
    ):
        message = factories.MessageFactory()
        message_id = message.id
        ticket_id = 1

        comment_1 = MagicMock(id=1)
        comment_2 = MagicMock(id=2)

        comments = [comment_1, comment_2]
        mock_public_comments_for_ticket_id.return_value = comments
        # We will mock that comment 1 has been processed, but 2 not
        mock_has_zendesk_comment_id_been_processed.side_effect = [True, False]
        mock_find_zendesk_comment_that_matches_message.return_value = comment_2

        # When
        reconcile_zendesk_comment_id(ticket_id, message_id)

        # Then
        mock_public_comments_for_ticket_id.assert_called_once_with(ticket_id=ticket_id)

        assert mock_has_zendesk_comment_id_been_processed.call_count == 2
        has_zendesk_comment_id_been_processed_args = [
            call_args
            for call_args in mock_has_zendesk_comment_id_been_processed.call_args_list
        ]
        assert (
            has_zendesk_comment_id_been_processed_args[0].kwargs["comment_id"]
            == comment_1.id
        )
        assert (
            has_zendesk_comment_id_been_processed_args[1].kwargs["comment_id"]
            == comment_2.id
        )

        mock_find_zendesk_comment_that_matches_message.assert_called_once_with(
            zendesk_comments_list=[comment_2], message=message
        )
        assert message.zendesk_comment_id == comment_2.id
        mock_db_session_commit.assert_called_once


class TestFindZendeskCommentThatMatchesMessage:
    @pytest.mark.parametrize(
        argnames="with_message",
        argvalues=[False, True],
    )
    @mock.patch("messaging.services.zendesk.hamming_distance")
    @mock.patch("messaging.services.zendesk.log.info")
    def test_find_zendesk_comment_that_matches_message__no_message_or_message_with_no_body(
        self,
        mock_log_info,
        mock_hamming_distance,
        with_message,
        factories,
    ):
        # Given
        message = None
        if with_message:
            message = factories.MessageFactory(body=None)
        zd_comment = MagicMock(id=1)
        zd_comments_list = [zd_comment]

        # When
        match = find_zendesk_comment_that_matches_message(zd_comments_list, message)

        # Then
        mock_log_info.assert_called_with(
            "Cant find match for None message or message with no body",
            message_id=message.id if message else None,
        )
        assert not mock_hamming_distance.called
        assert match is None

    @mock.patch("messaging.services.zendesk.hamming_distance")
    @mock.patch("messaging.services.zendesk.log.info")
    def test_find_zendesk_comment_that_matches_message__no_zd_comments_list(
        self,
        mock_log_info,
        mock_hamming_distance,
        factories,
    ):
        # Given
        message = factories.MessageFactory(body="message_body")
        zd_comments_list = []

        # When
        match = find_zendesk_comment_that_matches_message(zd_comments_list, message)

        # Then
        assert not mock_hamming_distance.called
        assert not mock_log_info.called
        assert match is None

    @mock.patch("messaging.services.zendesk.hamming_distance")
    @mock.patch("messaging.services.zendesk.log.info")
    def test_find_zendesk_comment_that_matches_message__comments_list_have_no_body(
        self,
        mock_log_info,
        mock_hamming_distance,
        factories,
    ):
        # Given
        message = factories.MessageFactory(body="message_body")
        zd_comment = MagicMock(id=1, body=None)
        zd_comments_list = [zd_comment]

        # When
        match = find_zendesk_comment_that_matches_message(zd_comments_list, message)

        # Then
        mock_log_info.assert_called_with(
            "No body in zendesk comment", zd_comment_id=zd_comment.id
        )
        assert not mock_hamming_distance.called
        assert match is None

    @mock.patch("messaging.services.zendesk.hamming_distance")
    @mock.patch("messaging.services.zendesk.log.info")
    def test_find_zendesk_comment_that_matches_message__happy_path(
        self,
        mock_log_info,
        mock_hamming_distance,
        factories,
    ):
        # Given
        message = factories.MessageFactory(body="message_body")
        zd_comment_1 = MagicMock(id=1, body="comment_1_body")
        zd_comment_2 = MagicMock(id=2, body="comment_2_body")
        zd_comments_list = [zd_comment_1, zd_comment_2]
        mock_hamming_distance.side_effect = [2, 1]

        # When
        match = find_zendesk_comment_that_matches_message(zd_comments_list, message)

        # Then
        assert mock_hamming_distance.call_count == 2
        hamming_distance_args = [
            call_args for call_args in mock_hamming_distance.call_args_list
        ]
        assert hamming_distance_args[0].kwargs["str1"] == zd_comment_1.body
        assert hamming_distance_args[0].kwargs["str2"] == message.body
        assert hamming_distance_args[1].kwargs["str1"] == zd_comment_2.body
        assert hamming_distance_args[1].kwargs["str2"] == message.body
        assert match == zd_comment_2


class TestReconciliationZendeskTicket:
    @mock.patch("messaging.services.zendesk._increment_update_zendesk_count_metric")
    @mock.patch("messaging.services.zendesk.SynchronizedZendeskTicket.update_zendesk")
    def test_update_zendesk(
        self,
        mock_super_update_zendesk,
        mock_increment_update_zendesk_count_metric,
        message_channel,
        factories,
    ):
        message = factories.MessageFactory.create(
            body="member test",
            channel_id=message_channel.id,
            user_id=message_channel.member.id,
        )

        # Given we have a ReconciliationZendeskTicket
        reconciliation_ticket = ReconciliationZendeskTicket(message)
        assert reconciliation_ticket.desired_ticket_status == "open"

        # When calling update_zendesk
        reconciliation_ticket.update_zendesk()

        # Then assert super update_zendesk is called and metric increased
        mock_super_update_zendesk.assert_called_once()
        assert isinstance(
            mock_super_update_zendesk.call_args_list[0].args[0],
            ReconciliationZendeskTicket,
        )
        message_id_called = mock_super_update_zendesk.call_args_list[0].kwargs[
            "message_id"
        ]
        assert message_id_called == str(message.id)
        mock_increment_update_zendesk_count_metric.assert_called_once_with(
            reconciliation_ticket.is_internal,
            reconciliation_ticket.is_wallet,
            "ReconciliationZendeskTicket",
        )


class TestEnterpriseValidationZendeskTicket:
    @mock.patch("messaging.services.zendesk._increment_update_zendesk_count_metric")
    @mock.patch("messaging.services.zendesk.redis_client")
    def test_update_zendesk(
        self,
        mock_zendesk_redis_client,
        mock_increment_update_zendesk_count_metric,
        factories,
        mock_zendesk,
    ):
        member = factories.MemberFactory()

        # Given we have a EnterpriseValidationZendeskTicket
        evzt = EnterpriseValidationZendeskTicket(member, "solved", "a_message")

        # When calling update_zendesk
        evzt.update_zendesk()

        # Then assert update zendesk metric increased and ticket not added to reconciliation queue
        mock_increment_update_zendesk_count_metric.assert_called_once_with(
            evzt.is_internal, evzt.is_wallet, "EnterpriseValidationZendeskTicket"
        )
        mock_zendesk_redis_client.return_value.sadd.assert_not_called()

    @mock.patch("messaging.services.zendesk.log.info")
    @mock.patch(
        "messaging.services.zendesk.SynchronizedZendeskTicket._parse_comment_id"
    )
    def test_update_zendesk__no_comment_id(
        self,
        mock_parse_comment_id,
        mock_log_info,
        factories,
        mock_zendesk,
    ):
        member = factories.MemberFactory()
        mock_parse_comment_id.return_value = None

        # Given we have a EnterpriseValidationZendeskTicket and no comment_id
        evzt = EnterpriseValidationZendeskTicket(member, "solved", "a_message")

        # When calling update_zendesk
        evzt.update_zendesk()

        # Then assert log specific for error with no message ID called
        assert (
            mock_log_info.call_args[0][0]
            == "Failed to parse zendesk_comment_id during ticket creation"
        )

    @mock.patch("messaging.services.zendesk.SynchronizedZendeskTicket.update_zendesk")
    def test_solve(
        self,
        mock_super_update_zendesk,
        factories,
    ):
        # Given
        member = factories.MemberFactory()
        member.member_profile.zendesk_verification_ticket_id = "1"

        # When
        EnterpriseValidationZendeskTicket.solve(member, "a_message")

        # Then assert super update_zendesk is called
        mock_super_update_zendesk.assert_called_once()

    @mock.patch("messaging.services.zendesk._increment_update_zendesk_count_metric")
    @mock.patch("messaging.services.zendesk.SynchronizedZendeskTicket.update_zendesk")
    def test_comment_public(
        self,
        mock_super_update_zendesk,
        mock_increment_update_zendesk_count_metric,
        factories,
    ):
        member = factories.MemberFactory()

        evzt = EnterpriseValidationZendeskTicket(member, "open", "a_message")
        assert evzt.comment_public is False

        updated_ticket = evzt.comment(member, "public comment", comment_public=True)
        assert updated_ticket.comment_public is True

        mock_super_update_zendesk.assert_called_once()
        mock_increment_update_zendesk_count_metric.assert_called_once_with(
            evzt.is_internal, evzt.is_wallet, "EnterpriseValidationZendeskTicket"
        )


class TestPostSessionZendeskTicket:
    @mock.patch("messaging.services.zendesk._increment_update_zendesk_count_metric")
    @mock.patch(
        "messaging.services.zendesk.SynchronizedZendeskTicket._create_new_ticket"
    )
    @mock.patch(
        "messaging.services.zendesk.SynchronizedZendeskTicket._parse_comment_id"
    )
    def test_update_zendesk(
        self,
        mock_parse_comment_id,
        mock_create_new_ticket,
        mock_increment_update_zendesk_count_metric,
        message_channel,
        factories,
    ):
        mock_create_new_ticket.return_value.ticket.id = 12345
        mock_parse_comment_id.return_value = 6789
        member = message_channel.member
        practitioner = factories.PractitionerUserFactory.create()
        factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=practitioner
        )

        message = factories.MessageFactory.create(
            body="member test",
            channel_id=message_channel.id,
            user_id=member.id,
        )
        # confirm zd ticket and comment ID not stored
        assert member.member_profile.zendesk_ticket_id is None
        assert message.zendesk_comment_id is None

        # Given we have a PostSessionZendeskTicket
        pszt = PostSessionZendeskTicket(practitioner, message)

        # When calling update_zendesk
        pszt.update_zendesk()

        # Then assert metric increased and zendesk ticket information stored
        mock_increment_update_zendesk_count_metric.assert_called_once_with(
            pszt.is_internal, pszt.is_wallet, "PostSessionZendeskTicket"
        )
        db.session.expire_all()
        assert member.member_profile.zendesk_ticket_id is not None
        assert message.zendesk_comment_id is not None


class TestSendGeneralTicketToZendesk:
    @pytest.mark.parametrize(argnames="ticket_status", argvalues=["solved", "open"])
    @patch(
        "messaging.services.zendesk.ZendeskClient.create_ticket",
    )
    @patch(
        "messaging.services.zendesk.get_or_create_zenpy_user",
    )
    def test_send_general_ticket_to_zendesk(
        self,
        mock_get_or_create_zenpy_user,
        mock_create_ticket,
        ticket_status,
        default_user,
        enable_set_user_need_if_solving_ticket_ff_on,
    ):
        # Given
        expected_new_ticket_id = 123
        mock_create_ticket.return_value = mock.MagicMock(
            ticket=mock.MagicMock(id=expected_new_ticket_id)
        )

        zenpy_user_id = "test_id"
        mock_get_or_create_zenpy_user.return_value = mock.MagicMock(id=zenpy_user_id)

        # When
        zendesk_ticket_id = send_general_ticket_to_zendesk(
            user=default_user,
            ticket_subject="mock-subject",
            content="mock-body",
            called_by="mock-sender",
            via_followup_source_id=1234,
            status=ticket_status,
            user_need_when_solving_ticket="the_best_user_need_when_solving_ticket",
            tags=["hello", "world"],
        )

        # Then
        assert zendesk_ticket_id == expected_new_ticket_id

        mock_create_ticket.assert_called_once()
        call_args = mock_create_ticket.call_args_list[0][0]
        new_ticket_created = call_args[0]

        assert new_ticket_created.requester_id == zenpy_user_id
        assert new_ticket_created.status == ticket_status
        assert new_ticket_created.subject == namespace_subject("mock-subject")
        assert new_ticket_created.tags == ["hello", "world"]
        assert new_ticket_created.via_followup_source_id == 1234
        assert new_ticket_created.comment.body == "mock-body"
        assert new_ticket_created.comment.author_id == "test_id"
        expected_custom_fields = None
        if ticket_status == "solved":
            expected_custom_fields = [
                {
                    "id": get_user_need_custom_field_id(),
                    "value": "the_best_user_need_when_solving_ticket",
                }
            ]

        assert new_ticket_created.custom_fields == expected_custom_fields
        assert not new_ticket_created.comment.public

        ticket_creator_id = call_args[1]
        assert ticket_creator_id == default_user.id
        requester_id = call_args[2]
        assert requester_id == "test_id"


class TestUpdateZendeskUserJobLock:
    @mock.patch("messaging.services.zendesk.update_zendesk_user.delay")
    def test_update_zendesk_user_job_lock_timeout(self, mock_update_zd_user):
        user_id = "123"
        # get the lock
        with update_zendesk_user_job_lock(user_id=user_id, update_identity=""):
            # fail to get lock because it's already held
            with update_zendesk_user_job_lock(
                user_id=user_id,
                update_identity="",
                lock_timeout_sec=0.1,
            ):
                pass
        # assert we re-enqueued the job
        assert mock_update_zd_user.called_once_with(user_id, "")

    def test_update_zendesk_user_job_lock(self):
        user_id_1 = "123"
        user_id_2 = "456"
        # get the lock
        with update_zendesk_user_job_lock(
            user_id=user_id_1,
            update_identity="",
        ):
            # get the second lock
            with update_zendesk_user_job_lock(
                user_id=user_id_2,
                update_identity="",
                lock_timeout_sec=0.1,
            ):
                pass


class TestFilterClientTracks:
    def test_get_org_tracks(
        self,
        factories,
    ):
        # Given org + 5 client tracks (1 inactive, 3 filtered out)
        org = factories.OrganizationFactory()
        adoption_track = factories.ClientTrackFactory.create(
            organization=org, track=ZendeskTrackName.ADOPTION
        )
        partner_newparent_track = factories.ClientTrackFactory.create(
            organization=org, track=ZendeskTrackName.PARTNER_NEWPARENT
        )
        # tracks that should be filtered out
        generic_track = factories.ClientTrackFactory.create(
            organization=org, track=ZendeskTrackName.GENERIC
        )
        pregnancy_options_track = factories.ClientTrackFactory.create(
            organization=org, track=ZendeskTrackName.PREGNANCY_OPTIONS
        )
        sponsored_track = factories.ClientTrackFactory.create(
            organization=org, track=ZendeskTrackName.SPONSORED
        )
        # inactive track
        inactive_track = factories.ClientTrackFactory.create(
            organization=org,
            track=ZendeskTrackName.MENOPAUSE,
            active=0,
        )
        tracks = [
            adoption_track,
            partner_newparent_track,
            generic_track,
            pregnancy_options_track,
            sponsored_track,
            inactive_track,
        ]
        zendesk_client_tracks = [
            ZendeskClientTrack(
                active=track.active, name=track.name, display_name=track.display_name
            )
            for track in tracks
        ]
        # When
        tracks = filter_client_tracks(zendesk_client_tracks)

        # Then
        assert tracks == "Adoption\nPartner Postpartum"

    def test_get_org_tracks__localization_not_initialized(
        self,
    ):
        # given
        # When track w localized slug
        tracks = filter_client_tracks(
            [
                ZendeskClientTrack(
                    active=True,
                    name=ZendeskTrackName.ADOPTION,
                    display_name="track_config_display_name_adoption",
                )
            ]
        )

        # Then
        assert tracks == "Adoption"


class TestUpdateZendeskOrg:
    @pytest.mark.parametrize("enable_update_zendesk_org", [True, False])
    @mock.patch("messaging.services.zendesk.should_update_zendesk_org")
    @mock.patch("messaging.services.zendesk.log.info")
    @mock.patch(
        "messaging.services.zendesk_client.ZendeskClient.create_or_update_organization"
    )
    def test_update_zendesk_org(
        self,
        mock_create_or_update_org,
        mock_log_info,
        mock_should_update_zendesk_org,
        enable_update_zendesk_org,
        factories,
    ):
        # given
        mock_should_update_zendesk_org.return_value = enable_update_zendesk_org
        org = factories.OrganizationFactory.create()
        track_1 = factories.ClientTrackFactory.create(
            organization=org, track=ZendeskTrackName.ADOPTION
        )
        track_2 = factories.ClientTrackFactory.create(
            organization=org, track=ZendeskTrackName.PREGNANCY
        )
        mock_log_info.reset_mock()
        mock_create_or_update_org.reset_mock()
        # when
        update_zendesk_org(
            org_id=org.id,
            org_name=org.name,
            tracks=[
                ZendeskClientTrack(
                    active=track_1.active,
                    name=track_1.name,
                    display_name=track_1.display_name,
                ),
                ZendeskClientTrack(
                    active=track_2.active,
                    name=track_2.name,
                    display_name=track_2.display_name,
                ),
            ],
            offshore_restriction=org.US_restricted,
            track_name="",
        )
        # then
        if not enable_update_zendesk_org:
            pass
        else:
            mock_log_info.assert_called_once_with(
                "Updating zendesk organization",
                org_id=org.id,
            )
            mock_create_or_update_org.assert_called_once_with(
                org.id,
                org.name,
                f"{track_1.display_name}\n{track_2.display_name}",
                org.US_restricted,
            )

    @mock.patch("messaging.services.zendesk.should_update_zendesk_org")
    @mock.patch("messaging.services.zendesk.log.info")
    @mock.patch(
        "messaging.services.zendesk_client.ZendeskClient.create_or_update_organization"
    )
    def test_update_zendesk_org__no_tracks(
        self,
        mock_create_or_update_org,
        mock_log_info,
        mock_should_update_zendesk_org,
        factories,
    ):
        # given
        mock_should_update_zendesk_org.return_value = True
        org = factories.OrganizationFactory.create()
        mock_log_info.reset_mock()
        mock_create_or_update_org.reset_mock()
        # when
        update_zendesk_org(
            org_id=org.id,
            org_name=org.name,
            tracks=[],
            offshore_restriction=org.US_restricted,
            track_name="",
        )
        # then

        mock_log_info.assert_called_once_with(
            "Updating zendesk organization",
            org_id=org.id,
        )
        mock_create_or_update_org.assert_called_once_with(
            org.id, org.name, "", org.US_restricted
        )


class TestGetCXTags:
    def test_get_cx_tags__bad_params(self):
        with pytest.raises(AttributeError):
            get_cx_tags(member=None, channel=None, message=None)

    def test_get_cx_tags__existing_tags(
        self,
        message_channel,
        factories,
    ):
        message = factories.MessageFactory.create(
            body="member test",
            channel_id=message_channel.id,
            user_id=message_channel.member.id,
        )

        existing_tag = "tags_are_cool"
        another_existing_tag = "tags_are_not_cool"
        tags = get_cx_tags(
            member=message_channel.member,
            channel=message_channel,
            message=message,
            existing_tags=[existing_tag, another_existing_tag],
        )

        assert existing_tag in tags
        assert another_existing_tag in tags

    def test_get_cx_tags__channel_id_and_cx_tags(
        self,
        message_channel,
        factories,
    ):
        message = factories.MessageFactory.create(
            body="member test",
            channel_id=message_channel.id,
            user_id=message_channel.member.id,
        )

        tags = get_cx_tags(
            member=message_channel.member, channel=message_channel, message=message
        )
        assert SynchronizedZendeskTicket.CX_MESSAGING in tags
        assert _generate_cx_channel_id_tag(message_channel.id) in tags

    @mock.patch("messaging.services.zendesk.wallet_exists_for_channel")
    def test_get_cx_tags__wallet_tags(
        self,
        mock_wallet_exists_for_channel,
        message_channel,
        factories,
    ):
        mock_wallet_exists_for_channel.return_value = True
        message = factories.MessageFactory.create(
            body="member test",
            channel_id=message_channel.id,
            user_id=message_channel.member.id,
        )

        tags = get_cx_tags(
            member=message_channel.member, channel=message_channel, message=message
        )
        mock_wallet_exists_for_channel.assert_called_once()
        assert SynchronizedZendeskTicket.MAVEN_WALLET in tags

    @mock.patch("messaging.services.zendesk.wallet_exists_for_channel")
    def test_get_cx_tags__no_wallet_tags(
        self,
        mock_wallet_exists_for_channel,
        message_channel,
        factories,
    ):
        mock_wallet_exists_for_channel.return_value = False
        message = factories.MessageFactory.create(
            body="member test",
            channel_id=message_channel.id,
            user_id=message_channel.member.id,
        )

        tags = get_cx_tags(
            member=message_channel.member, channel=message_channel, message=message
        )
        mock_wallet_exists_for_channel.assert_called_once()
        assert SynchronizedZendeskTicket.MAVEN_WALLET not in tags

    def test_get_cx_tags__automated_message_tag(
        self,
        message_channel,
        factories,
    ):
        message = factories.MessageFactory.create(
            body="member test",
            channel_id=message_channel.id,
            user_id=message_channel.member.id,
            braze_campaign_id="some_braze_id",
        )

        tags = get_cx_tags(
            member=message_channel.member, channel=message_channel, message=message
        )
        assert SynchronizedZendeskTicket.NEW_AUTOMATED_MESSAGE in tags
        assert SynchronizedZendeskTicket.AUTOMATED_MESSAGE_IN_THREAD in tags

    def test_get_cx_tags__no_automated_message_tag(
        self,
        message_channel,
        factories,
    ):
        message2 = factories.MessageFactory.create(
            body="member test",
            channel_id=message_channel.id,
            user_id=message_channel.member.id,
        )
        tags = get_cx_tags(
            member=message_channel.member,
            channel=message_channel,
            message=message2,
            existing_tags=[SynchronizedZendeskTicket.NEW_AUTOMATED_MESSAGE],
        )
        assert SynchronizedZendeskTicket.NEW_AUTOMATED_MESSAGE not in tags
        assert SynchronizedZendeskTicket.AUTOMATED_MESSAGE_IN_THREAD not in tags

    def test_get_cx_tags__enterprise_tags(
        self,
        message_channel,
        factories,
    ):
        message = factories.MessageFactory.create(
            body="member test",
            channel_id=message_channel.id,
            user_id=message_channel.member.id,
        )

        tags = get_cx_tags(
            member=message_channel.member, channel=message_channel, message=message
        )

        assert SynchronizedZendeskTicket.ENTERPRISE in tags
        org_name = message_channel.member.organization_v2.name
        assert _generate_org_name_tag(org_name) in tags
