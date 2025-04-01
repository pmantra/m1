from __future__ import annotations

from unittest import mock

import pytest
from onelogin.saml2 import auth

from authn.services.integrations.saml import service, translate


@pytest.fixture
def auth_data(
    faker,
) -> tuple[
    str, auth.OneLogin_Saml2_Auth, service.OneLoginSAMLConfiguration, dict, dict
]:
    mapping = dict(
        email="EmailAddress",
        first_name="firstname",
        last_name="lastname",
        employee_id="EmployeeID",
        rewards_id="MemberID",
        organization_external_id="SponsorID",
    )
    idp = "super-id-maker"
    mock_auth = mock.MagicMock(spec=auth.OneLogin_Saml2_Auth).return_value
    mock_configuration = mock.MagicMock(
        spec=service.OneLoginSAMLConfiguration
    ).return_value
    attribs, translated = {}, {}
    for target, source in mapping.items():
        try:
            factory = getattr(faker, target)
        except AttributeError:
            factory = faker.swift11
        value = factory()
        attribs[source] = [value]
        translated[target] = value

    mock_auth.get_attributes.return_value = attribs
    mock_auth.get_attribute.side_effect = attribs.get
    return idp, mock_auth, mock_configuration, mapping, translated


def test_response_to_assertion(auth_data):
    # Given
    idp, auth_object, configuration, given_mapping, expected_translation = auth_data
    # When
    assertion = translate.response_to_assertion(
        idp=idp, response=auth_object, configuration=configuration, **given_mapping
    )
    translated = {k: getattr(assertion, k) for k in expected_translation}
    # Then
    assert translated == expected_translation


@pytest.fixture(params=sorted(translate._REQUIRED_FIELDS))
def broken_auth_data(
    request, auth_data
) -> tuple[str, auth.OneLogin_Saml2_Auth, service.OneLoginSAMLConfiguration, dict]:
    field = request.param
    idp, mock_auth, mock_configuration, given_mapping, translated = auth_data
    source_field = given_mapping[field]
    mock_auth.get_attributes().pop(source_field)
    return idp, mock_auth, mock_configuration, given_mapping


def test_response_to_assertion_missing_required_field(broken_auth_data):
    # Given
    idp, auth_object, configuration, given_mapping = broken_auth_data
    # When/Then
    with pytest.raises(translate.error.SAMLTranslationError):
        translate.response_to_assertion(
            idp=idp, response=auth_object, configuration=configuration, **given_mapping
        )
