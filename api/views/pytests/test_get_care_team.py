from unittest import mock

import pytest


@pytest.mark.parametrize(
    argnames="l10n_enabled",
    argvalues=[True, False],
)
@mock.patch("views.profiles.feature_flags.bool_variation")
@mock.patch("l10n.db_strings.schema.feature_flags.bool_variation")
def test_get_care_team(
    mock_l10n_flag, mock_l10n_flag2, l10n_enabled, factories, client, api_helpers, db
):
    mock_l10n_flag.return_value = l10n_enabled
    mock_l10n_flag2.return_value = l10n_enabled
    v = factories.VerticalFactory.create(
        name="Care Advocate",
        display_name="Care Advocate",
    )
    prac1 = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[v]
    )
    enterprise_user = factories.EnterpriseUserFactory.create(care_team=[prac1])

    expected_translation = "translatedabc"
    with mock.patch(
        "l10n.db_strings.schema.TranslateDBFields.get_translated_vertical",
        return_value=expected_translation,
    ):
        res = client.get(
            f"/api/v1/users/{enterprise_user.id}/care_team",
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    data = res.json["data"]
    assert len(data) == 1
    actual_prac = data[0]
    assert len(actual_prac["profiles"]) == 1
    assert actual_prac["id"] == prac1.id
    actual_profile = actual_prac["profiles"]["practitioner"]

    assert len(actual_profile["verticals"]) == 1
    if l10n_enabled:
        assert actual_profile["verticals"][0] == expected_translation
        assert len(actual_profile["vertical_objects"]) == 1
        assert actual_profile["vertical_objects"][0]["name"] == expected_translation
        assert (
            actual_profile["vertical_objects"][0]["pluralized_display_name"]
            == expected_translation
        )
        assert (
            actual_profile["vertical_objects"][0]["description"] == expected_translation
        )
        assert (
            actual_profile["vertical_objects"][0]["long_description"]
            == expected_translation
        )
    else:
        assert actual_profile["verticals"][0] == v.name
        assert len(actual_profile["vertical_objects"]) == 1
        assert actual_profile["vertical_objects"][0]["name"] == v.name
        assert (
            actual_profile["vertical_objects"][0]["pluralized_display_name"]
            == v.pluralized_display_name
        )
        assert actual_profile["vertical_objects"][0]["description"] == v.description
        assert (
            actual_profile["vertical_objects"][0]["long_description"]
            == v.long_description
        )
