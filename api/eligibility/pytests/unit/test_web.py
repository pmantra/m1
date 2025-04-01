import contextlib
import datetime
from unittest import mock
from unittest.mock import MagicMock

import pytest
from werkzeug import exceptions

from eligibility import service, web
from eligibility.pytests import factories
from eligibility.web import ClientVerificationParameters
from pytests.factories import OrganizationEmployeeFactory, OrganizationFactory


@pytest.mark.parametrize(
    argnames="given_params,expected_type",
    argvalues=[
        (dict(verification_type="multistep"), "multistep"),
        (dict(fileless=True), "fileless"),
        (dict(external_identity=True), "sso"),
        (dict(healthplan=True), "multistep"),
        (dict(standard=True), "standard"),
        (dict(alternate=True), "alternate"),
        (dict(organization_id=1, unique_corp_id="foo"), "client_specific"),
        (dict(), None),
    ],
    ids=[
        "verification-type-override",
        "fileless",
        "external-identity-sso",
        "health-plan-multistep",
        "standard",
        "alternate",
        "client-specific",
        "none-fallthrough",
    ],
)
def test_get_verification_type(given_params, expected_type):
    # When
    verification_type = web.get_verification_type(given_params)
    # Then
    assert verification_type == expected_type


PARSE_PARAMS_TEST_MATRIX = {
    "date-parsing": (
        dict(date_of_birth="1970-01-01", own_date_of_birth="invalid"),
        "standard",
        factories.ServiceVerificationParametersFactory.create(
            date_of_birth=datetime.date(1970, 1, 1)
        ),
    ),
    "datetime-date-parsing": (
        dict(date_of_birth="1970-01-01T00:00:00", own_date_of_birth="invalid"),
        "standard",
        factories.ServiceVerificationParametersFactory.create(
            date_of_birth=datetime.date(1970, 1, 1)
        ),
    ),
    "multistep-corp-id-override": (
        dict(subscriber_id="subscriber", unique_corp_id="sheeple"),
        "multistep",
        factories.ServiceVerificationParametersFactory.create(
            unique_corp_id="subscriber",
        ),
    ),
    "regular-corp-id": (
        dict(subscriber_id="subscriber", unique_corp_id="sheeple"),
        "standard",
        factories.ServiceVerificationParametersFactory.create(
            unique_corp_id="sheeple",
        ),
    ),
    "empty-string-is-null": (
        dict(
            unique_corp_id="",
            first_name="",
            last_name="",
            date_of_birth="",
            company_email="",
        ),
        "alternate",
        factories.ServiceVerificationParametersFactory.create(),
    ),
    "is-employee-json-bool-parsing": (
        dict(
            is_employee="true",
        ),
        "alternate",
        factories.ServiceVerificationParametersFactory.create(is_employee=True),
    ),
    "is-employee-json-int-parsing": (
        dict(
            is_employee="1",
        ),
        "alternate",
        factories.ServiceVerificationParametersFactory.create(is_employee=True),
    ),
    "is-employee-json-empty-string-parsing": (
        dict(
            is_employee="",
        ),
        "alternate",
        factories.ServiceVerificationParametersFactory.create(),
    ),
    "int-parsing": (
        dict(
            organization_id="1",
            eligibility_member_id="1",
        ),
        "alternate",
        factories.ServiceVerificationParametersFactory.create(
            organization_id=1, eligibility_member_id=1
        ),
    ),
    "int-parsing-invalid": (
        dict(eligibility_member_id="foo"),
        "alternate",
        factories.ServiceVerificationParametersFactory.create(),
    ),
}


@pytest.mark.parametrize(
    argnames="given_web_params,verification_type,expected_service_params",
    argvalues=[*PARSE_PARAMS_TEST_MATRIX.values()],
    ids=[*PARSE_PARAMS_TEST_MATRIX.keys()],
)
def test_parse_parameters(given_web_params, verification_type, expected_service_params):
    # When
    parsed_service_params = web.parse_parameters(
        params=given_web_params, verification_type=verification_type
    )
    # Then
    assert parsed_service_params == expected_service_params


@pytest.fixture
def verification_passes(mock_eligibility_service):
    mock_eligibility_service.side_effect = None
    return None


@pytest.fixture
def verification_fails(mock_eligibility_service):
    return service.EnterpriseVerificationFailedError("Oh no!", "standard")


@pytest.fixture(params=["verification-passes", "verification-fails"])
def verification_test_case(
    verification_passes, verification_fails, request, mock_eligibility_service
):
    if request.param == "verification-passes":
        err = verification_passes
        mock_eligibility_service.get_enterprise_association.side_effect = err
        mock_eligibility_service.get_enterprise_association.return_value = (
            factories.VerificationFactory.create()
        )
        return no_error()

    err = verification_fails
    mock_eligibility_service.get_enterprise_association.side_effect = err
    return pytest.raises(err.__class__)


@pytest.fixture(params=["verification-passes", "verification-fails"])
def verifications_test_case(
    verification_passes, verification_fails, request, mock_eligibility_service
):
    if request.param == "verification-passes":
        err = verification_passes
        mock_eligibility_service.get_enterprise_associations.side_effect = err
        verification_association_list = [
            (
                factories.VerificationFactory.create(),
                OrganizationEmployeeFactory.create(),
            )
        ]
        # Return only the verifications from the verification_association_list
        verifications = [v for v, _ in verification_association_list if v is not None]
        mock_eligibility_service.get_enterprise_associations.return_value = (
            verifications
        )
        return no_error()

    err = verification_fails
    mock_eligibility_service.get_enterprise_associations.side_effect = err
    return pytest.raises(err.__class__)


def test_verify_member(verification_test_case):
    # Given
    expectation = verification_test_case
    params = factories.ServiceVerificationParametersFactory.create(
        unique_corp_id="foo",
        date_of_birth=datetime.date(1970, 1, 1),
    )
    # When/Then
    with expectation:
        web.verify_member(user_id=1, client_params=params)


def test_verify_members(verifications_test_case):
    # Given
    expectation = verifications_test_case
    params = factories.ServiceVerificationParametersFactory.create(
        unique_corp_id="foo",
        date_of_birth=datetime.date(1970, 1, 1),
    )
    # When/Then
    with expectation:
        web.verify_members(user_id=1, client_params=params)


@pytest.mark.parametrize(
    argnames="given_params,expected_type",
    argvalues=[
        (dict(alternate=True), "lookup"),
        ({}, "lookup"),
        (dict(external_identity=True), "sso"),
    ],
    ids=[
        "alternate-becomes-lookup",
        "none-becomes-lookup",
        "sso-stays-sso",
    ],
)
def test_verify_member_no_params(mock_eligibility_service, given_params, expected_type):
    # Given
    mock_eligibility_service.get_enterprise_association.return_value = (
        factories.VerificationFactory.create()
    )
    # When
    web.verify_member(user_id=1, client_params=given_params)
    # Then
    call = mock_eligibility_service.get_enterprise_association.call_args
    called_verification_type = call.kwargs["verification_type"]
    assert called_verification_type == expected_type


@pytest.mark.parametrize(
    argnames="given_params,expected_type",
    argvalues=[
        (dict(alternate=True), "lookup"),
        ({}, "lookup"),
        (dict(external_identity=True), "sso"),
    ],
    ids=[
        "alternate-becomes-lookup",
        "none-becomes-lookup",
        "sso-stays-sso",
    ],
)
def test_verify_members_no_params(
    mock_eligibility_service, given_params, expected_type
):
    # Given
    verification_association_list = [factories.VerificationFactory.create()]
    mock_eligibility_service.get_enterprise_associations.return_value = (
        verification_association_list
    )
    # When
    web.verify_members(user_id=1, client_params=given_params)
    # Then
    call = mock_eligibility_service.get_enterprise_associations.call_args
    called_verification_type = call.kwargs["verification_type"]
    assert called_verification_type == expected_type


def test_verify_members_with_org_id_in_params_should_apply_filter(
    mock_eligibility_service,
):
    # Given
    org_ids = [1, 2]
    verification_association_list = [
        factories.VerificationFactory.create(organization_id=org.id)
        for org in [OrganizationFactory.create(id=org_id) for org_id in org_ids]
    ]

    mock_eligibility_service.get_enterprise_associations.return_value = (
        verification_association_list
    )
    mock_organization_id = 2
    mock_params = MagicMock(spec=ClientVerificationParameters)
    mock_params.get.return_value = mock_organization_id

    # When
    result = web.verify_members(user_id=1, client_params=mock_params)
    call = mock_eligibility_service.get_enterprise_associations.call_args

    # Then
    assert call.kwargs["organization_id"] == mock_organization_id
    assert len(result) == 1
    assert result[0].organization_id == mock_organization_id


def test_verify_members_no_associations_with_org_id_in_params_should_apply_filter_(
    mock_eligibility_service,
):
    # Given
    org_ids = [1, 2]
    verification_association_list = [
        factories.VerificationFactory.create(organization_id=org.id)
        for org in [OrganizationFactory.create(id=org_id) for org_id in org_ids]
    ]

    mock_eligibility_service.get_enterprise_associations.return_value = (
        verification_association_list
    )
    mock_organization_id = 2
    mock_params = MagicMock(spec=ClientVerificationParameters)
    mock_params.get.return_value = mock_organization_id

    # When
    result = web.verify_members(user_id=1, client_params=mock_params)
    call = mock_eligibility_service.get_enterprise_associations.call_args

    # Then
    assert call.kwargs["organization_id"] == mock_organization_id
    assert len(result) == 1
    assert result[0].organization_id == mock_organization_id


_SETTINGS = factories.EnterpriseEligibilitySettingsFactory.create()
VERIFICATION_ERROR_TEST_MATRIX = {
    "failed-verification": (
        service.EnterpriseVerificationFailedError(
            "foo",
            "standard",
        ),
        exceptions.NotFound,
        [
            {
                "status": exceptions.NotFound.code,
                "title": mock.ANY,
                "detail": "Verification Type: standard",
                "code": "EMPLOYEE_NOT_FOUND",
                "message": mock.ANY,
                "data": {"verification_type": "standard"},
            }
        ],
    ),
    "missing-parameters": (
        service.EnterpriseVerificationQueryError(
            "bar",
            verification_type="standard",
            required_params=("date_of_birth", "company_email"),
        ),
        exceptions.BadRequest,
        [
            {
                "status": exceptions.BadRequest.code,
                "title": mock.ANY,
                "detail": "Verification Type: standard",
                "code": "BAD_REQUEST",
                "message": mock.ANY,
                "data": {
                    "verification_type": "standard",
                    "required_params": ["date_of_birth", "company_email"],
                },
            }
        ],
    ),
    "wrong-verification-type": (
        service.EnterpriseVerificationConfigurationError(
            "bar",
            verification_type="standard",
            settings=_SETTINGS,
        ),
        exceptions.Conflict,
        [
            {
                "status": exceptions.Conflict.code,
                "title": mock.ANY,
                "detail": "Verification Type: standard",
                "code": "STANDARD_ELIGIBILITY_ENABLED",
                "message": mock.ANY,
                "data": {
                    "verification_type": "standard",
                },
            }
        ],
    ),
    "employee-claimed": (
        service.EnterpriseVerificationConflictError(
            "bar",
            verification_type="standard",
            given_user_id=1,
            claiming_user_id=3,
            employee_id=5,
        ),
        exceptions.Conflict,
        [
            {
                "status": exceptions.Conflict.code,
                "title": mock.ANY,
                "detail": "Verification Type: standard",
                "code": "EMPLOYEE_CLAIMED",
                "message": mock.ANY,
                "data": {
                    "verification_type": "standard",
                    "given_user_id": 1,
                    "claiming_user_id": 3,
                    "employee_id": 5,
                },
            }
        ],
    ),
}


@pytest.mark.parametrize(
    argnames="given_error,expected_error,expected_detail",
    argvalues=VERIFICATION_ERROR_TEST_MATRIX.values(),
    ids=VERIFICATION_ERROR_TEST_MATRIX.keys(),
)
def test_handle_verification_errors(given_error, expected_error, expected_detail):
    # Given/When
    with pytest.raises(expected_error) as err_info:
        with web.handle_verification_errors():
            raise given_error
    # Then
    assert err_info.value.data["errors"] == expected_detail


@contextlib.contextmanager
def no_error():
    yield
