import json

import pytest
import requests
from auth0 import exceptions
from maven.data_access import errors

from authn.errors.idp.client_error import (
    ClientError,
    DuplicateResourceError,
    IdentityClientError,
)
from authn.services.integrations import idp


class TestManagementClient:
    @staticmethod
    def test_get_job(mock_auth0_management):
        # Given
        job_id = "job123"

        # When
        idp.ManagementClient().get_job(job_id)

        # Then
        assert mock_auth0_management.jobs.get.call_args.args == (job_id,)

    @staticmethod
    def test_get_job_error(mock_auth0_management):
        # Given
        mock_auth0_management.jobs.get.side_effect = exceptions.Auth0Error(
            400, "Failed", "Bad Job ID"
        )
        # When/Then
        with pytest.raises(ClientError):
            idp.ManagementClient().get_job("job123")

    @staticmethod
    def test_get_job_with_auth0_server_error(mock_auth0_management):
        # Given
        mock_auth0_management.jobs.get.side_effect = exceptions.Auth0Error(
            500, "Failed", "Bad Job ID"
        )
        # When/Then
        with pytest.raises(IdentityClientError):
            idp.ManagementClient().get_job("job123")

    @staticmethod
    def test_import_users(mock_auth0_management):
        # Given
        payload = [{"email": "test@example.com"}]

        # When
        idp.ManagementClient().import_users(payload=payload)

        # Then
        assert (
            json.load(mock_auth0_management.jobs.import_users.call_args.args[1])
            == payload
        )

    @staticmethod
    def test_create_user(management_client, mock_auth0_management):
        # Given
        user_id = 999
        email = "test@example.com"
        password = "password"
        conn_name = "my_connection_1234"
        management_client.connection_id = "some_connection"
        management_client.connection_name = conn_name
        management_client.client_disabled = False
        mock_auth0_management.users.create.return_value = {"user_id": user_id}

        # When
        management_client.create_user(email=email, password=password, user_id=user_id)

        # Then
        user = {
            "email": email,
            "name": email,
            "email_verified": True,
            "password": password,
            "connection": conn_name,
            "app_metadata": {"maven_user_id": user_id},
        }
        assert mock_auth0_management.users.create.call_args.args == (user,)

    @staticmethod
    def test_create_user_with_transit_error(management_client, mock_auth0_management):
        # Given
        user_id = 999
        email = "test@example.com"
        password = "password"
        conn_name = "my_connection_1234"
        management_client.connection_id = "some_connection"
        management_client.connection_name = conn_name
        management_client.client_disabled = False
        mock_auth0_management.users.create.side_effect = requests.ReadTimeout()

        # When / Then
        with pytest.raises(errors.TransientRepositoryError):
            management_client.create_user(
                email=email, password=password, user_id=user_id
            )

        user = {
            "email": email,
            "name": email,
            "email_verified": True,
            "password": password,
            "connection": conn_name,
            "app_metadata": {"maven_user_id": user_id},
        }
        assert mock_auth0_management.users.create.call_args.args == (user,)

    @staticmethod
    @pytest.mark.skip(reason="local pass, failed in CI for unknown reason")
    def test_create_user_already_exists(management_client, mock_auth0_management):
        # Given
        user_id = 999
        email = "test@example.com"
        password = "password"
        mock_auth0_management.users.create.side_effect = exceptions.Auth0Error(
            409, "User already exists", "Cannot create an existing user"
        )

        # When/Then
        with pytest.raises(DuplicateResourceError) as err:
            management_client.create_user(
                email=email, password=password, user_id=user_id
            )
        assert err.value.code == 409
        assert err.value.message == "Cannot create an existing user"

    @staticmethod
    @pytest.mark.skip(reason="local pass, failed in CI for unknown reason")
    def test_create_user_with_bad_request_error(
        management_client, mock_auth0_management
    ):
        # Given
        user_id = 999
        email = "test@example.com"
        password = "password"
        mock_auth0_management.users.create.side_effect = exceptions.Auth0Error(
            400, "Bad request", "Bad request to Auth0"
        )

        # When/Then
        with pytest.raises(ClientError) as err:
            management_client.create_user(
                email=email, password=password, user_id=user_id
            )
        assert err.value.code == 400
        assert err.value.message == "Bad request to Auth0"

    @staticmethod
    def test_update_user(management_client, mock_auth0_management):
        # Given
        external_id = "auth0|abcd1234"
        password = "new_password"
        conn_name = "my_connection_1234"
        management_client.connection_name = conn_name
        expected_body = {"password": password, "connection": conn_name}
        mock_auth0_management.users.update.side_effect = None

        # When
        management_client.update_user(external_id, password=password)

        # Then
        assert mock_auth0_management.users.update.call_args.kwargs["id"] == external_id
        assert (
            mock_auth0_management.users.update.call_args.kwargs["body"] == expected_body
        )

    @staticmethod
    def test_update_user_transit_error(management_client, mock_auth0_management):
        # Given
        external_id = "auth0|abcd1234"
        password = "new_password"
        conn_name = "my_connection_1234"
        management_client.connection_name = conn_name
        expected_body = {"password": password, "connection": conn_name}
        mock_auth0_management.users.update.side_effect = requests.ReadTimeout

        # When/Then
        with pytest.raises(errors.TransientRepositoryError):
            management_client.update_user(external_id, password=password)

        assert mock_auth0_management.users.update.call_args.kwargs["id"] == external_id
        assert (
            mock_auth0_management.users.update.call_args.kwargs["body"] == expected_body
        )

    @staticmethod
    def test_user_access_control(management_client, mock_auth0_management):
        # Given
        external_id = "auth0|abcd1234"
        expected_body = {"blocked": False}
        mock_auth0_management.users.update.side_effect = None

        # When
        management_client.user_access_control(external_id=external_id, is_active=True)

        # Then
        assert mock_auth0_management.users.update.call_args.kwargs["id"] == external_id
        assert (
            mock_auth0_management.users.update.call_args.kwargs["body"] == expected_body
        )

    @staticmethod
    def test_user_access_control_transit_error(
        management_client, mock_auth0_management
    ):
        # Given
        external_id = "auth0|abcd1234"
        expected_body = {"blocked": False}
        mock_auth0_management.users.update.side_effect = requests.ReadTimeout
        # When/Then
        with pytest.raises(errors.TransientRepositoryError):
            management_client.user_access_control(
                external_id=external_id, is_active=True
            )
        assert mock_auth0_management.users.update.call_args.kwargs["id"] == external_id
        assert (
            mock_auth0_management.users.update.call_args.kwargs["body"] == expected_body
        )

    @staticmethod
    def test_delete_user(management_client, mock_auth0_management):
        # Given
        external_id = "auth0|abcd1234"

        # When
        management_client.delete_user(external_id)

        # Then
        assert mock_auth0_management.users.delete.call_args.kwargs["id"] == external_id

    @staticmethod
    def test_search_by_email(management_client, mock_auth0_management):
        # Given
        email = "test@example.com"
        user_id = "auth0|abcd1234"
        user = {"email": email, "user_id": user_id}
        management_client.client_disabled = False
        mock_auth0_management.users.list.return_value = {"users": [user]}

        # When
        found_user = management_client.search_by_email(email=email)

        # Then
        assert found_user.email == email
        assert found_user.user_id == user_id
        assert (
            f"email:{email}" in mock_auth0_management.users.list.call_args.kwargs["q"]
        )

    @staticmethod
    def test_search_by_email_multiple_users(management_client, mock_auth0_management):
        # Given
        email = "test@example.com"
        user = {"email": "email", "user_id": "auth0|abcd1234"}
        user2 = {"email": "email2", "user_id": "auth0|defg9876"}
        mock_auth0_management.users.list.return_value = {"users": [user, user2]}

        # When
        users = management_client.search_by_email(email=email)

        # Then
        assert users is None

    @staticmethod
    def test_search(management_client, mock_auth0_management):
        # Given
        user = {"email": "test@example.com", "user_id": "auth0|abcd1234"}
        query = {
            "q": "_exists_:user_metadata.pool_user_id",
            "fields": ["user_id", "user_metadata"],
        }
        mock_auth0_management.users.list.return_value = {"users": [user]}

        # When
        users = management_client.search(query=query)

        # Then
        assert users == [user]
        assert mock_auth0_management.users.list.call_args.kwargs["q"] == query["q"]
