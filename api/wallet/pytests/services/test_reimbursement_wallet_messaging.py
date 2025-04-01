from unittest import mock
from unittest.mock import ANY, call, patch

import pytest
from zenpy.lib.api_objects import Comment, Ticket

from messaging.services.zendesk_client import ZendeskClient
from wallet.models.constants import WalletState
from wallet.models.reimbursement_wallet_user import ReimbursementWalletUsers
from wallet.pytests.factories import (
    ReimbursementWalletFactory,
    ReimbursementWalletUsersFactory,
)
from wallet.services.reimbursement_wallet_messaging import (
    add_comment_to_ticket,
    add_reimbursement_request_comment,
    add_reimbursement_request_to_wallet_channel,
    get_or_create_rwu_channel,
    get_organization_tag,
)


class TestAddReimbursementRequestComment:
    @mock.patch(
        "wallet.services.reimbursement_wallet_messaging.enable_creating_reimbursement_message_to_db",
        return_value=True,
    )
    @mock.patch(
        "wallet.services.reimbursement_wallet_messaging.add_reimbursement_request_to_wallet_channel"
    )
    def test_success_with_existing_ticket(
        self,
        mock_add_reimbursement_request_to_wallet_channel,
        mock_enable_creating_reimbursement_message_to_db,
        valid_reimbursement_request,
        enterprise_user,
    ):
        mock_zendesk_ticket = mock.MagicMock()
        mock_zendesk_user = mock.MagicMock()
        mock_zendesk_user.id = "test_id"
        with patch.object(
            ZendeskClient, "get_ticket", return_value=mock_zendesk_ticket
        ), patch.object(ZendeskClient, "update_ticket") as mock_update_ticket, patch(
            "wallet.services.reimbursement_wallet_messaging.get_or_create_zenpy_user",
            return_value=mock_zendesk_user,
        ):
            reimbursement_wallet_user = ReimbursementWalletUsers.query.filter(
                ReimbursementWalletUsers.user_id == enterprise_user.id
            ).one()

            add_reimbursement_request_comment(
                valid_reimbursement_request, reimbursement_wallet_user
            )

            expected_calls = [
                call(
                    mock_zendesk_ticket,
                    enterprise_user.id,
                    "reimbursement request creation flow",
                ),
                call(
                    mock_zendesk_ticket,
                    enterprise_user.id,
                    "reimbursement request creation flow",
                ),
            ]
            mock_update_ticket.assert_has_calls(calls=expected_calls, any_order=False)

            # mock_zendesk_ticket contains the comment from the second (last) update
            assert mock_zendesk_ticket.status == "open"
            assert (
                mock_zendesk_ticket.comment.body
                == f"Reimbursement request for {valid_reimbursement_request.label} has been created with the id: {valid_reimbursement_request.id}."
            )
            assert mock_zendesk_ticket.comment.public is True
            assert mock_zendesk_ticket.comment.author_id == "test_id"

            # assert call to persist the reimbursement request message to the db was made
            mock_add_reimbursement_request_to_wallet_channel.assert_called_once()

    @mock.patch(
        "wallet.services.reimbursement_wallet_messaging.enable_creating_reimbursement_message_to_db",
        return_value=True,
    )
    @mock.patch(
        "wallet.services.reimbursement_wallet_messaging.add_reimbursement_request_to_wallet_channel"
    )
    def test_success_with_closed_ticket(
        self,
        mock_add_reimbursement_request_to_wallet_channel,
        mock_enable_creating_reimbursement_message_to_db,
        valid_reimbursement_request,
        enterprise_user,
        qualified_alegeus_wallet_hdhp_single,
    ):
        mock_zendesk_ticket = mock.MagicMock()
        mock_zendesk_ticket.id = 123
        mock_zendesk_ticket.status = "closed"
        mock_zendesk_ticket.subject = "mock subject"
        mock_zendesk_ticket.tags = ["hello", "world"]
        mock_zendesk_user = mock.MagicMock()
        mock_zendesk_user.id = "test_id"

        with patch.object(
            ZendeskClient, "get_ticket", return_value=mock_zendesk_ticket
        ), patch.object(ZendeskClient, "update_ticket") as mock_update_ticket, patch(
            "wallet.services.reimbursement_wallet_messaging.get_or_create_zenpy_user",
            return_value=mock_zendesk_user,
        ), patch(
            "wallet.services.reimbursement_wallet_messaging.send_general_ticket_to_zendesk",
            return_value=8888,
        ) as mock_send_general_ticket_to_zendesk:
            reimbursement_wallet_user = ReimbursementWalletUsers.query.filter(
                ReimbursementWalletUsers.user_id == enterprise_user.id
            ).one()

            add_reimbursement_request_comment(
                valid_reimbursement_request, reimbursement_wallet_user
            )

            mock_send_general_ticket_to_zendesk.assert_called_once_with(
                user=ANY,
                status="open",
                ticket_subject=f"Maven Wallet message with {reimbursement_wallet_user.member.full_name}",
                content="Empty",
                tags=[
                    "hello",
                    "world",
                ],
                called_by="reimbursement request creation flow",
                via_followup_source_id=123,
                user_need_when_solving_ticket="",
            )
            assert reimbursement_wallet_user.zendesk_ticket_id == 8888
            mock_update_ticket.assert_has_calls(
                [
                    call(
                        mock_zendesk_ticket,
                        enterprise_user.id,
                        "reimbursement request creation flow",
                    ),
                    call(
                        mock_zendesk_ticket,
                        enterprise_user.id,
                        "reimbursement request creation flow",
                    ),
                ],
                any_order=False,
            )

            # mock_zendesk_ticket contains the comment from the last update
            assert mock_zendesk_ticket.status == "open"
            assert (
                mock_zendesk_ticket.comment.body
                == f"Reimbursement request for {valid_reimbursement_request.label} has been created with the id: {valid_reimbursement_request.id}."
            )
            assert mock_zendesk_ticket.comment.public is True
            assert mock_zendesk_ticket.comment.author_id == "test_id"

            # assert call to persist the reimbursement request message to the db was made
            mock_add_reimbursement_request_to_wallet_channel.assert_called_once()

    def test_no_zendesk_ticket_on_RWU_should_auto_create_a_wallet_ticket(
        self, enterprise_user, valid_reimbursement_request
    ):
        mock_zendesk_ticket = mock.MagicMock()
        mock_zendesk_ticket.id = 123
        mock_zendesk_ticket.status = "open"
        mock_zendesk_ticket.subject = "mock subject"
        mock_zendesk_ticket.tags = ["hello", "world"]
        mock_zendesk_user = mock.MagicMock()
        mock_zendesk_user.id = "test_id"

        with patch.object(
            ZendeskClient, "get_ticket", return_value=mock_zendesk_ticket
        ), patch.object(ZendeskClient, "update_ticket") as mock_update_ticket, patch(
            "wallet.services.reimbursement_wallet_messaging.get_or_create_zenpy_user",
            return_value=mock_zendesk_user,
        ), patch(
            "wallet.services.reimbursement_wallet_messaging.send_general_ticket_to_zendesk",
            return_value=8888,
        ) as mock_send_general_ticket_to_zendesk:
            reimbursement_wallet_user = ReimbursementWalletUsers.query.filter(
                ReimbursementWalletUsers.user_id == enterprise_user.id
            ).one()

            # set zendesk ticket id to None to trigger the flow
            reimbursement_wallet_user.zendesk_ticket_id = None

            add_reimbursement_request_comment(
                valid_reimbursement_request, reimbursement_wallet_user
            )

            # ticket should be opened
            mock_send_general_ticket_to_zendesk.assert_called_once_with(
                user=ANY,
                status="solved",
                ticket_subject=f"New Wallet for {reimbursement_wallet_user.member.full_name}",
                content="Empty",
                tags=[
                    "cx_channel_id_None",
                    "maven_wallet",
                    "cx_messaging",
                    "enterprise",
                    ANY,
                ],
                called_by="reimbursement request creation flow",
                via_followup_source_id=ANY,
                user_need_when_solving_ticket="customer-need-member-wallet-application-setting-up-wallet",
            )

            assert reimbursement_wallet_user.zendesk_ticket_id == 8888
            mock_update_ticket.assert_has_calls(
                [
                    call(
                        mock_zendesk_ticket,
                        enterprise_user.id,
                        "reimbursement request creation flow",
                    ),
                    call(
                        mock_zendesk_ticket,
                        enterprise_user.id,
                        "reimbursement request creation flow",
                    ),
                ],
                any_order=False,
            )

            # mock_zendesk_ticket contains the comment from the last update
            assert mock_zendesk_ticket.status == "open"
            assert (
                mock_zendesk_ticket.comment.body
                == f"Reimbursement request for {valid_reimbursement_request.label} has been created with the id: {valid_reimbursement_request.id}."
            )
            assert mock_zendesk_ticket.comment.public is True
            assert mock_zendesk_ticket.comment.author_id == "test_id"

    def test_zendesk_client_error(self, valid_reimbursement_request, enterprise_user):
        reimbursement_wallet_user = ReimbursementWalletUsers.query.filter(
            ReimbursementWalletUsers.user_id == enterprise_user.id
        ).one()

        with patch.object(ZendeskClient, "get_ticket") as mock_get_ticket:
            mock_get_ticket.side_effect = Exception("failed to get zendesk ticket")

            with pytest.raises(Exception, match="failed to get zendesk ticket"):
                add_reimbursement_request_comment(None, reimbursement_wallet_user)

    def test_zendesk_no_ticket_found_error(
        self, valid_reimbursement_request, enterprise_user
    ):
        reimbursement_wallet_user = ReimbursementWalletUsers.query.filter(
            ReimbursementWalletUsers.user_id == enterprise_user.id
        ).one()

        with patch.object(ZendeskClient, "get_ticket", return_value=None):

            with pytest.raises(
                Exception,
                match="Failed to comment on reimbursement request due to missing existing "
                "wallet ticket",
            ):
                add_reimbursement_request_comment(
                    valid_reimbursement_request, reimbursement_wallet_user
                )

    def test_add_comment_to_ticket(self, valid_reimbursement_request, enterprise_user):
        ticket = Ticket(
            id=1,
            requester_id=2,
            status="open",
            subject="as",
            comment=Comment(body="test"),
            tags=[],
        )
        called_by = "called by xxx"
        reimbursement_wallet_user = ReimbursementWalletUsers.query.filter(
            ReimbursementWalletUsers.user_id == enterprise_user.id
        ).one()
        with patch.object(ZendeskClient, "update_ticket") as mock_update_ticket:
            add_comment_to_ticket(
                ticket=ticket,
                comment_body="new comment",
                author_id=12,
                is_public=False,
                called_by=called_by,
                reimbursement_wallet_user=reimbursement_wallet_user,
            )

            ticket.status = "open"
            ticket.comment = Comment(body="new comment", author_id=12, public=False)
            mock_update_ticket.assert_called_once_with(
                ticket, enterprise_user.id, called_by
            )

    @pytest.mark.parametrize(
        "org, expected_org",
        [
            ("test-org", "test_org"),
            ("PWC", "pwc"),
            ("test_org", "test_org"),
            ("Test Org", "test_org"),
        ],
    )
    def test_get_organization_tag(self, enterprise_user, org, expected_org):

        enterprise_user.organization_employee.json = {"wallet_enabled": True}
        enterprise_user.organization.name = org
        wallet = ReimbursementWalletFactory.create(
            member=enterprise_user, state=WalletState.QUALIFIED
        )
        reimbursement_wallet_user = ReimbursementWalletUsersFactory.create(
            reimbursement_wallet_id=wallet.id,
            user_id=enterprise_user.id,
        )

        # then:
        org = get_organization_tag(reimbursement_wallet_user)

        assert org == expected_org

    def test_add_reimbursement_request_to_wallet_channel(
        self,
        valid_reimbursement_request,
        enterprise_user,
    ):
        # Given

        reimbursement_wallet_user = ReimbursementWalletUsers.query.filter(
            ReimbursementWalletUsers.user_id == enterprise_user.id
        ).one()

        public_comment_body = f"Reimbursement request for {valid_reimbursement_request.label} has been created with the id: {valid_reimbursement_request.id}."

        # a reimbursement wallet channel
        rwu_channel = get_or_create_rwu_channel(reimbursement_wallet_user)

        assert len(rwu_channel.messages) == 0

        # When
        add_reimbursement_request_to_wallet_channel(
            rwu_channel=rwu_channel,
            user=reimbursement_wallet_user.member,
            message=public_comment_body,
            zendesk_comment_id=1,
        )

        # Then

        assert len(rwu_channel.messages) == 1
        assert rwu_channel.messages[0].user_id == enterprise_user.id
        assert rwu_channel.messages[0].body == public_comment_body
        assert rwu_channel.messages[0].zendesk_comment_id == 1
