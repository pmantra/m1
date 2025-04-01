from unittest import mock


def test_vertical_translate(factories):
    v = factories.MemberAppointmentServiceResponseVerticalFactory.create(
        name="OB-GYN",
        slug="ob-gyn",
    )

    expected_translation = "translatedtext"
    with mock.patch(
        "appointments.schemas.v2.member_appointment.TranslateDBFields.get_translated_vertical",
        return_value=expected_translation,
    ) as translation_mock:
        v.translate()

        assert translation_mock.call_count == 2

    assert v.name == expected_translation
    assert v.description == expected_translation
