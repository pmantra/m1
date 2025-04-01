from __future__ import annotations

import pytest

Q1_OPTIONS = [
    "report_problem_q1_o1",
    "report_problem_q1_o2",
    "report_problem_q1_o3",
    "report_problem_q1_o4",
]


@pytest.mark.parametrize(
    argnames="locale",
    argvalues=[None, "en", "es", "fr", "fr_CA"],
)
def test_get_report_problem(
    locale,
    client,
    api_helpers,
    default_user,
    release_mono_api_localization_on,
):
    # Given a desire to get a list of video problem options
    # when: we request the options
    headers = api_helpers.json_headers(default_user)
    if locale:
        headers = api_helpers.with_locale_header(
            api_helpers.json_headers(user=default_user), locale=locale
        )
    res = client.get(
        "/api/v1/video/report_problem",
        headers=headers,
    )
    # then: we should get the problem options

    assert res.status_code == 200
    res_data = api_helpers.load_json(res)
    assert res_data["title_text"] != "report_problem_title"
    assert res_data["header_text"] != "report_problem_header"
    assert res_data["questions"][0]["question"] != "report_problem_q1_text"
    for option in res_data["questions"][0]["options"]:
        assert option["text"] not in Q1_OPTIONS
