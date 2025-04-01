from unittest import mock


def test_get_providers_languages(
    factories,
    client,
    api_helpers,
    enterprise_user,
    vertical_ca,
    vertical_wellness_coach_can_prescribe,
):
    english = factories.LanguageFactory.create(
        name="English", abbreviation="en", iso_639_3="eng"
    )
    spanish = factories.LanguageFactory.create(
        name="Spanish", abbreviation="es", iso_639_3="spa"
    )
    expected_language_ids = {english.id, spanish.id}
    expected_language_names = {english.name, spanish.name}

    p1 = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_ca],
        practitioner_profile__languages=[english],
    )
    p2 = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_wellness_coach_can_prescribe],
        practitioner_profile__languages=[english, spanish],
    )
    practitioners = [p1, p2]
    practitioner_profiles = [p.practitioner_profile for p in practitioners]

    query_string = {
        "vertical_ids": f"{practitioner_profiles[0].vertical.id}, {practitioner_profiles[1].vertical.id}"
    }
    res = client.get(
        "/api/v1/providers/languages",
        query_string=query_string,
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200

    data = res.json["data"]
    assert len(data) == 2

    actual_language_ids = {data[0]["id"], data[1]["id"]}
    actual_language_names = {data[0]["display_name"], data[1]["display_name"]}
    assert actual_language_ids == expected_language_ids
    assert actual_language_names == expected_language_names


def test_get_providers_languages__verticals(
    factories,
    client,
    api_helpers,
    enterprise_user,
    vertical_ca,
    vertical_wellness_coach_can_prescribe,
):
    """
    Tests that the correct languages are returned when filtering by vertical
    """
    english = factories.LanguageFactory.create(
        name="English", abbreviation="en", iso_639_3="eng"
    )
    spanish = factories.LanguageFactory.create(
        name="Spanish", abbreviation="es", iso_639_3="spa"
    )
    french = factories.LanguageFactory.create(
        name="French", abbreviation="fr", iso_639_3="fra"
    )
    expected_language_ids = {english.id, spanish.id}
    expected_language_names = set([english.name, spanish.name])

    p1 = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_ca],
        practitioner_profile__languages=[english],
    )
    p2 = factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_wellness_coach_can_prescribe],
        practitioner_profile__languages=[english, spanish],
    )
    # Filtered practitioner
    filtered_vertical = factories.VerticalFactory.create(name="OB-GYN")
    factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[filtered_vertical],
        practitioner_profile__languages=[french],
    )

    practitioners = [p1, p2]
    practitioner_profiles = [p.practitioner_profile for p in practitioners]

    query_string = {
        "vertical_ids": f"{practitioner_profiles[0].vertical.id}, {practitioner_profiles[1].vertical.id}"
    }
    res = client.get(
        "/api/v1/providers/languages",
        query_string=query_string,
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200

    data = res.json["data"]
    assert len(data) == 2

    actual_language_ids = {data[0]["id"], data[1]["id"]}
    actual_language_names = {data[0]["display_name"], data[1]["display_name"]}
    assert actual_language_ids == expected_language_ids
    assert actual_language_names == expected_language_names


def test_get_providers_languages__specialties(
    factories,
    client,
    api_helpers,
    enterprise_user,
    vertical_ca,
    vertical_wellness_coach_can_prescribe,
):
    """
    Tests that the correct languages are returned when filtering by specialty
    """
    english = factories.LanguageFactory.create(
        name="English", abbreviation="en", iso_639_3="eng"
    )
    spanish = factories.LanguageFactory.create(
        name="Spanish", abbreviation="es", iso_639_3="spa"
    )
    french = factories.LanguageFactory.create(
        name="French", abbreviation="fr", iso_639_3="fra"
    )
    expected_language_ids = {english.id, spanish.id}
    expected_language_names = set([english.name, spanish.name])

    specialty = factories.SpecialtyFactory.create(name="specialty 1")
    factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_ca],
        practitioner_profile__languages=[english],
        practitioner_profile__specialties=[specialty],
    )
    factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_ca],
        practitioner_profile__languages=[english, spanish],
        practitioner_profile__specialties=[specialty],
    )
    # Filtered practitioner
    filtered_specialty = factories.SpecialtyFactory.create(name="filtered specialty")
    factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_ca],
        practitioner_profile__languages=[french],
        practitioner_profile__specialties=[filtered_specialty],
    )

    query_string = {"specialty_ids": f"{specialty.id}"}
    res = client.get(
        "/api/v1/providers/languages",
        query_string=query_string,
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 200

    data = res.json["data"]
    assert len(data) == 2

    actual_language_ids = {data[0]["id"], data[1]["id"]}
    actual_language_names = {data[0]["display_name"], data[1]["display_name"]}
    assert actual_language_ids == expected_language_ids
    assert actual_language_names == expected_language_names


def test_get_providers_languages__no_filter_params(
    factories,
    client,
    api_helpers,
    enterprise_user,
    vertical_ca,
    vertical_wellness_coach_can_prescribe,
):
    english = factories.LanguageFactory.create(
        name="English", abbreviation="en", iso_639_3="eng"
    )
    spanish = factories.LanguageFactory.create(
        name="Spanish", abbreviation="es", iso_639_3="spa"
    )

    factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_ca],
        practitioner_profile__languages=[english],
    )
    factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_wellness_coach_can_prescribe],
        practitioner_profile__languages=[english, spanish],
    )

    # No filter parameters sent
    query_string = {}
    res = client.get(
        "/api/v1/providers/languages",
        query_string=query_string,
        headers=api_helpers.json_headers(enterprise_user),
    )

    assert res.status_code == 400


def test_get_providers_languages_invalid_param(
    factories,
    client,
    api_helpers,
    enterprise_user,
    vertical_ca,
    vertical_wellness_coach_can_prescribe,
):
    query_string = {"can_prescribe": False}
    res = client.get(
        "/api/v1/providers/languages",
        query_string=query_string,
        headers=api_helpers.json_headers(enterprise_user),
    )
    assert res.status_code == 400


@mock.patch("models.tracks.client_track.should_enable_doula_only_track")
def test_get_providers_languages__no_fiter_params_for_doula_member(
    mock_should_enable_doula_only_track,
    factories,
    client,
    api_helpers,
    create_doula_only_member,
    vertical_ca,
    vertical_wellness_coach_can_prescribe,
):

    # Given

    english = factories.LanguageFactory.create(
        name="English", abbreviation="en", iso_639_3="eng"
    )
    spanish = factories.LanguageFactory.create(
        name="Spanish", abbreviation="es", iso_639_3="spa"
    )

    expected_language_ids = {english.id}
    expected_language_names = {english.name}

    vertical_1 = factories.VerticalFactory.create(
        name="Doula and Childbirth Educator",
    )
    factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_1],
        practitioner_profile__languages=[english],
    )

    vertical_2 = factories.VerticalFactory.create(name="Diabetes Coach")
    factories.PractitionerUserFactory.create(
        practitioner_profile__verticals=[vertical_2],
        practitioner_profile__languages=[spanish],
    )

    # When

    # No filter parameters sent by doula only member
    query_string = {}
    res = client.get(
        "/api/v1/providers/languages",
        query_string=query_string,
        headers=api_helpers.json_headers(create_doula_only_member),
    )

    # Then

    assert res.status_code == 200

    # assert that only the language specific to the doula provider is returned
    data = res.json["data"]
    assert len(data) == 1
    actual_language_ids = {data[0]["id"]}
    actual_language_names = {data[0]["display_name"]}
    assert actual_language_ids == expected_language_ids
    assert actual_language_names == expected_language_names
