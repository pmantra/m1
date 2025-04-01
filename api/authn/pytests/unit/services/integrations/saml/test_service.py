from __future__ import annotations

from unittest import mock

import pytest

from authn.pytests import factories
from authn.services.integrations import saml


@pytest.fixture
def mock_response_to_assertion():
    with mock.patch(
        "authn.services.integrations.saml.translate.response_to_assertion",
        autospec=True,
    ) as m:
        yield m


def test_parse_assertion(onelogin, mock_response_to_assertion, mock_auth_object):
    # Given
    assertion = factories.SAMLAssertionFactory.create()
    request = factories.SAMLRequestBodyFactory.create()
    mock_response_to_assertion.return_value = assertion
    mock_auth_object.is_authenticated.return_value = True
    onelogin.add_idp("Foo", "Bar")
    # When
    parsed = onelogin.parse_assertion(request)
    # Then
    assert parsed == assertion


def test_parse_assertion_error_fallthru(
    onelogin, mock_response_to_assertion, mock_auth_object
):
    # Given
    assertion = factories.SAMLAssertionFactory.create()
    request = factories.SAMLRequestBodyFactory.create()
    mock_response_to_assertion.return_value = assertion
    mock_auth_object.is_authenticated.side_effect = [False, True]
    onelogin.add_idp("Foo", "Bar")
    onelogin.add_idp("Baz", "Buz")
    # When
    parsed = onelogin.parse_assertion(request)
    # Then
    assert parsed == assertion


def test_parse_assertion_error_all_fail(
    onelogin, mock_response_to_assertion, mock_auth_object
):
    # Given
    assertion = factories.SAMLAssertionFactory.create()
    request = factories.SAMLRequestBodyFactory.create()
    mock_response_to_assertion.return_value = assertion
    mock_auth_object.is_authenticated.side_effect = [False, False]
    onelogin.add_idp("Foo", "Bar")
    onelogin.add_idp("Baz", "Buz")
    # When
    with pytest.raises(saml.SAMLVerificationError) as exc_info:
        onelogin.parse_assertion(request)
    # Then
    assert exc_info.value.auth_errors.keys() == {"foo", "baz"}
