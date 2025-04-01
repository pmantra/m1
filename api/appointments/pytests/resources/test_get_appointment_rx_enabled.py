from http import HTTPStatus

from appointments.models.constants import PRIVACY_CHOICES, RX_REASONS


def test_rx_enabled_false_by_default(
    basic_appointment, get_appointment_from_endpoint_using_appointment
):
    """Tests that the basic appointment has rx disabled by default"""
    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(basic_appointment)

    # Assert a successful GET and not rx_enabled with the reason
    # being the pharmacy information is missing
    _assert_rx_disabled(
        response=res,
        rx_reason=RX_REASONS.PHARMACY_INFO_NOT_ADDED,
    )


def test_rx_enabled_true(
    basic_appointment,
    enable_appointment_rx,
    get_appointment_from_endpoint_using_appointment,
):
    """Tests that with the proper settings, rx is enabled"""
    # Enable rx on the appointment
    enable_appointment_rx(basic_appointment)

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(basic_appointment)

    # Assert a successful GET and rx_enabled
    _assert_rx_enabled(response=res)


def test_rx_enabled_false_when_no_address_set(
    basic_appointment,
    enable_appointment_rx,
    get_appointment_from_endpoint_using_appointment,
):
    # Enable rx on the appointment
    enable_appointment_rx(basic_appointment)
    # Clear the member's address information
    basic_appointment.member.addresses = []

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(basic_appointment)

    # Assert a successful GET and not rx_enabled with the reason
    # being the pharmacy information is missing
    _assert_rx_disabled(
        response=res,
        rx_reason=RX_REASONS.PHARMACY_INFO_NOT_ADDED,
    )


def test_rx_enabled_false_anonymous_appointment(
    basic_appointment,
    enable_appointment_rx,
    get_appointment_from_endpoint_using_appointment,
):
    """Tests that anonymous appointments will have rx disabled"""
    # Enable rx on the appointment
    enable_appointment_rx(basic_appointment)
    # Set privacy to make the appointment anonymous
    basic_appointment.privacy = PRIVACY_CHOICES.anonymous

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(basic_appointment)

    # Assert a successful GET and not rx_enabled with no reason provided
    _assert_rx_disabled(response=res)


def test_rx_enabled_false_practitioner_can_prescribe_false(
    basic_appointment,
    enable_appointment_rx,
    get_appointment_from_endpoint_using_appointment,
):
    """Tests that if the practitioner cannot prescribe, rx is disabled"""
    # Enable rx on the appointment
    enable_appointment_rx(basic_appointment)
    # Setting either the dosespot or the verticals to an empty container will
    # set the practitioner's enable_prescribe to False
    prac_profile = basic_appointment.practitioner.profile
    prac_profile.dosespot = {}
    prac_profile.verticals = []

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(basic_appointment)

    # Assert a successful GET and not rx_enabled with no reason provided
    _assert_rx_disabled(response=res)


def test_rx_enabled_false_practitioner_not_certified_for_member_state(
    basic_appointment,
    enable_appointment_rx,
    get_appointment_from_endpoint_using_appointment,
    factories,
):
    # Enable rx on the appointment
    enable_appointment_rx(basic_appointment)
    # Set the member's state to something other than the practitioner's
    # certified state, which is by default New York/NY
    basic_appointment.member.profile.state = factories.StateFactory.create(
        name="Connecticut", abbreviation="CT"
    )

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(basic_appointment)

    # Assert a successful GET and not rx_enabled with no reason provided
    _assert_rx_disabled(response=res)


def test_rx_enabled_false_practitioner_no_member_state(
    basic_appointment,
    enable_appointment_rx,
    get_appointment_from_endpoint_using_appointment,
):
    # Enable rx on the appointment
    enable_appointment_rx(basic_appointment)
    # Clear the member's state
    basic_appointment.member.profile.state = None

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(basic_appointment)

    # Assert a successful GET and not rx_enabled with no reason provided
    _assert_rx_disabled(response=res)


def test_rx_enabled_false_ZZ_member_state(
    basic_appointment,
    enable_appointment_rx,
    get_appointment_from_endpoint_using_appointment,
    factories,
):
    # Enable rx on the appointment
    enable_appointment_rx(basic_appointment)
    # Set state to Other/ZZ
    basic_appointment.member.profile.state = factories.StateFactory.create(
        name="Other", abbreviation="ZZ"
    )

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(basic_appointment)

    # Assert a successful GET and not rx_enabled with no reason provided
    _assert_rx_disabled(response=res)


def test_rx_enabled_false_member_country_is_not_us(
    basic_appointment,
    enable_appointment_rx,
    get_appointment_from_endpoint_using_appointment,
):
    # Enable rx on the appointment
    enable_appointment_rx(basic_appointment)
    # Set the country to something that's not the U.S.
    basic_appointment.member.profile.country_code = "CA"

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(basic_appointment)

    # Assert a successful GET and not rx_enabled with no reason provided
    _assert_rx_disabled(response=res)


def test_rx_enabled_true_no_country_set(
    basic_appointment,
    enable_appointment_rx,
    get_appointment_from_endpoint_using_appointment,
):
    # Enable rx on the appointment
    enable_appointment_rx(basic_appointment)
    # Clear the member's country
    basic_appointment.member.profile.country_code = None

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(basic_appointment)

    # Assert a successful GET and rx_enabled
    _assert_rx_enabled(response=res)


def test_rx_enabled_enterprise_true(
    enterprise_appointment,
    enable_appointment_rx,
    get_appointment_from_endpoint_using_appointment,
):
    # Enable rx on the appointment
    enable_appointment_rx(enterprise_appointment)

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(enterprise_appointment)

    # Assert a successful GET and rx_enabled
    _assert_rx_enabled(response=res)


def test_rx_enabled_false_member_organization_rx_enabled_is_false(
    enterprise_appointment,
    enable_appointment_rx,
    get_appointment_from_endpoint_using_appointment,
):
    # Enable rx on the appointment
    enable_appointment_rx(enterprise_appointment)
    # Disable rx on the organization
    enterprise_appointment.member.organization.rx_enabled = False

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(enterprise_appointment)

    # Assert a successful GET and not rx_enabled with reason being
    # the organization does not allow it
    _assert_rx_disabled(
        response=res,
        rx_reason=RX_REASONS.NOT_ALLOWED_BY_ORG,
    )


def test_rx_enabled_false_when_org_is_education_only(
    enterprise_appointment,
    enable_appointment_rx,
    get_appointment_from_endpoint_using_appointment,
):
    # Enable rx on the appointment
    enable_appointment_rx(enterprise_appointment)
    # education_only cannot be set to True unless rx_enabled is set to False
    organization = enterprise_appointment.member.organization
    organization.rx_enabled = False
    organization.education_only = True

    # Get the appointment from the endpoint
    res = get_appointment_from_endpoint_using_appointment(enterprise_appointment)

    # Assert a successful GET and not rx_enabled with reason being
    # the organization does not allow it
    _assert_rx_disabled(
        response=res,
        rx_reason=RX_REASONS.NOT_ALLOWED_BY_ORG,
    )


def _assert_rx_enabled(response):
    assert response.status_code == HTTPStatus.OK
    assert response.json["rx_enabled"]
    assert response.json["rx_reason"] == RX_REASONS.IS_ALLOWED


def _assert_rx_disabled(response, rx_reason=""):
    assert response.status_code == HTTPStatus.OK
    assert not response.json["rx_enabled"]
    assert response.json["rx_reason"] == rx_reason
