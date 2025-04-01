import base64
import json
from datetime import datetime, timedelta
from unittest import mock

import factory
import pymysql.err
import pytest
import requests
from flask.wrappers import Response
from sqlalchemy import exc
from sqlalchemy.exc import IntegrityError
from werkzeug import security

from authn.errors.idp.client_error import (
    REQUEST_TIMEOUT_ERROR,
    UNAUTHORIZED_STATUS,
    DuplicateResourceError,
    RateLimitError,
    RequestsError,
)
from authn.models import user as model
from authn.pytests.factories import IdentityProviderFactory, UserExternalIdentityFactory
from authn.resources import user
from authn.resources.auth import UNAUTHORIZED
from authn.services.integrations.idp import IDPIdentity, IDPUser
from common.services.stripe import StripeCustomerClient
from models import referrals
from pytests import factories
from storage.connection import db

# region: user creation


@pytest.fixture
def email_domain_denylist():
    return factories.EmailDomainDenylistFactory.create(domain="denied.com")


@pytest.mark.parametrize(
    argnames="options,expected_status",
    argvalues=[
        (
            {
                "email": "foo@example.com",
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "$ecretW0rd",
                "username": "foobar",
            },
            200,
        ),
        (
            {
                "email": "foo@example.com",
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "kxパスワードFghs密码👌394",
            },
            200,
        ),
        (
            {
                "email": "\xa0foo@example.com",  # \xa0 is a non-breaking space
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "$ecretW0rd",
                "username": "foobar",
            },
            400,
        ),
        (
            {
                "email": "f2345678911234567892123456789312345678941234567895"
                "12345678961234@example.com",  # 64 character max in local section
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "$ecretW0rd",
                "username": "foobar",
            },
            200,
        ),
        (
            {
                "email": "f2345678911234567892123456789312345678941234567895"
                "123456789612345@example.com",  # 64 character max in local section
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "$ecretW0rd",
                "username": "foobar",
            },
            400,
        ),
        (
            {
                "email": "foo@eabcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd."
                "abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd."
                "abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd."
                "abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd."
                "abcd.abcd.abcd.abcd.abcde.com",  # 255 character max in domain section
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "$ecretW0rd",
                "username": "foobar",
            },
            200,
        ),
        (
            {
                "email": "foo@eabcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd."
                "abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd."
                "abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd."
                "abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd.abcd."
                "abcd.abcd.abcd.abcd.abcdef.com",  # 255 character max in domain section
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "$ecretW0rd",
                "username": "foobar",
            },
            400,
        ),
        (
            {
                "email": "foo@example.com",
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "foo@example.com",
            },
            400,
        ),
        (
            {
                "email": "foo@example.com",
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "f",
            },
            400,
        ),
        (
            {
                "email": "foo@denied.com",
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "$ecretW0rd",
                "username": "foobar",
            },
            400,
        ),
        (
            {
                "email": "foo@DENIED.com",
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "$ecretW0rd",
                "username": "foobar",
            },
            400,
        ),
        (
            {
                "email": "foo@notdenied.com",
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "$ecretW0rd",
                "username": "foobar",
            },
            200,
        ),
        (
            {
                "email": "foo@denied.jk.not.com",
                "first_name": "Foo",
                "last_name": "Bar",
                "password": "$ecretW0rd",
                "username": "foobar",
            },
            200,
        ),
    ],
    ids=[
        "success-basic",
        "success-utf8-email-null-username",
        "error-bad-email",
        "success-email-64-char-username",
        "error-bad-email-65-char-username",
        "success-email-255-char-domain",
        "error-bad-email-256-char-domain",
        "error-email-password-match",
        "error-short-password",
        "error-denied-email-domain",
        "error-denied-email-domain-case-insensitive",
        "success-email-domain-ends-with-denied-domain",
        "success-email-domain-contains-partial-denied-domain",
    ],
)
def test_create_user(
    options: dict, expected_status: int, client, api_helpers, email_domain_denylist
):
    # When
    response = client.post(
        "/api/v1/users",
        data=json.dumps(options),
        headers=api_helpers.json_headers(None),
    )
    # Then
    assert response.status_code == expected_status

    data = api_helpers.load_json(response)
    assert "created_at" not in data


@pytest.mark.parametrize(
    argnames="options,changes,expected_status",
    argvalues=[
        (
            {"email": "peach@mushroom-mail.com"},
            {"first_name": "Peach", "username": "plumberlover82"},
            400,
        ),
        (
            {"username": "plumberlover82"},
            {
                "first_name": "Peach",
                "username": "plumberlover82",
                "email": "peach@mushroom-mail.com",
            },
            400,
        ),
        (
            {"email": "peach@mushroom-mail.com", "username": "plumberlover82"},
            {"first_name": "Peach", "username": "plumberlover82"},
            400,
        ),
        (
            {"email": "peach@mushroom-mail.com"},
            {"first_name": "Peach"},
            400,
        ),
        (
            {"email": "peach@mushroom-mail.com"},
            {"email": "PEACH@mushroom-mail.com", "first_name": "Peach"},
            400,
        ),
        (
            {"email": "peach@mushroom-mail.com", "username": "plumberlover82"},
            {
                "email": "peach82@mushroom-mail.com",
                "username": "PLUMBERLOVER82",
                "first_name": "Peach",
            },
            400,
        ),
    ],
    ids=[
        "duplicate-email",
        "duplicate-username",
        "duplicate-email-and-username",
        "duplicate-email-null-username",
        "duplicate-email-case-insensitive",
        "duplicate-username-case-insensitive",
    ],
)
def test_create_user_conflict(
    options: dict, changes: dict, expected_status: int, client, api_helpers
):
    # Given
    existing = factories.DefaultUserFactory.create(**options)
    payload = {**options, **changes}
    # When
    response = client.post(
        "/api/v1/users",
        data=api_helpers.json_data(payload),
        headers=api_helpers.json_headers(None),
    )
    users = db.session.query(model.User).all()
    # Then
    assert response.status_code == expected_status
    assert users == [existing]


def test_no_usernames_different_emails(client, api_helpers):
    # Given
    data = {
        "email": "foo@example.com",
        "username": None,
        "first_name": "Foo",
        "last_name": "Bar",
        "password": "$ecretW0rd",
    }
    factories.DefaultUserFactory.create(**data)
    # When
    new_data = {**data, "email": "foo2@example.com"}
    client.post(
        "/api/v1/users",
        data=api_helpers.json_data(new_data),
        headers=api_helpers.json_headers(None),
    )
    # Then
    users = db.session.query(model.User).count()
    assert users == 2


def test_integrity_error(client, api_helpers):
    # Given
    data = {
        "email": "foo@example.com",
        "first_name": "Foo",
        "last_name": "Bar",
        "password": "$ecretW0rd",
        "username": "foobar",
    }
    # When

    def error():
        raise exc.IntegrityError("foo", {}, pymysql.err.IntegrityError())

    with mock.patch.object(db.session, "flush", side_effect=error):
        res = client.post(
            "/api/v1/users",
            data=api_helpers.json_data(data),
            headers=api_helpers.json_headers(None),
        )
    # Then
    assert res.status_code, 409


def test_signup_with_referral_code(client, api_helpers):
    # Given
    code = referrals.ReferralCode()
    value = referrals.ReferralCodeValue(code=code, for_user_type="member", value=10)
    db.session.add(code)
    db.session.add(value)
    db.session.commit()
    data = {
        "email": "foo@example.com",
        "first_name": "Foo",
        "last_name": "Bar",
        "password": "$ecretW0rd",
        "username": "foobar",
        "referral_code": code.code,
    }
    # When
    client.post(
        "/api/v1/users",
        data=api_helpers.json_data(data),
        headers=api_helpers.json_headers(None),
    )
    user = model.User.query.one()
    # Then
    assert len(code.uses) == 1 and code.uses[0].user_id == user.id


# endregion
# region: user updates


@pytest.mark.parametrize(
    argnames="options,changes,expected_status",
    argvalues=[
        ({"first_name": "Zelda"}, {"first_name": "Buttercup"}, 200),
        ({"username": "hyruleprincess84"}, {"username": "farmgirlprincess15"}, 200),
        ({"username": "hyruleprincess84"}, {"username": "hyruleprincess84"}, 200),
        ({"username": ""}, {"username": None}, 200),
        ({"username": None}, {"username": None}, 200),
        ({"middle_name": ""}, {"middle_name": ""}, 200),
        ({"middle_name": None}, {"middle_name": ""}, 200),
    ],
    ids=[
        "change-first-name",
        "change-username",
        "change-username-noop",
        "change-username-empty-string-to-None",
        "change-username-None-to-None",
        "change-middle-name-empty-string-to-empty-string",
        "change-middle-name-None-to-empty-string",
    ],
)
def test_update_user(
    options: dict, changes: dict, expected_status: int, client, api_helpers
):
    # Given
    user = factories.DefaultUserFactory.create(**options)
    url = f"/api/v1/users/{user.id}"
    headers = api_helpers.json_headers(user)
    # When
    response = client.put(url, data=json.dumps(changes), headers=headers)
    result = json.loads(response.data.decode())
    # Then
    assert response.status_code == expected_status
    assert {k: result[k] for k in changes} == changes, result


def test_cannot_update_two_users_with_same_username(client, api_helpers):
    # Given. Create the first user (without any variable assigned), then the second user.
    factories.DefaultUserFactory.create(**{"username": "hyruleprincess84"})
    user2 = factories.DefaultUserFactory.create(**{"username": ""})
    url2 = f"/api/v1/users/{user2.id}"
    headers2 = api_helpers.json_headers(user2)
    # When 2nd user tries to change username to be the same as 1st user's username
    response = client.put(
        url2, data=json.dumps({"username": "hyruleprincess84"}), headers=headers2
    )
    # Then
    assert response.status_code == 400
    assert response.json["message"] == "Username already taken!"


@pytest.mark.parametrize(
    argnames="options,changes,expected_status,ff_value",
    argvalues=[
        (
            {"email": "zelda@hyrule-castle.com"},
            {"email": "buttercup@dread-pirate.co.uk"},
            403,
            False,
        ),
        (
            {"email": "zelda@hyrule-castle.com"},
            {"email": "buttercup@dread-pirate.co.uk"},
            200,
            True,
        ),
        (
            {"email": "zelda@hyrule-castle.com"},
            {"email": "bad_email"},
            400,
            True,
        ),
    ],
    ids=[
        "change-email-fail-ff-false",
        "change-email-success-ff-true",
        "change-email-fail-ff-true-bad-email",
    ],
)
def test_update_user_email(
    options: dict,
    changes: dict,
    expected_status: int,
    ff_value: bool,
    client,
    api_helpers,
    ff_test_data,
    mock_authn_service,
):
    # Given
    ff_test_data.update(
        ff_test_data.flag("auth0-email-mfa").variation_for_all(ff_value)
    )
    if ff_value:
        mock_authn_service.update_email.return_value = True
    user = factories.DefaultUserFactory.create(**options)
    url = f"/api/v1/users/{user.id}"
    headers = api_helpers.json_headers(user)
    # When
    response = client.put(url, data=json.dumps(changes), headers=headers)
    # Then
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    argnames="options,changes,expected_status,ff_value",
    argvalues=[
        (
            {"email": "zelda@hyrule-castle.com"},
            {"email": "buttercup@dread-pirate.co.uk"},
            400,
            True,
        ),
    ],
    ids=[
        "change-email-fail",
    ],
)
def test_update_user_email_existing(
    options: dict,
    changes: dict,
    expected_status: int,
    ff_value: bool,
    client,
    api_helpers,
    ff_test_data,
):
    # Given
    ff_test_data.update(
        ff_test_data.flag("auth0-email-mfa").variation_for_all(ff_value)
    )
    user = factories.DefaultUserFactory.create(**options)
    factories.DefaultUserFactory.create(**{"email": "buttercup@dread-pirate.co.uk"})
    url = f"/api/v1/users/{user.id}"
    headers = api_helpers.json_headers(user)
    # When
    response = client.put(url, data=json.dumps(changes), headers=headers)
    # Then
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    argnames="options,changes,expected_status,ff_value",
    argvalues=[
        (
            {"email": "zelda@hyrule-castle.com"},
            {"email": "buttercup@dread-pirate.co.uk"},
            400,
            True,
        ),
    ],
    ids=[
        "change-email-fail",
    ],
)
def test_update_user_email_auth0_call_fail(
    options: dict,
    changes: dict,
    expected_status: int,
    ff_value: bool,
    client,
    api_helpers,
    ff_test_data,
    mock_authn_service,
):
    # Given
    ff_test_data.update(
        ff_test_data.flag("auth0-email-mfa").variation_for_all(ff_value)
    )
    mock_authn_service.update_email.side_effect = RateLimitError
    user = factories.DefaultUserFactory.create(**options)
    url = f"/api/v1/users/{user.id}"
    headers = api_helpers.json_headers(user)
    # When
    response = client.put(url, data=json.dumps(changes), headers=headers)
    # Then
    assert response.status_code == expected_status


def test_change_list_payload(client, api_helpers):
    # Given
    user = factories.DefaultUserFactory.create()
    url = f"/api/v1/users/{user.id}"
    headers = api_helpers.json_headers(user)
    # When
    res = client.put(
        url,
        data="[]",
        headers=headers,
    )
    assert res.status_code == 400


def test_change_password(client, api_helpers):
    # Given
    password = "$ecretW0rd"
    user = factories.DefaultUserFactory.create()
    url = f"/api/v1/users/{user.id}"
    payload = {
        "old_password": user.password,
        "new_password": password + "!@78",
    }
    # When
    response = client.put(
        url,
        data=json.dumps(payload),
        headers=api_helpers.json_headers(user),
    )
    # Then
    assert response.status_code == 200, response.data


def test_start_delete_request(client, api_helpers, enterprise_user):
    with mock.patch("utils.slack_v2.notify_gdpr_delete_user_request_channel"):
        with mock.patch("models.gdpr.GDPRUserRequest"):
            resp = client.post(
                f"/api/v1/users/start_delete_request/{enterprise_user.id}",
                headers=api_helpers.json_headers(enterprise_user),
            )
            assert resp.status_code == 204


class TestDeleteUserProfiles:
    def test_delete_marketplace_user_permanently(self, client, api_helpers):
        # Given
        marketplace_user = factories.DefaultUserFactory.create()
        marketplace_user_schedule = factories.ScheduleFactory.create(
            user=marketplace_user
        )
        assert marketplace_user.schedule == marketplace_user_schedule
        user_id = marketplace_user.id
        # Check that user exists in db
        user = db.session.query(model.User).get(user_id)
        assert user == marketplace_user
        data = {"email": marketplace_user.email}
        # When
        resp = client.delete(
            f"/api/v1/users/{user_id}?flag=gdpr",
            data=json.dumps(data),
            headers=api_helpers.json_headers(marketplace_user),
        )
        assert resp.status == "400 BAD REQUEST"
        assert resp.status_code == 400
        assert (
            resp.json["error"]
            == "Only members can be forgotten. Use practitioner deactivation for practitioners."
        )

    def test_delete_marketplace_user_permanently__error(self, client, api_helpers):
        # Given
        marketplace_user = factories.DefaultUserFactory.create()
        marketplace_user_schedule = factories.ScheduleFactory.create(
            user=marketplace_user
        )
        assert marketplace_user.schedule == marketplace_user_schedule
        user_id = marketplace_user.id
        # Check that user exists in db
        user = db.session.query(model.User).get(user_id)
        assert user == marketplace_user
        data = {"email": marketplace_user.email}
        # When
        resp = client.delete(
            f"/api/v1/users/{user_id}?flag=gdpr_v2",
            data=json.dumps(data),
            headers=api_helpers.json_headers(marketplace_user),
        )
        assert resp.status == "400 BAD REQUEST"
        assert resp.status_code == 400
        assert resp.json["error"] == "requested_date missing or value is not provided."

    @staticmethod
    def confirm_user_is_inactive(test_user: model.User):
        assert test_user.first_name is None
        assert test_user.middle_name is None
        assert test_user.last_name is None
        assert test_user.username is None
        assert test_user.active is False
        assert "hello+GDPR" in test_user.email
        assert test_user.email_confirmed is True
        assert test_user.api_key is None
        assert test_user.image_id is None
        assert test_user.otp_secret is None

    def test_delete_enterprise_user_permanently(
        self, client, api_helpers, enterprise_user
    ):
        # Given
        factories.GDPRUserRequestFactory.create(
            user_id=enterprise_user.id, user_email=enterprise_user.email
        )
        member_schedule = factories.ScheduleFactory.create(user=enterprise_user)
        assert enterprise_user.schedule == member_schedule
        user_id = enterprise_user.id
        # Check that user exists in db and is an enterprise member
        user = db.session.query(model.User).get(user_id)
        assert user == enterprise_user
        assert user.role_name == "member"
        data = {"email": enterprise_user.email}
        # When
        with mock.patch("utils.data_management.unsubscribe_user_from_mailchimp"):
            with mock.patch.object(StripeCustomerClient, "delete_customer"):
                with mock.patch("messaging.services.zendesk.permanently_delete_user"):
                    resp = client.delete(
                        f"/api/v1/users/{user_id}?flag=gdpr",
                        data=json.dumps(data),
                        headers=api_helpers.json_headers(enterprise_user),
                    )
                    assert resp.status == "204 NO CONTENT"
                    assert resp.status_code == 204
                    user = db.session.query(model.User).get(user_id)
                    # Then
                    self.confirm_user_is_inactive(user)

        # Deleting an already deleted user results in 401 response
        resp = client.delete(
            f"/api/v1/users/{user_id}?flag=gdpr",
            data=json.dumps(data),
            headers=api_helpers.json_headers(enterprise_user),
        )
        assert resp.status_code == 401
        assert resp.json["message"] == UNAUTHORIZED
        user = db.session.query(model.User).get(user_id)
        self.confirm_user_is_inactive(user)

    @mock.patch("utils.data_management.delete_user")
    def test_delete_user_permanently_raises_exception(
        self, delete_mock, client, api_helpers, enterprise_user
    ):
        # Any kind of server-side unexpected exception will work
        delete_mock.side_effect = requests.exceptions.ConnectionError()
        data = {"email": enterprise_user.email}
        resp = client.delete(
            f"/api/v1/users/{enterprise_user.id}?flag=gdpr",
            data=json.dumps(data),
            headers=api_helpers.json_headers(enterprise_user),
        )
        assert resp.status_code == 500

    def test_delete_inactive_user_raises_exception(
        self, client, api_helpers, enterprise_user
    ):
        enterprise_user.active = False
        data = {"email": enterprise_user.email}
        resp = client.delete(
            f"/api/v1/users/{enterprise_user.id}?flag=gdpr",
            data=json.dumps(data),
            headers=api_helpers.json_headers(enterprise_user),
        )
        assert resp.json["message"] == UNAUTHORIZED
        assert resp.status_code == 401

    def test_delete_user_with_tracks_less_than_1_week_old(
        self, factories, client, api_helpers, mock_authn_service
    ):
        # Given
        user = factories.DefaultUserFactory.create()
        factories.MemberTrackFactory(
            user=user, created_at=datetime.utcnow() - timedelta(days=3)
        )
        assert len(user.active_tracks) == 1
        mock_authn_service.user_access_control.return_value = None

        # When
        url = f"/api/v1/users/{user.id}"
        headers = api_helpers.json_headers(user)
        resp = client.delete(url, headers=headers)

        # Then
        assert resp.status_code == 204
        assert user.active is False
        assert len(user.active_tracks) == 0
        assert mock_authn_service.user_access_control.call_count == 1

    def test_delete_user_with_tracks_greater_than_1_week_old(
        self, factories, client, api_helpers, mock_authn_service
    ):
        # Given
        user = factories.DefaultUserFactory.create()
        factories.MemberTrackFactory(
            user=user, created_at=datetime.utcnow() - timedelta(days=8)
        )
        assert len(user.active_tracks) == 1
        mock_authn_service.user_access_control.return_value = None

        # When
        url = f"/api/v1/users/{user.id}"
        headers = api_helpers.json_headers(user)
        resp = client.delete(url, headers=headers)

        # Then
        assert resp.status_code == 204
        assert user.active is False
        assert len(user.active_tracks) == 0

    def test_delete_user_throws_exception(
        self, factories, client, api_helpers, mock_authn_service
    ):
        # Given
        user = factories.DefaultUserFactory.create()
        factories.MemberTrackFactory(
            user=user, created_at=datetime.utcnow() - timedelta(days=3)
        )
        assert len(user.active_tracks) == 1
        mock_authn_service.user_access_control.return_value = None

        # When
        with mock.patch("utils.member_tracks.terminate_track"):
            with mock.patch(
                "models.tracks.terminate",
                side_effect=requests.exceptions.ConnectionError(),
            ):

                url = f"/api/v1/users/{user.id}"
                headers = api_helpers.json_headers(user)
                resp = client.delete(url, headers=headers)

                # Then
                assert resp.status_code == 400
                assert (
                    resp.json["message"]
                    == "Something went wrong when deactivating your account, please try again."
                )

                assert user.active is True
                assert mock_authn_service.user_access_control.call_count == 0
                assert len(user.active_tracks) == 1


@pytest.fixture
def auth_api_mock(mock_twilio, mock_jwt):
    yield


class TestApiKeyResource:
    def test_get_api_key(self, client, api_helpers, mock_authn_service):
        # Given
        user: model.User = factories.DefaultUserFactory.create()
        auth_data = {"email": user.email, "password": user.password}
        expected_headers = {"x-user-id", "x-user-api-key", "x-user-identities"}
        mock_authn_service.check_password.return_value = True
        # When
        response: Response = client.post(
            "/api/v1/api_key",
            data=api_helpers.json_data(auth_data),
            headers=api_helpers.json_headers(),
        )
        received_headers = {*response.headers.keys(lower=True)}
        # Then
        assert response.status_code == 200
        assert received_headers.issuperset(expected_headers)

    def test_get_api_key_no_user(self, client, api_helpers, mock_authn_service):
        # Given
        auth_data = {"email": "foo@bar.com", "password": "password"}
        # When
        response: Response = client.post(
            "/api/v1/api_key",
            data=api_helpers.json_data(auth_data),
            headers=api_helpers.json_headers(),
        )
        # Then
        assert response.status_code == 403

    def test_get_api_bad_password(self, client, api_helpers, mock_authn_service):
        # Given
        auth_data = {"email": "foo@bar.com", "password": "password"}
        mock_authn_service.check_password.return_value = False
        # When
        response: Response = client.post(
            "/api/v1/api_key",
            data=api_helpers.json_data(auth_data),
            headers=api_helpers.json_headers(),
        )
        # Then
        assert response.status_code == 403

    def test_user_mfa_enabled(self, client, api_helpers):
        # Given
        mfa_user: model.User = factories.DefaultUserFactory.create(
            mfa_state=model.MFAState.ENABLED,
            sms_phone_number=factory.Faker("cellphone_number_e_164"),
        )
        auth_data = {"email": mfa_user.email, "password": mfa_user.password}
        expected_headers = {"x-user-id", "x-user-api-key", "x-user-identities"}
        # When
        with mock.patch.object(security, "check_password_hash", return_value=True):
            response: Response = client.post(
                "/api/v1/api_key",
                data=api_helpers.json_data(auth_data),
                headers=api_helpers.json_headers(),
            )
            received_headers = {*response.headers.keys(lower=True)}
        # Then
        assert response.status_code == 200
        assert response.json["mfa"] is not None
        assert received_headers.issuperset(expected_headers)

    def test_get_api_with_create_token_request_timeout(
        self, client, api_helpers, mock_authn_service
    ):
        # Given
        mfa_user: model.User = factories.DefaultUserFactory.create(
            mfa_state=model.MFAState.ENABLED,
            sms_phone_number=factory.Faker("cellphone_number_e_164"),
        )
        auth_data = {"email": mfa_user.email, "password": mfa_user.password}
        mock_authn_service.create_token.side_effect = RequestsError(
            UNAUTHORIZED_STATUS, REQUEST_TIMEOUT_ERROR
        )
        # When
        response = client.post(
            "/api/v1/api_key",
            data=api_helpers.json_data(auth_data),
            headers=api_helpers.json_headers(),
        )
        # Then
        assert response.status_code == 401
        assert response.json["message"] == "Request timed out, please try again later"

    def test_get_api_with_create_token_rate_limiting(
        self, client, api_helpers, mock_authn_service
    ):
        # Given
        mfa_user: model.User = factories.DefaultUserFactory.create(
            mfa_state=model.MFAState.ENABLED,
            sms_phone_number=factory.Faker("cellphone_number_e_164"),
        )
        auth_data = {"email": mfa_user.email, "password": mfa_user.password}
        mock_authn_service.create_token.side_effect = RateLimitError()
        # When
        response = client.post(
            "/api/v1/api_key",
            data=api_helpers.json_data(auth_data),
            headers=api_helpers.json_headers(),
        )
        # Then
        assert response.status_code == 429
        assert response.json["message"] == "Too many requests, try again later"


@mock.patch("authn.domain.service.authn.get_auth_service")
def test_create_idp_user_for_new_user_with_password(
    mock_get_auth_service_call, mock_authn_service
):
    # Given
    test_user = factories.DefaultUserFactory.create()
    mock_get_auth_service_call.return_value = mock_authn_service
    # When
    user.create_idp_user(test_user)
    # Then
    call_args = mock_authn_service.create_auth_user.call_args
    assert call_args.kwargs == {
        "email": test_user.email,
        "password": test_user.password,
        "user_id": test_user.id,
    }
    assert not mock_authn_service.update_idp_user_and_user_auth_table.called


@mock.patch("authn.domain.service.authn.get_auth_service")
def test_create_idp_user_for_new_user_without_password(
    mock_get_auth_service_call, mock_authn_service
):
    # Given
    test_user = factories.DefaultUserFactory.create()
    mock_get_auth_service_call.return_value = mock_authn_service
    # When
    user.create_idp_user(test_user, plain_password="password_in_args")
    # Then
    call_args = mock_authn_service.create_auth_user.call_args
    assert call_args.kwargs == {
        "email": test_user.email,
        "password": "password_in_args",
        "user_id": test_user.id,
    }
    assert not mock_authn_service.update_idp_user_and_user_auth_table.called


@mock.patch("authn.domain.service.authn.get_auth_service")
def test_create_idp_user_for_existing_user(
    mock_get_auth_service_call, mock_authn_service
):
    # Given
    test_user = factories.DefaultUserFactory.create()
    mock_get_auth_service_call.return_value = mock_authn_service
    mock_authn_service.create_auth_user.side_effect = DuplicateResourceError(
        "Cannot create existing user"
    )
    mock_authn_service.update_idp_user_and_user_auth_table.return_value = None
    # When
    user.create_idp_user(test_user)
    # Then
    call_args = mock_authn_service.create_auth_user.call_args
    assert call_args.kwargs == {
        "email": test_user.email,
        "password": test_user.password,
        "user_id": test_user.id,
    }
    call_args = mock_authn_service.update_idp_user_and_user_auth_table.call_args
    assert call_args.args == (test_user.id, test_user.email, test_user.password)


def test_email_addresses_must_be_unique():
    """Many workflows hinge on email addresses being unique."""
    user_1 = factories.EnterpriseUserFactory.create()
    with pytest.raises(IntegrityError):
        factories.EnterpriseUserFactory.create(email=user_1.email)


class TestUserSSORelink:
    url = "/api/v1/users/sso_relink"

    def test_unauthenticated_relink_feature(self, client, api_helpers):
        data = {"user_id": "1", "external_id": "123"}
        response = client.post(
            self.url, data=json.dumps(data), headers=api_helpers.json_headers()
        )

        assert response.status_code == 401

    def test_update_identity_user_id(self, client, api_helpers, mock_sso_service):
        user = factories.DefaultUserFactory.create()
        external_id = "auth0|abcd1234"
        mock_idp_user = IDPUser(user_id=external_id, external_user_id="abc")
        mock_provider = IdentityProviderFactory.create()
        mock_sso_service.retrieval_idp_user.return_value = (
            mock_idp_user,
            mock_provider,
            "con1",
        )

        data = {"user_id": "1", "external_id": "123"}

        response = client.post(
            self.url, data=json.dumps(data), headers=api_helpers.json_headers(user)
        )

        assert response.status_code == 200

    def test_create_identity_for_new_sso_user_ff_on(
        self, client, api_helpers, mock_sso_service, mock_feature_flag_on
    ):
        user = factories.DefaultUserFactory.create()
        external_id = "auth0|abcd1234"
        mock_idp_user = IDPUser(
            user_id=external_id,
            external_user_id="abc",
            first_name="hello",
            last_name="world",
            email="mock@example.com",
        )
        mock_provider = IdentityProviderFactory.create()
        mock_sso_service.retrieval_idp_user.return_value = (
            mock_idp_user,
            mock_provider,
            "con1",
        )
        mock_sso_service.fetch_identity_by_idp_and_external_user_id.return_value = None
        data = {"user_id": "1", "external_id": "123"}

        response = client.post(
            self.url, data=json.dumps(data), headers=api_helpers.json_headers(user)
        )

        assert response.status_code == 200

    def test_create_identity_for_new_sso_user_ff_off(
        self, client, api_helpers, mock_sso_service, mock_feature_flag_off
    ):
        user = factories.DefaultUserFactory.create()
        external_id = "auth0|abcd1234"
        mock_idp_user = IDPUser(
            user_id=external_id,
            external_user_id="abc",
            first_name="hello",
            last_name="world",
            email="mock@example.com",
        )
        mock_provider = IdentityProviderFactory.create()
        mock_sso_service.retrieval_idp_user.return_value = (
            mock_idp_user,
            mock_provider,
            "con1",
        )
        mock_sso_service.fetch_identity_by_idp_and_external_user_id.return_value = None
        data = {"user_id": "1", "external_id": "123"}

        response = client.post(
            self.url, data=json.dumps(data), headers=api_helpers.json_headers(user)
        )

        assert response.status_code == 200

    def test_sso_relink_without_external_user_id(
        self, client, api_helpers, mock_sso_service
    ):
        user = factories.DefaultUserFactory.create()
        external_id = "auth0|abcd1234"
        mock_idp_user = IDPUser(user_id=external_id)
        mock_provider = IdentityProviderFactory.create()
        mock_sso_service.retrieval_idp_user.return_value = (
            mock_idp_user,
            mock_provider,
            "con1",
        )

        data = {"user_id": "1", "external_id": "123"}

        response = client.post(
            self.url, data=json.dumps(data), headers=api_helpers.json_headers(user)
        )

        assert response.status_code == 400

    def test_invalid_request_payload_missing_field(
        self, client, api_helpers, mock_sso_service
    ):
        user = factories.DefaultUserFactory.create()
        external_id = "auth0|abcd1234"
        mock_idp_user = IDPUser(user_id=external_id)
        mock_provider = IdentityProviderFactory.create()
        mock_sso_service.retrieval_idp_user.return_value = (
            mock_idp_user,
            mock_provider,
            "con1",
        )

        data = {"external_id": "123"}

        response = client.post(
            self.url, data=json.dumps(data), headers=api_helpers.json_headers(user)
        )

        assert response.status_code == 400

    def test_invalid_request_payload(self, client, api_helpers, mock_sso_service):
        user = factories.DefaultUserFactory.create()
        external_id = "auth0|abcd1234"
        mock_idp_user = IDPUser(user_id=external_id)
        mock_provider = IdentityProviderFactory.create()
        mock_sso_service.retrieval_idp_user.return_value = (
            mock_idp_user,
            mock_provider,
            "con1",
        )

        data = {"user_id": "", "external_id": "123"}

        response = client.post(
            self.url, data=json.dumps(data), headers=api_helpers.json_headers(user)
        )

        assert response.status_code == 400

    def test_api_incorrectly_be_called(self, client, api_helpers, mock_sso_service):
        user = factories.DefaultUserFactory.create()
        external_id = "auth0|abcd1234"
        mock_idp_user = IDPUser(user_id=external_id, external_user_id="abc")
        mock_provider = IdentityProviderFactory.create()
        mock_sso_service.retrieval_idp_user.return_value = (
            mock_idp_user,
            mock_provider,
            "con1",
        )
        identity = UserExternalIdentityFactory.create(
            external_user_id="mock123", identity_provider_id=1
        )
        mock_sso_service.fetch_identity_by_idp_and_external_user_id.return_value = (
            identity
        )

        data = {"user_id": "1", "external_id": "mock123"}

        response = client.post(
            self.url, data=json.dumps(data), headers=api_helpers.json_headers(user)
        )

        assert response.status_code == 200


class TestSsoUserCreation:
    def test_sso_user_creation(
        self, client, api_helpers, mock_sso_service, mock_user_service
    ):
        external_id = "auth0|abcd1234"
        encoded_external_id = base64.b64encode(external_id.encode("utf-8")).decode(
            "utf-8"
        )
        mock_idp_user = IDPUser(
            user_id=external_id,
            external_user_id="abc",
            identities=[IDPIdentity(provider="samlp", connection="abc")],
        )
        mock_provider = IdentityProviderFactory.create(id=1)
        mock_sso_service.retrieval_idp_user.return_value = (
            mock_idp_user,
            mock_provider,
            "con1",
        )
        mock_sso_service.update_external_user_id_link.return_value = None
        mock_sso_service.identities.get_by_idp_and_external_user_id.return_value = None

        mock_user = factories.DefaultUserFactory.create()
        mock_user_service.create_maven_user.return_value = mock_user

        data = {
            "external_id": encoded_external_id,
            "email": "abc@mock.com",
            "password": "mock1.Password",
        }
        url = "/api/v1/users/sso_user_creation"

        with mock.patch(
            "authn.domain.service.user.post_user_create_steps_v2"
        ) as mock_post_user_create:
            response = client.post(
                url, data=json.dumps(data), headers=api_helpers.json_headers()
            )

            assert response.status_code == 200
            assert response.json["user_id"] == mock_user.id
            assert mock_post_user_create.called

    def test_sso_user_creation_with_ff_on(
        self,
        client,
        api_helpers,
        mock_sso_service,
        mock_user_service,
        mock_feature_flag_on,
    ):
        external_id = "auth0|abcd1234"
        encoded_external_id = base64.b64encode(external_id.encode("utf-8")).decode(
            "utf-8"
        )
        mock_idp_user = IDPUser(
            user_id=external_id,
            external_user_id="abc",
            first_name="hello",
            last_name="world",
            email="ssouser@test.com",
            identities=[IDPIdentity(provider="samlp", connection="mock_con")],
        )
        mock_provider = IdentityProviderFactory.create(id=1)
        mock_sso_service.retrieval_idp_user.return_value = (
            mock_idp_user,
            mock_provider,
            "con1",
        )
        mock_sso_service.update_external_user_id_link.return_value = None
        mock_sso_service.identities.get_by_idp_and_external_user_id.return_value = None

        mock_user = factories.DefaultUserFactory.create()
        mock_user_service.create_maven_user.return_value = mock_user

        data = {
            "external_id": encoded_external_id,
            "email": "abc@mock.com",
            "password": "mock1.Password",
        }
        url = "/api/v1/users/sso_user_creation"

        with mock.patch(
            "authn.domain.service.user.post_user_create_steps_v2"
        ) as mock_post_user_create:
            response = client.post(
                url, data=json.dumps(data), headers=api_helpers.json_headers()
            )

            assert response.status_code == 200
            assert response.json["user_id"] == mock_user.id
            assert mock_post_user_create.called

    def test_sso_user_creation_with_uei_existing(
        self, client, api_helpers, mock_sso_service, mock_user_service
    ):
        external_id = "auth0|abcd1234"
        encoded_external_id = base64.b64encode(external_id.encode("utf-8")).decode(
            "utf-8"
        )
        mock_idp_user = IDPUser(
            user_id=external_id,
            external_user_id="abc",
            identities=[IDPIdentity(provider="samlp", connection="abc")],
        )
        mock_provider = IdentityProviderFactory.create(id=1)
        mock_sso_service.retrieval_idp_user.return_value = (
            mock_idp_user,
            mock_provider,
            "con1",
        )
        identity = UserExternalIdentityFactory.create(
            external_user_id="mock123", identity_provider_id=1
        )
        mock_sso_service.update_external_user_id_link.return_value = None
        mock_sso_service.identities.get_by_idp_and_external_user_id.return_value = (
            identity
        )

        mock_user = factories.DefaultUserFactory.create()
        mock_user_service.create_maven_user.return_value = mock_user

        data = {
            "external_id": encoded_external_id,
            "email": "abc@mock.com",
            "password": "mock1.Password",
        }
        url = "/api/v1/users/sso_user_creation"

        response = client.post(
            url, data=json.dumps(data), headers=api_helpers.json_headers()
        )

        assert response.status_code == 500

    def test_sso_user_creation_with_invalid_request(
        self, client, api_helpers, mock_sso_service
    ):
        data = {"email": "abc@mock.com", "password": "mock.Password"}
        url = "/api/v1/users/sso_user_creation"

        response = client.post(
            url, data=json.dumps(data), headers=api_helpers.json_headers()
        )

        assert response.status_code == 400

    def test_sso_user_creation_with_invalid_auth0_account_info(
        self, client, api_helpers, mock_sso_service, mock_user_service
    ):
        external_id = "auth0|abcd1234"
        encoded_external_id = base64.b64encode(external_id.encode("utf-8")).decode(
            "utf-8"
        )
        mock_idp_user = IDPUser(user_id=external_id)
        mock_provider = IdentityProviderFactory.create()
        mock_sso_service.retrieval_idp_user.return_value = (
            mock_idp_user,
            mock_provider,
            "con1",
        )
        mock_sso_service.update_external_user_id_link.return_value = None

        mock_user = factories.DefaultUserFactory.create()
        mock_user_service.create_maven_user.return_value = mock_user

        data = {
            "external_id": encoded_external_id,
            "email": "abc@mock.com",
            "password": "mock1.Password",
        }
        url = "/api/v1/users/sso_user_creation"

        response = client.post(
            url, data=json.dumps(data), headers=api_helpers.json_headers()
        )

        assert response.status_code == 400


class TestGetUserIdentities:
    def test_get_user_identities_happy_case(
        self, client, api_helpers, mock_user_service
    ):
        mock_user = factories.DefaultUserFactory.create()
        url = f"/api/v1/-/users/get_identities/{mock_user.id}"
        mock_user_service.get_identities.return_value = "identities"
        response = client.get(url, headers=api_helpers.json_headers())
        assert response.status_code == 200
        assert response.json["identities"] == "identities"

    def test_get_user_identities_with_invalid_parameter(self, client, api_helpers):
        url = "/api/v1/-/users/get_identities/123"
        response = client.get(url, headers=api_helpers.json_headers())

        assert response.status_code == 401

    def test_get_user_identities_with_incorrect_path(self, client, api_helpers):
        url = "/api/v1/-/users/get_identities"
        response = client.get(url, headers=api_helpers.json_headers())

        assert response.status_code == 404


class TestGetOrgId:
    def test_get_org_id_happy_case(self, client, api_helpers, mock_mfa_service):
        mock_user = factories.DefaultUserFactory.create()
        url = f"/api/v1/-/users/get_org_id/{mock_user.id}"
        mock_mfa_service.get_org_id_by_user_id.return_value = 1
        response = client.get(url, headers=api_helpers.json_headers())

        assert response.status_code == 200
        assert response.json["org_id"] == 1

    def test_get_org_id_with_invalid_user_id(self, client, api_helpers):
        url = "/api/v1/-/users/get_org_id/123"
        response = client.get(url, headers=api_helpers.json_headers())

        assert response.status_code == 401

    def test_get_user_identities_with_incorrect_path(self, client, api_helpers):
        url = "/api/v1/-/users/get_org_id"
        response = client.get(url, headers=api_helpers.json_headers())

        assert response.status_code == 404


class TestSyncUserData:
    def test_sync_user_data_happy_case(self, client, api_helpers):
        url = "/api/v1/-/users/sync_user_data"
        data = {
            "id": 1,
            "esp_id": "123",
            "email": "1@test.com",
            "active": True,
            "email_confirmed": True,
            "mfa_state": "DISABLED",
            "password": "asdf",
        }
        response = client.post(
            url, data=json.dumps(data), headers=api_helpers.json_headers()
        )

        assert response.status_code == 200

    def test_sync_user_data_invalid_payload(self, client, api_helpers):
        url = "/api/v1/-/users/sync_user_data"
        data = {"sdf": 1}
        response = client.post(
            url, data=json.dumps(data), headers=api_helpers.json_headers()
        )

        assert response.status_code == 400

    def test_sync_user_data_with_no_payload(self, client, api_helpers):
        url = "/api/v1/-/users/sync_user_data"
        response = client.post(url, headers=api_helpers.json_headers())

        assert response.status_code == 400

    def test_sync_user_data_with_incorrect_path(self, client, api_helpers):
        url = "/api/v1/-/users/sync_user_data/11"
        response = client.post(url, headers=api_helpers.json_headers())

        assert response.status_code == 404


class TestUserVerificationEmailResource:
    url = "/api/v1/users/verification_email"

    def test_user_verification_email(self, client, mock_authn_service, api_helpers):
        user = factories.DefaultUserFactory.create()
        mock_authn_service.send_verification_email.return_value = None

        response = client.post(self.url, headers=api_helpers.json_headers(user))

        assert response.status_code == 200

    def test_user_verification_email_failure(
        self, client, mock_authn_service, api_helpers
    ):
        user = factories.DefaultUserFactory.create()
        mock_authn_service.send_verification_email.side_effect = RateLimitError

        response = client.post(self.url, headers=api_helpers.json_headers(user))

        assert response.status_code == 400
