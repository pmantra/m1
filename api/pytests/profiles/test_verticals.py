from unittest import mock

import pytest


@pytest.fixture
def practitioner(factories):
    return factories.PractitionerUserFactory.create()


@pytest.fixture()
def verticals(factories, practitioner):
    verticals = [
        factories.VerticalFactory.create(name="High-risk OB (MFM)"),
        factories.VerticalFactory.create(name="care Advocate"),
        factories.VerticalFactory.create(name="Fertility Awareness Educator"),
        factories.VerticalFactory.create(name="Reproductive Endocrinologist"),
    ]
    verticals.extend(practitioner.profile.verticals)
    verticals.sort(key=lambda x: x.name.lower())
    return verticals


def test_verticals_endpoint_is_sorted(client, api_helpers, practitioner, verticals):
    verticals = verticals
    expected_vertical_names = [vert.name for vert in verticals]

    res = client.get(
        "/api/v1/verticals",
        headers=api_helpers.json_headers(practitioner),
    )

    assert res.status_code == 200
    data = api_helpers.load_json(res)
    res_vertical_names = [sp["name"] for sp in data]
    assert len(data) == len(verticals)
    assert all(a == b for a, b in zip(res_vertical_names, expected_vertical_names))


def test_verticals_endpoint_filter_by_id(client, api_helpers, practitioner, verticals):
    expected_verticals = verticals[:2]
    expected_vertical_names = [vert.name for vert in expected_verticals]
    expected_ids = [v.id for v in expected_verticals]

    res = client.get(
        "/api/v1/verticals",
        query_string={"ids": ",".join([str(i) for i in expected_ids])},
        headers=api_helpers.json_headers(practitioner),
    )

    assert res.status_code == 200
    data = api_helpers.load_json(res)
    res_vertical_names = [sp["name"] for sp in data]
    assert len(data) == len(expected_verticals)
    assert all(a == b for a, b in zip(res_vertical_names, expected_vertical_names))


@mock.patch("views.profiles.feature_flags.bool_variation")
@mock.patch("l10n.db_strings.schema.feature_flags.bool_variation")
def test_verticals_translation(
    mock_l10n_flag, mock_l10n_flag2, client, api_helpers, enterprise_user, verticals
):
    mock_l10n_flag.return_value = True
    mock_l10n_flag2.return_value = True
    expected_translation = "translatedabc"
    expected_ids = {v.id for v in verticals}
    expected_vertical_names = [expected_translation for id in expected_ids]

    with mock.patch(
        "l10n.db_strings.schema.TranslateDBFields.get_translated_vertical",
        return_value=expected_translation,
    ):
        res = client.get(
            "/api/v1/verticals",
            query_string={"ids": ",".join([str(i) for i in expected_ids])},
            headers=api_helpers.json_headers(enterprise_user),
        )

    assert res.status_code == 200
    data = api_helpers.load_json(res)
    res_vertical_names = [sp["name"] for sp in data]
    assert len(data) == len(expected_ids)
    assert all(a == b for a, b in zip(res_vertical_names, expected_vertical_names))
