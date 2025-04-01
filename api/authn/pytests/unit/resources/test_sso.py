from __future__ import annotations

from urllib import parse

import pytest

from authn.pytests import factories
from authn.resources import sso


@pytest.mark.parametrize(
    argnames="is_new,expected_redirect",
    argvalues=[
        (
            True,
            sso.SAMLConsumerResource.SET_PASSWORD_PAGE,
        ),
        (
            False,
            sso.SAMLConsumerResource.DASHBOARD_PAGE,
        ),
    ],
    ids=[
        "new-user-to-set-password",
        "existing-user-to-dashboard",
    ],
)
def test_saml_post(mock_sso_service, client, is_new, expected_redirect):
    # Given
    identity = factories.UserExternalIdentityFactory.create()
    mock_sso_service.execute_assertion.return_value = (is_new, identity)
    # When
    response = client.post("/saml/consume/")
    redirect = parse.urlparse(response.headers["location"]).path
    user_id = int(response.headers[sso.SAMLConsumerResource.USER_ID_HEADER])
    # Then
    assert (response.status_code, redirect, user_id) == (
        302,
        expected_redirect,
        user_id,
    )


def test_saml_post_error_handling(mock_sso_service, client, sso_error):
    # Given
    exc, expected_status_code = sso_error
    mock_sso_service.execute_assertion.side_effect = exc
    # When
    response = client.post("/saml/consume/")
    # Then
    assert response.status_code == expected_status_code
