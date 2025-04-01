from typing import List
from unittest.mock import MagicMock, Mock, patch

from authn.models.user import User
from models.gdpr import GDPRDeletionBackup, GDPRRequestStatus, GDPRUserRequest
from storage.connection import db
from tasks.gdpr_user_deletion import gdpr_delete_users
from utils.random_string import generate_random_string


def test_gdpr_delete_users(factories):
    user_one_id = int(
        generate_random_string(
            length=8,
            include_lower_case_char=False,
            include_upper_case_char=False,
            include_digit=True,
        )
    )
    user_two_id = int(
        generate_random_string(
            length=8,
            include_lower_case_char=False,
            include_upper_case_char=False,
            include_digit=True,
        )
    )
    user_three_id = int(
        generate_random_string(
            length=8,
            include_lower_case_char=False,
            include_upper_case_char=False,
            include_digit=True,
        )
    )

    user_one_email = "abc@gmail.com"
    user_two_email = "xyz@yahoo.com"
    user_three_email = "xyt@yahoo.com"

    # create user
    user_one: User = factories.DefaultUserFactory.create(
        id=user_one_id,
        email=user_one_email,
    )
    user_two: User = factories.DefaultUserFactory.create(
        id=user_two_id,
        email=user_two_email,
    )
    user_three: User = factories.DefaultUserFactory.create(
        id=user_three_id,
        email=user_three_email,
    )

    # create pending gdpr user requests
    user_one_request: GDPRUserRequest = factories.GDPRUserRequestFactory.create(
        user_id=user_one.id, user_email=user_one.email, status="PENDING"
    )
    user_two_request: GDPRUserRequest = factories.GDPRUserRequestFactory.create(
        user_id=user_two.id, user_email=user_two.email, status="PENDING"
    )
    user_three_request: GDPRUserRequest = factories.GDPRUserRequestFactory.create(
        user_id=user_three.id, user_email=user_three.email, status="PENDING"
    )

    initiator_id = 456
    initiator = Mock(spec=User)
    initiator.id = initiator_id

    with patch(
        "utils.data_management.GDPRDeleteUser.user_has_permission_to_delete"
    ) as mock_user_has_permission_to_delete:
        with patch("tasks.gdpr_user_deletion._get_initiator") as mock_initiator:
            with patch("google.cloud.storage.Client") as mock_storage_client:
                mock_initiator.return_value = initiator
                mock_user_has_permission_to_delete.return_value = True

                mock_bucket = MagicMock()
                mock_blob = MagicMock()

                # Set up the mock client to return the mock bucket
                mock_storage_client.return_value.bucket.return_value = mock_bucket
                # Set up the mock bucket to return the mock blob
                mock_bucket.blob.return_value = mock_blob
                # Set up the mock blob to return specific content
                file_content = f"1/1/2024,{user_one_id},{user_one_email}\r\n2/7/2024,{user_two_id},{user_two_email}"
                mock_blob.download_as_string.return_value = file_content.encode(
                    encoding="utf-8"
                )

                users_before_deletion: List[User] = db.session.query(User).all()
                pending_gdpr_user_requests_before_deletion: List[GDPRUserRequest] = (
                    db.session.query(GDPRUserRequest)
                    .filter(GDPRUserRequest.status == GDPRRequestStatus.PENDING)
                    .all()
                )
                backups_before_deletion = db.session.query(GDPRDeletionBackup).all()

                gdpr_delete_users(initiator_id)

                users_after_deletion: List[User] = db.session.query(User).all()
                pending_gdpr_user_requests_after_deletion: List[GDPRUserRequest] = (
                    db.session.query(GDPRUserRequest)
                    .filter(GDPRUserRequest.status == GDPRRequestStatus.PENDING)
                    .all()
                )
                backups_after_deletion = db.session.query(GDPRDeletionBackup).all()

                assert len(backups_after_deletion) - len(backups_before_deletion) == 2

                assert len(users_before_deletion) - len(users_after_deletion) == 2
                assert (
                    len(
                        list(
                            filter(
                                lambda user_after_deletion: user_after_deletion.id
                                == user_three.id,
                                users_after_deletion,
                            )
                        )
                    )
                    == 1
                )

                assert (
                    len(pending_gdpr_user_requests_before_deletion)
                    - len(pending_gdpr_user_requests_after_deletion)
                    == 2
                )
                assert (
                    len(
                        list(
                            filter(
                                lambda pending_gdpr_user_request_after_deletion: pending_gdpr_user_request_after_deletion.id
                                == user_three_request.id,
                                pending_gdpr_user_requests_after_deletion,
                            )
                        )
                    )
                    == 1
                )

                user_one_request_after_deletion = (
                    db.session.query(GDPRUserRequest)
                    .filter(GDPRUserRequest.id == user_one_request.id)
                    .first()
                )
                assert (
                    user_one_request_after_deletion.status
                    == GDPRRequestStatus.COMPLETED
                )

                user_two_request_after_deletion = (
                    db.session.query(GDPRUserRequest)
                    .filter(GDPRUserRequest.id == user_two_request.id)
                    .first()
                )
                assert (
                    user_two_request_after_deletion.status
                    == GDPRRequestStatus.COMPLETED
                )
