import pytest

from authz.models.roles import ROLES
from models.questionnaires import (
    ASYNC_ENCOUNTER_QUESTIONNAIRE_OID,
    COACHING_NOTES_COACHING_PROVIDERS_OID,
    Questionnaire,
)


@pytest.fixture(autouse=True)
def structured_note(factories):
    return factories.QuestionnaireFactory.create(
        oid=COACHING_NOTES_COACHING_PROVIDERS_OID
    )


def test_fall_back_to_default_note(factories, structured_note):
    practitioner = factories.PractitionerUserFactory.create()
    assert structured_note == Questionnaire.get_structured_internal_note_for_pract(
        practitioner
    )


def test_get_one_note(factories):
    practitioner = factories.PractitionerUserFactory.create()
    vertical = practitioner.practitioner_profile.verticals[0]
    expected_note = factories.QuestionnaireFactory.create(verticals=[vertical])
    assert expected_note == Questionnaire.get_structured_internal_note_for_pract(
        practitioner
    )


def test_excluding_async_encounter_note(factories):
    practitioner = factories.PractitionerUserFactory.create()
    vertical = practitioner.practitioner_profile.verticals[0]
    expected_note = factories.QuestionnaireFactory.create(verticals=[vertical])
    factories.QuestionnaireFactory.create(
        verticals=[vertical], oid=ASYNC_ENCOUNTER_QUESTIONNAIRE_OID
    )
    assert expected_note == Questionnaire.get_structured_internal_note_for_pract(
        practitioner
    )


def test_excluding_prefixed_async_encounter_note(factories):
    practitioner = factories.PractitionerUserFactory.create()
    vertical = practitioner.practitioner_profile.verticals[0]
    expected_note = factories.QuestionnaireFactory.create(verticals=[vertical])
    factories.QuestionnaireFactory.create(
        verticals=[vertical], oid=ASYNC_ENCOUNTER_QUESTIONNAIRE_OID + "_care_advocate"
    )
    assert expected_note == Questionnaire.get_structured_internal_note_for_pract(
        practitioner
    )


def test_get_newest_note(factories):
    practitioner = factories.PractitionerUserFactory.create()
    vertical = practitioner.practitioner_profile.verticals[0]
    older_note = factories.QuestionnaireFactory.create(verticals=[vertical])
    expected_note = factories.QuestionnaireFactory.create(verticals=[vertical])
    assert older_note.created_at < expected_note.created_at
    assert expected_note == Questionnaire.get_structured_internal_note_for_pract(
        practitioner
    )


def test_omit_member_role_notes(factories):
    practitioner = factories.PractitionerUserFactory.create()
    vertical = practitioner.practitioner_profile.verticals[0]
    older_note = factories.QuestionnaireFactory.create(verticals=[vertical])
    newer_note = factories.QuestionnaireFactory.create(verticals=[vertical])

    assert older_note.created_at < newer_note.created_at

    # normally we expect the newer note
    assert newer_note == Questionnaire.get_structured_internal_note_for_pract(
        practitioner
    )

    # but if the newer note is for a member role, we expect the older note
    newer_note.roles = [factories.RoleFactory.create(name=ROLES.member)]
    assert older_note == Questionnaire.get_structured_internal_note_for_pract(
        practitioner
    )
