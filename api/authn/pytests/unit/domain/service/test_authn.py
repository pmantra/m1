from unittest import mock

import pytest
from werkzeug import security

from authn.domain.model import UserAuth
from authn.domain.service import (
    AuthenticationService,
    AuthenticationServiceError,
    E2EAuthenticationService,
    get_auth_service,
)
from authn.errors.idp.client_error import DuplicateResourceError, IdentityClientError
from authn.pytests import factories
from authn.services.integrations.idp.models import IDPUser


class TestAuthenticationService:
    @staticmethod
    def test_get_service_default():
        svc = get_auth_service(email="foo@mavenclinic.com")
        assert isinstance(svc, AuthenticationService)

    @staticmethod
    def test_get_service_e2e(mock_e2e_env):
        svc = get_auth_service(email="test+mvnqa-123@mavenclinic.com")
        assert isinstance(svc, E2EAuthenticationService)

    @staticmethod
    def test_create_token(
        mock_idp_auth_client, mock_user_service, mock_user_activity_service
    ):
        # Given
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_service=mock_user_service,
            user_activity_service=mock_user_activity_service,
        )
        # When
        token = authn.create_token(email="foo@bar.com", password="foo")
        # Then
        assert token is not None
        assert mock_user_activity_service.create.called

    @staticmethod
    def test_create_token_failure(
        mock_idp_auth_client,
        mock_user_service,
        mock_user_activity_service,
    ):
        # Given
        mock_idp_auth_client.create_token.side_effect = IdentityClientError(
            500, "token failure"
        )
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_service=mock_user_service,
            user_activity_service=mock_user_activity_service,
        )
        # When
        token = authn.create_token(email="foo@bar.com", password="foo")
        # Then
        assert token is None
        assert not mock_user_activity_service.create.called

    @staticmethod
    def test_refresh_token(mock_idp_auth_client):
        # Given
        authn = AuthenticationService(auth_client=mock_idp_auth_client)
        # When
        token = authn.refresh_token(refresh_token="abcd1234")
        # Then
        assert token is not None

    @staticmethod
    def test_refresh_token_failure(mock_idp_auth_client):
        # Given
        mock_idp_auth_client.refresh_token.side_effect = IdentityClientError(
            code=500, message="fail token"
        )
        authn = AuthenticationService(auth_client=mock_idp_auth_client)
        # When
        token = authn.refresh_token(refresh_token="abcd1234")
        # Then
        assert token is None

    @staticmethod
    def test_revoke_token(mock_idp_auth_client):
        # Given
        mock_idp_auth_client.revoke_token.return_value = None
        authn = AuthenticationService(auth_client=mock_idp_auth_client)
        # When
        resp = authn.revoke_token(refresh_token="abcd1234")
        # Then
        assert resp is None

    @staticmethod
    def test_check_password_mono():
        # Given
        user = factories.UserFactory.create()
        authn = AuthenticationService()
        # When/Then
        with mock.patch.object(security, "check_password_hash", return_value=True):
            valid = authn.check_password(
                hashed_password=user.password,
                email=user.email,
                plaintext_password="foo",
            )
            assert valid is True

    @staticmethod
    def test_check_password_idp(
        mock_idp_auth_client,
        mock_user_auth_repository,
        mock_user_service,
        mock_user_activity_service,
    ):
        # Given
        user = factories.UserFactory.create()
        user_auth = factories.UserAuthFactory.create(user_id=user.id)
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            user_service=mock_user_service,
            user_activity_service=mock_user_activity_service,
        )
        mock_user_auth_repository.get_by_user_id.return_value = user_auth
        # When
        valid = authn.check_password(
            hashed_password=user.password,
            email=user.email,
            plaintext_password="foo",
            user_id=123,
        )
        # Then
        assert valid is True
        assert mock_user_activity_service.create.called

    @staticmethod
    def test_check_password_idp_user_auth_missing(
        mock_idp_auth_client,
        mock_user_auth_repository,
        mock_idp_management_client,
        mock_user_service,
        mock_user_activity_service,
    ):
        # Given
        user = factories.UserFactory.create()
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            user_service=mock_user_service,
            user_activity_service=mock_user_activity_service,
        )
        mock_user_auth_repository.get_by_user_id.return_value = None

        # When/Then
        with mock.patch.object(security, "check_password_hash", return_value=True):
            valid = authn.check_password(
                hashed_password=user.password,
                email=user.email,
                plaintext_password="foo",
            )
            assert valid is True
            assert not mock_user_activity_service.create.called

    @staticmethod
    def test_check_password_idp_set_external_id(
        mock_idp_auth_client,
        mock_user_auth_repository,
        mock_idp_management_client,
        mock_user_service,
        mock_user_activity_service,
    ):
        # Given
        user = factories.UserFactory.create(id=123)
        external_id = "auth0|999"
        user_auth = factories.UserAuthFactory.create(user_id=user.id, external_id=None)
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
            user_service=mock_user_service,
            user_activity_service=mock_user_activity_service,
        )
        mock_user_auth_repository.get_by_user_id.return_value = user_auth
        mock_idp_management_client.search_by_email.return_value = IDPUser(
            user_id=external_id
        )

        # When
        authn.check_password(
            hashed_password=user.password,
            email=user.email,
            plaintext_password="foo",
            user_id=user.id,
        )

        updated_user_auth = mock_user_auth_repository.update.call_args.kwargs[
            "instance"
        ]
        assert updated_user_auth.external_id == external_id
        assert mock_user_activity_service.create.called

    @staticmethod
    def test_check_password_idp_user_auth_invalid(
        mock_idp_auth_client,
        mock_user_auth_repository,
        mock_idp_management_client,
        mock_user_service,
        mock_user_activity_service,
    ):
        # Given
        user = factories.UserFactory.create(id=123)
        user_auth = factories.UserAuthFactory.create(
            user_id=user.id, external_id="auth0|abcd1234"
        )
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            user_service=mock_user_service,
            user_activity_service=mock_user_activity_service,
        )
        mock_user_auth_repository.get_by_user_id.return_value = user_auth
        mock_idp_auth_client.create_token.side_effect = IdentityClientError(
            500, "Create failed"
        )

        # When/Then
        valid = authn.check_password(
            hashed_password=user.password,
            email=user.email,
            plaintext_password="foo",
            user_id=user.id,
        )

        assert valid is False
        assert not mock_user_activity_service.create.called

    @staticmethod
    def test_check_password_idp_failed_migration(
        mock_idp_auth_client,
        mock_user_auth_repository,
        mock_idp_management_client,
        mock_user_service,
        mock_user_activity_service,
    ):
        # Given
        user = factories.UserFactory.create(id=123)
        external_id = "auth0|999"
        user_auth = factories.UserAuthFactory.create(user_id=user.id, external_id=None)
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
            user_service=mock_user_service,
            user_activity_service=mock_user_activity_service,
        )
        mock_user_auth_repository.get_by_user_id.return_value = user_auth
        # Searching for the user failed to return anything, indicating a failed user migration
        mock_idp_management_client.search_by_email.return_value = None
        # The user is then created in the IDP
        mock_idp_management_client.search_by_email.return_value = IDPUser(
            user_id=external_id
        )
        # The password gets randomized, so the auth attempt fails
        mock_idp_auth_client.create_token.return_value = None

        # When
        success = authn.check_password(
            hashed_password=user.password,
            email=user.email,
            plaintext_password="foo",
            user_id=user.id,
        )

        updated_user_auth = mock_user_auth_repository.update.call_args.kwargs[
            "instance"
        ]
        assert updated_user_auth.external_id == external_id
        assert success is False
        assert not mock_user_activity_service.create.called

    @staticmethod
    def test_create_auth_user_idp(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user_id = 999
        external_id = "auth0|abcd1234"
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            management_client=mock_idp_management_client,
            user_auth=mock_user_auth_repository,
        )
        mock_idp_management_client.search_by_email.return_value = IDPUser(
            user_id=external_id
        )
        mock_idp_management_client.create_user.return_value = IDPUser(
            user_id=external_id
        )
        # When
        created_user_auth = authn.create_auth_user(
            email="email",
            password="password",
            user_id=user_id,
        )
        # Then
        assert created_user_auth.user_id == external_id

    @staticmethod
    def test_create_auth_user_idp_failure(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user_id = 999
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            management_client=mock_idp_management_client,
            user_auth=mock_user_auth_repository,
        )
        mock_idp_management_client.create_user.return_value = None
        # When
        created_user_auth = authn.create_auth_user(
            email="email",
            password="password",
            user_id=user_id,
        )
        # Then
        assert mock_user_auth_repository.create.call_args is None
        assert created_user_auth is None

    @staticmethod
    def test_create_auth_user_idp_client_error(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user_id = 999
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            management_client=mock_idp_management_client,
            user_auth=mock_user_auth_repository,
        )
        mock_idp_management_client.create_user.side_effect = DuplicateResourceError(
            "User already exists"
        )
        # When/Then
        result = authn.create_auth_user(
            email="email",
            password="password",
            user_id=user_id,
        )
        assert result is not None
        assert mock_user_auth_repository.create.call_args is None

    @staticmethod
    def test_update_password_idp(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user = factories.UserFactory.create(id=123)
        external_id = "auth0|999"
        user_auth = factories.UserAuthFactory.create(
            user_id=user.id, external_id=external_id
        )
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        mock_user_auth_repository.get_by_user_id.return_value = user_auth

        # When
        authn.update_password(user_id=user.id, email=user.email, password=user.password)

        # Then
        update_call_args = mock_idp_management_client.update_user.call_args
        assert update_call_args.args == (external_id,)
        assert update_call_args.kwargs == {"password": user.password}

    @staticmethod
    def test_delete_user(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user = factories.UserFactory.create(id=123)
        external_id = "auth0|999"
        user_auth = factories.UserAuthFactory.create(
            user_id=user.id, external_id=external_id
        )
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        mock_user_auth_repository.get_by_user_id.return_value = user_auth

        # When
        authn.delete_user(user_id=user.id)

        # Then
        delete_call_args = mock_idp_management_client.delete_user.call_args
        assert delete_call_args.kwargs == {"external_id": external_id}

    @staticmethod
    def test_update_password_bad_migration(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user = factories.UserFactory.create(id=123)
        external_id = "auth0|999"
        user_auth = factories.UserAuthFactory.create(
            user_id=user.id, external_id=external_id
        )
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        mock_user_auth_repository.get_by_user_id.return_value = user_auth

        # When
        authn.update_password(user_id=user.id, email=user.email, password=user.password)

        # Then
        update_call_args = mock_idp_management_client.update_user.call_args
        assert update_call_args.args == (external_id,)
        assert update_call_args.kwargs == {"password": user.password}

    @staticmethod
    def test_update_email_idp(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user = factories.UserFactory.create(id=123)
        external_id = "auth0|999"
        new_email = "new_email@example.com"
        user_auth = factories.UserAuthFactory.create(
            user_id=user.id, external_id=external_id
        )
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        mock_user_auth_repository.get_by_user_id.return_value = user_auth

        # When
        authn.update_email(user_id=user.id, email=user.email, new_email=new_email)

        # Then
        update_call_args = mock_idp_management_client.update_user.call_args
        assert update_call_args.args == (external_id,)
        assert update_call_args.kwargs == {"email": new_email}

    @staticmethod
    def test_update_metadata(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user = factories.UserFactory.create(id=123)
        external_id = "auth0|999"
        roles = ["member"]
        app_metadata = {"maven_user_identities": roles}
        user_auth = factories.UserAuthFactory.create(
            user_id=user.id, external_id=external_id
        )
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        mock_user_auth_repository.get_by_user_id.return_value = user_auth

        # When
        authn.update_metadata(user_id=user.id, app_metadata=app_metadata)

        # Then
        update_call_args = mock_idp_management_client.update_user.call_args
        assert update_call_args.args == (external_id,)
        assert update_call_args.kwargs == {
            "app_metadata": {"maven_user_identities": roles},
        }

    @staticmethod
    def test_update_metadata_set_external_id(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user = factories.UserFactory.create(id=123)
        external_id = "auth0|999"
        roles = ["member"]
        app_metadata = {"maven_user_identities": roles}
        user_auth = factories.UserAuthFactory.create(user_id=user.id, external_id=None)
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        mock_user_auth_repository.get_by_user_id.return_value = user_auth
        mock_idp_management_client.search_by_email.return_value = IDPUser(
            user_id=external_id
        )

        # When
        authn.update_metadata(user_id=user.id, app_metadata=app_metadata)

        # Then
        update_call_args = mock_idp_management_client.update_user.call_args
        assert update_call_args.args == (external_id,)
        assert update_call_args.kwargs == {
            "app_metadata": {"maven_user_identities": roles},
        }

    @staticmethod
    def test_update_metadata_missing_app_metadata(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user = factories.UserFactory.create(id=123)
        external_id = "auth0|999"
        app_metadata = {}
        user_auth = factories.UserAuthFactory.create(
            user_id=user.id, external_id=external_id
        )
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        mock_user_auth_repository.get_by_user_id.return_value = user_auth

        # When
        authn.update_metadata(user_id=user.id, app_metadata=app_metadata)

        # Then
        update_call_args = mock_idp_management_client.update_user.call_args
        assert update_call_args is None

    @staticmethod
    def test_update_user_ids_in_idp_and_user_auth_table_success(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        internal_user_id = 123
        external_user_id = "idp-user-id"
        user = factories.UserFactory.create(id=internal_user_id)
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        mock_idp_management_client.search_by_email.return_value = IDPUser(
            user_id=external_user_id
        )
        mock_user_auth_repository.get_by_user_id.return_value = None

        # When
        authn.update_idp_user_and_user_auth_table(
            user_id=user.id, email=user.email, password=user.password
        )

        # Then
        update_user_call_args = mock_idp_management_client.update_user.call_args
        assert update_user_call_args.args == (external_user_id,)
        assert update_user_call_args.kwargs == {
            "password": user.password,
            "app_metadata": {"maven_user_id": internal_user_id},
        }
        create_user_auth_call_args = mock_user_auth_repository.create.call_args
        user_auth = UserAuth(user_id=internal_user_id, external_id=external_user_id)
        assert create_user_auth_call_args.kwargs == {"instance": user_auth}

    @staticmethod
    def test_update_user_ids_in_idp_and_user_auth_table_fails_with_idp_error(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user = factories.UserFactory.create(id=123)
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        mock_idp_management_client.update_user.side_effect = IdentityClientError(
            500, "error"
        )

        # When/Then
        with pytest.raises(IdentityClientError):
            authn.update_idp_user_and_user_auth_table(
                user_id=user.id, email=user.email, password=user.password
            )
        assert mock_user_auth_repository.create.call_args is None

    @staticmethod
    def test_insert_user_auth_data_from_authn_api(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        # Given
        user_auth = factories.UserAuthFactory.create(id=11)
        user_auth_dict: dict = user_auth.__dict__
        user_auth_dict["updated_at"] = user_auth_dict["modified_at"]
        user_auth_dict.pop("modified_at")
        # user_dict is the original data, it simulates the raw data from the authn-api
        # When
        authn.insert_user_auth_data_from_authn_api(data=user_auth_dict)
        # Then
        ret = authn.get_user_auth_by_id(user_auth_id=user_auth.id)
        assert ret is not None

    @staticmethod
    def test_update_user_auth_data_from_authn_api(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        # Given
        user_auth = factories.UserAuthFactory.create(id=12)
        user_auth_dict: dict = user_auth.__dict__
        user_auth_dict["updated_at"] = user_auth_dict["modified_at"]
        user_auth_dict.pop("modified_at")
        # user_dict is the original data, it simulates the raw data from the authn-api
        authn.insert_user_auth_data_from_authn_api(data=user_auth_dict)
        update_data = user_auth_dict
        update_data["external_id"] = "test_update"
        user_auth_dict["updated_at"] = user_auth_dict["modified_at"]
        user_auth_dict.pop("modified_at")
        # When
        authn.update_user_auth_data_from_authn_api(data=user_auth_dict)
        # Then
        ret = authn.get_user_auth_by_id(user_auth_id=user_auth.id)
        assert ret is not None

    @staticmethod
    def test_insert_org_auth_data_from_authn_api(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        # Given
        org_auth = factories.OrganizationAuthFactory.create(id=1)
        org_auth_dict: dict = org_auth.__dict__
        org_auth_dict["updated_at"] = org_auth_dict["modified_at"]
        org_auth_dict.pop("modified_at")
        # user_dict is the original data, it simulates the raw data from the authn-api
        # When
        authn.insert_org_auth_data_from_authn_api(data=org_auth_dict)
        # Then
        ret = authn.get_org_auth_by_id(org_auth_id=org_auth.id)
        assert ret is not None

    @staticmethod
    def test_update_org_auth_data_from_authn_api(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        authn = AuthenticationService(
            auth_client=mock_idp_auth_client,
            user_auth=mock_user_auth_repository,
            management_client=mock_idp_management_client,
        )
        # Given
        org_auth = factories.OrganizationAuthFactory.create(id=2)
        org_auth_dict: dict = org_auth.__dict__
        org_auth_dict["updated_at"] = org_auth_dict["modified_at"]
        org_auth_dict.pop("modified_at")
        # user_dict is the original data, it simulates the raw data from the authn-api
        authn.insert_org_auth_data_from_authn_api(data=org_auth_dict)
        update_data = org_auth_dict
        update_data["mfa_required"] = True
        org_auth_dict["updated_at"] = org_auth_dict["modified_at"]
        org_auth_dict.pop("modified_at")
        # When
        authn.update_org_auth_data_from_authn_api(data=org_auth_dict)
        # Then
        ret = authn.get_org_auth_by_id(org_auth_id=org_auth.id)
        assert ret is not None


class TestE2EAuthenticationService:
    @staticmethod
    def test_create_auth_user_idp(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user_id = 999
        external_id = "auth0|abcd1234"
        authn = E2EAuthenticationService(
            auth_client=mock_idp_auth_client,
            management_client=mock_idp_management_client,
            user_auth=mock_user_auth_repository,
        )
        mock_idp_management_client.search.return_value = [
            {
                "user_id": external_id,
                "app_metadata": {"pool_user_id": "test-pool-user-1@mavenclinic.com"},
            }
        ]
        with mock.patch("authn.domain.service.authn.lock") as m:
            mock_lock = m.Lock()
            mock_lock.locked.return_value = False
            mock_lock.acquire.return_value = True
            # When
            authn.create_auth_user(
                email="new_email",
                password="new_password",
                user_id=user_id,
            )
            # Then
            update_calls = mock_idp_management_client.update_user.call_args_list
            assert update_calls[0].kwargs["external_id"] == external_id
            assert update_calls[0].kwargs["email"] == "new_email"
            assert update_calls[1].kwargs["external_id"] == external_id
            assert update_calls[1].kwargs["password"] == "new_password"

    @staticmethod
    def test_create_auth_user_idp_pool_exhausted(
        mock_idp_auth_client, mock_idp_management_client, mock_user_auth_repository
    ):
        # Given
        user_id = 999
        external_id = "auth0|abcd1234"
        authn = E2EAuthenticationService(
            auth_client=mock_idp_auth_client,
            management_client=mock_idp_management_client,
            user_auth=mock_user_auth_repository,
        )
        mock_idp_management_client.search.return_value = [
            {
                "user_id": external_id,
                "app_metadata": {"pool_user_id": "test-pool-user-1@mavenclinic.com"},
            }
        ]

        # When/Then
        with pytest.raises(AuthenticationServiceError):
            with mock.patch("authn.domain.service.authn.lock") as m:
                mock_lock = m.Lock()
                mock_lock.locked.return_value = True
                mock_lock.acquire.return_value = False

                authn.create_auth_user(
                    email="new_email",
                    password="new_password",
                    user_id=user_id,
                )
