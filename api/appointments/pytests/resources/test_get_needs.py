from unittest import mock

from pytests.db_util import enable_db_performance_warnings


def test_get_needs_by_id(
    factories,
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    track_names = ["adoption", "parenting_and_pediatrics"]
    member, tracks, _ = enterprise_user_with_tracks_and_categories(track_names)

    expected_need = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need.id,
    )
    need_2 = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=need_2.id,
    )

    query_string = {"id": expected_need.id}
    res = client.get(
        "/api/v1/needs",
        query_string=query_string,
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    res_data = res.json["data"]
    assert len(res_data) == 1
    actual_need = res_data[0]
    assert actual_need.get("id") == expected_need.id
    assert actual_need.get("name") == expected_need.name
    assert actual_need.get("description") == expected_need.description


def test_get_needs_by_name(
    factories,
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    track_names = ["adoption", "parenting_and_pediatrics"]
    member, tracks, _ = enterprise_user_with_tracks_and_categories(track_names)

    expected_need = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need.id,
    )
    need_2 = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=need_2.id,
    )

    query_string = {"name": expected_need.name}
    res = client.get(
        "/api/v1/needs",
        query_string=query_string,
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    res_data = res.json["data"]
    assert len(res_data) == 1
    actual_need = res_data[0]
    assert actual_need.get("id") == expected_need.id
    assert actual_need.get("name") == expected_need.name
    assert actual_need.get("description") == expected_need.description


def test_get_needs_by_provider__vertical(
    factories,
    client,
    db,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
    vertical_wellness_coach_can_prescribe,
):
    """
    Tests get needs using the provider_id parameter, when the provider has
    a vertical but no specialty
    """
    track_names = ["adoption", "parenting_and_pediatrics"]
    member, tracks, _ = enterprise_user_with_tracks_and_categories(track_names)

    vertical_1 = factories.VerticalFactory(name="womens_health_nurse_practitioner")
    vertical_2 = factories.VerticalFactory(name="lactation_consultant")
    vertical_3 = factories.VerticalFactory(name="nurse_practitioner")

    specialty = factories.SpecialtyFactory(name="allergies")

    provider = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_1, vertical_2],
        practitioner_profile__specialties=[],
    )

    # This need should match because it has a matching vertical and no specialties
    expected_need = factories.NeedFactory.create(
        verticals=[vertical_1],
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need.id,
    )

    # This need shouldn't match because it has a matching vertical,
    # but it has a specialty
    need_2 = factories.NeedFactory.create(
        verticals=[vertical_2],
        specialties=[specialty],
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=need_2.id,
    )

    # This need shouldn't match because it has neither a matching vertical
    # nor specialty
    need_3 = factories.NeedFactory.create(
        verticals=[vertical_3],
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=need_3.id,
    )

    with enable_db_performance_warnings(
        database=db,
        failure_threshold=14,
    ):
        query_string = {"provider_id": provider.id}
        res = client.get(
            "/api/v1/needs",
            query_string=query_string,
            headers=api_helpers.json_headers(member),
        )

    assert res.status_code == 200
    res_data = res.json["data"]
    assert len(res_data) == 1
    actual_need = res_data[0]
    assert actual_need.get("id") == expected_need.id
    assert actual_need.get("name") == expected_need.name
    assert actual_need.get("description") == expected_need.description


def test_get_needs_by_provider__vertical_and_specialty(
    factories,
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
    vertical_wellness_coach_can_prescribe,
):
    """
    Tests get needs using the provider_id parameter, when the provider has
    a vertical and a specialty
    """
    track_names = ["adoption", "parenting_and_pediatrics"]
    member, tracks, _ = enterprise_user_with_tracks_and_categories(track_names)

    vertical_1 = factories.VerticalFactory(name="womens_health_nurse_practitioner")
    vertical_2 = factories.VerticalFactory(name="lactation_consultant")
    vertical_3 = factories.VerticalFactory(name="nurse_practitioner")

    specialty_1 = factories.SpecialtyFactory(name="allergies")
    specialty_2 = factories.SpecialtyFactory(name="pediatric_nutrition")
    specialty_3 = factories.SpecialtyFactory(name="diabetes")

    provider = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_1, vertical_2],
        practitioner_profile__specialties=[specialty_1, specialty_2],
    )

    # This need should match because it has a matching vertical and no specialties
    expected_need_1 = factories.NeedFactory.create(
        name="name_expected_9",
        verticals=[vertical_3, vertical_1],
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need_1.id,
    )

    # This need should match because it has a matching vertical and
    # matching multiple specialties
    expected_need_2 = factories.NeedFactory.create(
        name="name_expected_8",
        verticals=[vertical_2],
        specialties=[specialty_1, specialty_2],
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need_2.id,
    )

    # This need should match because it has multiple matching verticals and
    # matching specialty
    expected_need_3 = factories.NeedFactory.create(
        name="name_expected_7",
        verticals=[vertical_1, vertical_2],
        specialties=[specialty_2, specialty_3],
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[1].name,
        need_id=expected_need_3.id,
    )

    # This need should match because it has multiple matching verticals and
    # matching specialties
    expected_need_4 = factories.NeedFactory.create(
        name="name_expected_6",
        verticals=[vertical_1, vertical_2],
        specialties=[specialty_1, specialty_2],
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[1].name,
        need_id=expected_need_4.id,
    )

    # This need with a matching vertical shouldn't match
    # because it has an unmatched specialty
    not_expected_need_1 = factories.NeedFactory.create(
        verticals=[vertical_2],
        specialties=[specialty_3],
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=not_expected_need_1.id,
    )

    # This need with no specialty shouldn't match
    # because it has an unmatched vertical
    not_expected_need_2 = factories.NeedFactory.create(
        verticals=[vertical_3],
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=not_expected_need_2.id,
    )

    # This need shouldn't match because it has neither a matching vertical
    # nor specialty
    not_expected_need_3 = factories.NeedFactory.create(
        verticals=[vertical_3],
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=not_expected_need_3.id,
    )

    # # This need shouldn't match because it's track name not matching user's tracks
    not_expected_need_4 = factories.NeedFactory.create(
        verticals=[vertical_1],
        specialties=[specialty_1],
    )
    factories.NeedTrackFactory.create(
        track_name="general_wellness",
        need_id=not_expected_need_4.id,
    )

    query_string = {"provider_id": provider.id}
    res = client.get(
        "/api/v1/needs",
        query_string=query_string,
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    res_data = res.json["data"]
    assert len(res_data) == 4
    actual_needs = res_data

    # result should be in sorted order by Need.name

    assert actual_needs == [
        {
            "id": expected_need_4.id,
            "name": expected_need_4.name,
            "description": expected_need_4.description,
        },
        {
            "id": expected_need_3.id,
            "name": expected_need_3.name,
            "description": expected_need_3.description,
        },
        {
            "id": expected_need_2.id,
            "name": expected_need_2.name,
            "description": expected_need_2.description,
        },
        {
            "id": expected_need_1.id,
            "name": expected_need_1.name,
            "description": expected_need_1.description,
        },
    ]


def test_get_needs_no_query_string(
    factories,
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    """Test that GET /needs returns a list of all needs when no param is passed"""
    track_names = ["adoption", "parenting_and_pediatrics"]
    member, tracks, _ = enterprise_user_with_tracks_and_categories(track_names)

    expected_need_1 = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need_1.id,
    )
    expected_need_2 = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need_2.id,
    )

    query_string = {}
    res = client.get(
        "/api/v1/needs",
        query_string=query_string,
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    res_data = res.json["data"]
    assert len(res_data) == 2

    actual_need_1 = res_data[0]
    actual_need_2 = res_data[1]

    expected_ids = {expected_need_1.id, expected_need_2.id}
    expected_names = {expected_need_1.name, expected_need_2.name}
    expected_desc = {expected_need_1.description, expected_need_2.description}

    assert actual_need_1.get("id") in expected_ids
    assert actual_need_1.get("name") in expected_names
    assert actual_need_1.get("description") in expected_desc

    assert actual_need_2.get("id") in expected_ids
    assert actual_need_2.get("name") in expected_names
    assert actual_need_2.get("description") in expected_desc


def test_get_needs_two_query_strings(
    factories,
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    track_names = ["adoption", "parenting_and_pediatrics"]
    member, tracks, _ = enterprise_user_with_tracks_and_categories(track_names)

    expected_need = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need.id,
    )

    query_string = {"id": expected_need.id, "name": expected_need.name}
    res = client.get(
        "/api/v1/needs",
        query_string=query_string,
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 400

    query_string = {"name": expected_need.name, "provider_id": 5}
    res = client.get(
        "/api/v1/needs",
        query_string=query_string,
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 400


def test_get_needs_by_id_not_found(
    factories,
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    track_names = ["adoption", "parenting_and_pediatrics"]
    member, tracks, _ = enterprise_user_with_tracks_and_categories(track_names)

    expected_need = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need.id,
    )

    bad_id = expected_need.id + 1
    query_string = {"id": bad_id}
    res = client.get(
        "/api/v1/needs",
        query_string=query_string,
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    res_data = res.json["data"]
    assert len(res_data) == 0


def test_get_needs_by_name_not_found(
    factories,
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    track_names = ["adoption", "parenting_and_pediatrics"]
    member, tracks, _ = enterprise_user_with_tracks_and_categories(track_names)

    expected_need = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need.id,
    )

    bad_name = expected_need.name + "bad"
    query_string = {"name": bad_name}
    res = client.get(
        "/api/v1/needs",
        query_string=query_string,
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    res_data = res.json["data"]
    assert len(res_data) == 0


def test_get_needs_no_matching_track(
    factories,
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    track_names = ["adoption", "parenting_and_pediatrics"]
    member, tracks, _ = enterprise_user_with_tracks_and_categories(track_names)
    tracks_2_names = ["postpartum"]
    _, tracks_2, _ = enterprise_user_with_tracks_and_categories(tracks_2_names)

    expected_need = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=tracks_2[0].name,
        need_id=expected_need.id,
    )

    bad_name = expected_need.name + "bad"
    query_string = {"name": bad_name}
    res = client.get(
        "/api/v1/needs",
        query_string=query_string,
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    res_data = res.json["data"]
    assert len(res_data) == 0


def test_get_needs_no_desc(
    factories,
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    """
    Desc is required in admin but not in the DB. The endpoint should return null when one isn't present
    """
    track_names = ["adoption", "parenting_and_pediatrics"]
    member, tracks, _ = enterprise_user_with_tracks_and_categories(track_names)

    expected_need = factories.NeedFactory.create(
        description=None,
    )
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need.id,
    )

    query_string = {"id": expected_need.id}
    res = client.get(
        "/api/v1/needs",
        query_string=query_string,
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    res_data = res.json["data"]
    assert len(res_data) == 1
    actual_need = res_data[0]
    assert "description" in actual_need
    assert actual_need.get("description") is None


def test_get_needs__filter_by_track(
    factories,
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    expected_track = factories.MemberTrackFactory()  # pregnancy is default
    member, _, _ = enterprise_user_with_tracks_and_categories(
        ["adoption", "parenting_and_pediatrics"]
    )

    # This is expected because it will get passed to the endpoint
    # by id, and it has a matching track
    expected_need = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=expected_track.name,
        need_id=expected_need.id,
    )

    need_2 = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=expected_track.name,
        need_id=need_2.id,
    )

    query_string = {"id": expected_need.id, "track_name": expected_track.name}
    res = client.get(
        "/api/v1/needs",
        query_string=query_string,
        headers=api_helpers.json_headers(member),
    )

    assert res.status_code == 200
    res_data = res.json["data"]
    assert len(res_data) == 1
    actual_need = res_data[0]
    assert actual_need.get("id") == expected_need.id
    assert actual_need.get("name") == expected_need.name
    assert actual_need.get("description") == expected_need.description


def test_get_needs_by_id__with_l10n(
    factories,
    client,
    api_helpers,
    enterprise_user_with_tracks_and_categories,
):
    track_names = ["adoption", "parenting_and_pediatrics"]
    member, tracks, _ = enterprise_user_with_tracks_and_categories(track_names)

    expected_need = factories.NeedFactory.create()
    factories.NeedTrackFactory.create(
        track_name=tracks[0].name,
        need_id=expected_need.id,
    )

    expected_translation = "translatedneedabc"
    with mock.patch(
        "appointments.resources.needs.feature_flags.bool_variation",
        return_value=True,
    ), mock.patch(
        "l10n.db_strings.translate.TranslateDBFields.get_translated_need",
        return_value=expected_translation,
    ) as translation_mock:
        query_string = {"id": expected_need.id}
        res = client.get(
            "/api/v1/needs",
            query_string=query_string,
            headers=api_helpers.json_headers(member),
        )

        translation_mock.assert_has_calls(
            calls=[
                mock.call(expected_need.slug, "name", expected_need.name),
                mock.call(expected_need.slug, "description", expected_need.description),
            ]
        )

    assert res.status_code == 200
    res_data = res.json["data"]
    assert len(res_data) == 1
    actual_need = res_data[0]
    assert actual_need.get("id") == expected_need.id
    assert actual_need.get("name") == expected_translation
    assert actual_need.get("description") == expected_translation
