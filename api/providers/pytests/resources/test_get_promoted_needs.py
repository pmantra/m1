import datetime
from unittest import mock

import pytest

from appointments.schemas.provider import serialize_datetime
from models.tracks import TrackName
from providers.service.promoted_needs.needs_configurations.config import (
    configuration as Configuration,
)

now = datetime.datetime.utcnow()


@pytest.fixture
def create_test_env(factories):
    target_track = TrackName.TRYING_TO_CONCEIVE

    state = factories.StateFactory.create(abbreviation="NY", name="New York")
    nj_state = factories.StateFactory.create(abbreviation="NJ", name="New Jersey")
    member = factories.MemberFactory.create(member_profile__state=state)
    factories.MemberTrackFactory.create(user=member, name=target_track)

    verticals = [
        factories.VerticalFactory.create(name="Nurse Practitioner"),
        factories.VerticalFactory.create(name="Doula And Childbirth Educator"),
        factories.VerticalFactory.create(name="Midwife"),
    ]

    specialties = [
        factories.SpecialtyFactory.create(
            name=f"specialty-{i:02d}", ordering_weight=10 - i
        )
        for i in range(3)
    ]

    eng = factories.LanguageFactory.create(name="English")
    fr = factories.LanguageFactory.create(name="French")
    deu = factories.LanguageFactory.create(name="German")

    practitionerUsers = [
        factories.DefaultUserFactory.create(),
        factories.DefaultUserFactory.create(),
        factories.DefaultUserFactory.create(),
    ]

    practitionersProfiles = [
        factories.PractitionerProfileFactory.create(
            user_id=practitionerUsers[0].id,
            certified_states=[state, nj_state],
            verticals=[verticals[0]],
            specialties=[specialties[0]],
            next_availability=now + datetime.timedelta(days=1),
            languages=[eng, fr, deu],
        ),
        factories.PractitionerProfileFactory.create(
            user_id=practitionerUsers[1].id,
            certified_states=[state],
            verticals=[verticals[1]],
            specialties=[specialties[1]],
            next_availability=now + datetime.timedelta(days=2),
            languages=[eng],
        ),
        factories.PractitionerProfileFactory.create(
            user_id=practitionerUsers[2].id,
            certified_states=[state],
            verticals=[verticals[2]],
            specialties=[specialties[2]],
            next_availability=now + datetime.timedelta(days=7),
            languages=[eng],
        ),
    ]

    # create a need that is tied to the production configuration files...
    need_slugs = Configuration.get("data").get(target_track)

    needs = [
        factories.NeedFactory.create(
            slug=need_slugs[0], verticals=[verticals[0]], specialties=[specialties[0]]
        ),
        factories.NeedFactory.create(
            slug=need_slugs[1], verticals=[verticals[1]], specialties=[specialties[1]]
        ),
        factories.NeedFactory.create(
            slug=need_slugs[2], verticals=[verticals[2]], specialties=[specialties[2]]
        ),
    ]

    return (
        member,
        verticals,
        practitionerUsers,
        practitionersProfiles,
        needs,
        specialties,
    )


class TestGetPromotedNeeds:
    def test_get(self, client, api_helpers, create_test_env):
        (
            member,
            verticals,
            practitionerUsers,
            practitionersProfiles,
            needs,
            specialties,
        ) = create_test_env

        # call endpoint
        res = client.get(
            "/api/v1/promoted_needs",
            query_string={"availability_scope_in_days": 3},
            headers=api_helpers.json_headers(member),
        )

        # assert it returns 200 and the needs are returned with the right data
        assert res.status_code == 200
        response_data = api_helpers.load_json(res)

        response_needs = response_data["data"]
        # should not return all 3 providers since provider 3 is out of the 3 day window
        assert len(response_needs) == 2

        response_needs_1 = response_needs[0]
        response_needs_2 = response_needs[1]

        # check need 1
        assert response_needs_1["need"] == {
            "id": needs[0].id,
            "name": needs[0].name,
            "description": needs[0].description,
            "slug": needs[0].slug,
            "display_order": 1,
        }

        assert response_needs_1["providers"] == [
            {
                "id": practitionersProfiles[0].user_id,
                "image_url": practitionerUsers[0].avatar_url,
            }
        ]
        assert response_needs_1["next_availability"] == serialize_datetime(
            now + datetime.timedelta(days=1)
        )

        # check need 2
        assert response_needs_2["need"] == {
            "id": needs[1].id,
            "name": needs[1].name,
            "description": needs[1].description,
            "slug": needs[1].slug,
            "display_order": 2,
        }

        assert response_needs_2["providers"] == [
            {
                "id": practitionersProfiles[1].user_id,
                "image_url": practitionerUsers[1].avatar_url,
            }
        ]
        assert response_needs_2["next_availability"] == serialize_datetime(
            now + datetime.timedelta(days=2)
        )

    def test_get_promoted_needs__translated(self, client, api_helpers, create_test_env):
        (
            member,
            verticals,
            practitionerUsers,
            practitionersProfiles,
            needs,
            specialties,
        ) = create_test_env
        expected_translation = "translatedabc"
        with mock.patch(
            "providers.resources.promoted_needs.feature_flags.bool_variation",
            return_value=True,
        ), mock.patch(
            "providers.resources.promoted_needs.TranslateDBFields.get_translated_need",
            return_value=expected_translation,
        ) as translation_mock:
            res = client.get(
                "/api/v1/promoted_needs",
                query_string={"availability_scope_in_days": 3},
                headers=api_helpers.json_headers(member),
            )

        assert res.status_code == 200
        response_data = api_helpers.load_json(res)

        response_needs = response_data["data"]
        assert len(response_needs) == 2
        for actual_need in response_needs:
            actual_need["name"] = expected_translation
            actual_need["description"] = expected_translation

        assert translation_mock.call_count == 4
