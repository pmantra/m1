from unittest.mock import patch

import pytest

from models.questionnaires import COACHING_NOTES_COACHING_PROVIDERS_OID


@pytest.fixture
def generic_questionnaire(valid_questionnaire_with_oid):
    return valid_questionnaire_with_oid(oid=COACHING_NOTES_COACHING_PROVIDERS_OID)


@pytest.fixture
def verticals_questionnaire(basic_appointment, valid_questionnaire_with_verticals):
    return valid_questionnaire_with_verticals(
        verticals=basic_appointment.practitioner.practitioner_profile.verticals
    )


@pytest.fixture
def generic_then_verticals(request):
    # First generic questionnaire
    request.getfixturevalue("generic_questionnaire")
    # Then verticals questionnaire
    request.getfixturevalue("verticals_questionnaire")


@pytest.fixture
def verticals_then_generic(request):
    # First verticals questionnaire
    request.getfixturevalue("verticals_questionnaire")
    # Then generic questionnaire
    request.getfixturevalue("generic_questionnaire")


@pytest.fixture
def prepare_questionnaires(request):
    def prepare_questionnaires_func(
        questionnaires_fixture, expected_questionnaire_fixture
    ):
        """Prepares the questionnaires by getting the fixture and then returns
        the questionnaire object of the specified expected questionnaire
        """
        # Prepare the questionnaires
        request.getfixturevalue(questionnaires_fixture)
        # Return the expected questionnaire
        return request.getfixturevalue(expected_questionnaire_fixture)

    return prepare_questionnaires_func


@pytest.mark.parametrize(
    "questionnaires_fixture, expected_questionnaire_fixture",
    [
        ("generic_questionnaire", "generic_questionnaire"),
        ("verticals_questionnaire", "verticals_questionnaire"),
        ("verticals_then_generic", "verticals_questionnaire"),
        ("generic_then_verticals", "verticals_questionnaire"),
    ],
)
def test_get_structured_note(
    basic_appointment,
    prepare_questionnaires,
    questionnaires_fixture,
    expected_questionnaire_fixture,
    get_appointment_from_endpoint_using_appointment,
):
    """Tests that the expected questionnaire is returned, based on the type of
    questionnaires available, but regardless of the order in which they were
    created/added
    """
    # Prepare the questionnaires and get the reference to the expected
    # questionnaire
    expected_questionnaire = prepare_questionnaires(
        questionnaires_fixture=questionnaires_fixture,
        expected_questionnaire_fixture=expected_questionnaire_fixture,
    )

    # Get the appointment
    data = get_appointment_from_endpoint_using_appointment(
        appointment=basic_appointment
    ).json

    # Assert that the questionnaire is the one expected
    assert data["structured_internal_note"]["questionnaire"]["id"] == str(
        expected_questionnaire.id
    )


def test_no_structured_note_found(
    basic_appointment, get_appointment_from_endpoint_using_appointment
):
    """Tests that if no questionnaire is found, it will be logged as an
    exception and None is returned as the questionnaire
    """
    with patch("models.questionnaires.log_exception_message") as log_method:
        data = get_appointment_from_endpoint_using_appointment(
            appointment=basic_appointment
        ).json

        # Assert expectations: Questionnaire is None and exception is logged
        assert data["structured_internal_note"]["questionnaire"] is None
        log_method.assert_called()
