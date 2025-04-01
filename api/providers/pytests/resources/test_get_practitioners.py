from unittest import mock

import pytest


def test_get_practitioners(
    client,
    api_helpers,
    db,
    factories,
):

    member = factories.MemberFactory.create()
    v = factories.VerticalFactory.create(
        name="Care Advocate",
        display_name="Care Advocate",
    )
    factories.PractitionerUserFactory.create(practitioner_profile__verticals=[v])
    res = client.get(
        "/api/v1/practitioners",
        query_string={},
        headers=api_helpers.json_headers(member),
    )

    data = res.json["data"]
    assert len(data) == 1

    actual_profile = data[0]["profiles"]["practitioner"]
    assert actual_profile["verticals"][0] == v.name
    assert len(actual_profile["vertical_objects"]) == 1
    assert actual_profile["vertical_objects"][0]["name"] == v.name
    assert (
        actual_profile["vertical_objects"][0]["pluralized_display_name"]
        == v.pluralized_display_name
    )
    assert actual_profile["vertical_objects"][0]["description"] == v.description
    assert (
        actual_profile["vertical_objects"][0]["long_description"] == v.long_description
    )


@pytest.mark.skip(reason="see https://mavenclinic.atlassian.net/browse/DISCO-5064")
@pytest.mark.parametrize("locale", [None, "en", "es", "fr"])
@mock.patch("views.profiles.feature_flags.bool_variation")
@mock.patch("l10n.db_strings.schema.feature_flags.bool_variation")
def test_get_practitioners__localized_text(
    mock_l10n_flag,
    mock_l10n_flag2,
    locale,
    client,
    api_helpers,
    db,
    factories,
    release_mono_api_localization_on,
):
    mock_l10n_flag.return_value = True
    mock_l10n_flag2.return_value = True
    member = factories.MemberFactory.create()
    factories.PractitionerUserFactory.create()

    expected_translated_vertical_name = "abc"

    with mock.patch(
        "l10n.db_strings.schema.TranslateDBFields.get_translated_vertical",
        return_value=expected_translated_vertical_name,
    ):
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(member), locale
        )
        res = client.get(
            "/api/v1/practitioners",
            query_string={},
            headers=headers,
        )

    data = res.json["data"]
    assert len(data) == 1

    profile = data[0]["profiles"]["practitioner"]
    assert len(profile["vertical_objects"]) == 1
    assert profile["vertical_objects"][0]["name"] == expected_translated_vertical_name
    assert len(profile["verticals"]) == 1
    assert profile["verticals"][0] == expected_translated_vertical_name
