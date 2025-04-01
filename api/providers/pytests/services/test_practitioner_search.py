import datetime
import unittest
from unittest import TestCase, mock
from unittest.mock import PropertyMock

import pytest

from appointments.models.needs_and_categories import NeedVertical
from models.profiles import CareTeamTypes
from payments.models.practitioner_contract import ContractType
from payments.pytests.factories import PractitionerContractFactory
from providers.service.provider import ProviderService
from pytests.factories import (
    DefaultUserFactory,
    MemberFactory,
    MemberPractitionerAssociationFactory,
    MemberProfileFactory,
    PractitionerProfileFactory,
    StateFactory,
    VerticalFactory,
    VerticalInStateMatchStateFactory,
)
from storage.connection import db


@pytest.fixture
def three_languages(factories):
    language_1 = factories.LanguageFactory.create(name="English")
    language_2 = factories.LanguageFactory.create(name="French")
    language_3 = factories.LanguageFactory.create(name="Spanish")
    return [language_1, language_2, language_3]


@pytest.fixture
def eight_practitioners(factories, three_languages):
    state_1 = factories.StateFactory.create(abbreviation="AR", name="Arkansas")
    state_2 = factories.StateFactory.create(abbreviation="CA", name="California")
    state_3 = factories.StateFactory.create(abbreviation="ME", name="Maine")
    state_4 = factories.StateFactory.create(abbreviation="PA", name="Pennsylvania")
    states = [state_1, state_2, state_3, state_4]

    specialty_1 = factories.SpecialtyFactory.create(name="Digestive Health")
    specialty_2 = factories.SpecialtyFactory.create(name="Endometriosis")
    specialty_3 = factories.SpecialtyFactory.create(name="Sleep Training")
    specialty_4 = factories.SpecialtyFactory.create(name="Art Therapy")
    specialties = [specialty_1, specialty_2, specialty_3, specialty_4]

    vertical_1 = factories.VerticalFactory.create(name="Adoption Coach")
    vertical_2 = factories.VerticalFactory.create(name="OB-GYN")
    vertical_3 = factories.VerticalFactory.create(name="Urologist")
    verticals = [vertical_1, vertical_2, vertical_3]

    language_1 = three_languages[0]
    language_2 = three_languages[1]
    language_3 = three_languages[2]

    # Practitioner setup:
    # Prac 1: Vert 1     Spec 1        state AR     language 1
    # Prac 2: Vert 2     Spec 2        state AR     language 2
    # Prac 3: Vert 3     Spec 3, 4     state AR     language 3
    #
    # Prac 4: Vert 1     Spec 2        state CA     No language
    # Prac 5: Vert 2     Spec 1, 4     state CA     language 1
    # Prac 6: Vert 3     Spec 1        state CA     language 1
    #
    # Prac 7: Vert 1                   state ME     language 2
    # Prac 8: Vert 2, 3  Spec 1, 2, 3  state ME     language 2, 3
    practitioner_1 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        certified_states=[state_1],
        verticals=[vertical_1],
        specialties=[specialty_1],
        languages=[language_1],
    )
    practitioner_2 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        certified_states=[state_1],
        verticals=[vertical_2],
        specialties=[specialty_2],
        languages=[language_2],
    )
    practitioner_3 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        certified_states=[state_1],
        verticals=[vertical_3],
        specialties=[specialty_3, specialty_4],
        languages=[language_3],
    )

    practitioner_4 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        certified_states=[state_2],
        verticals=[vertical_1],
        specialties=[specialty_2],
    )
    practitioner_5 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        certified_states=[state_2],
        verticals=[vertical_2],
        specialties=[specialty_1, specialty_4],
        languages=[language_1],
    )
    practitioner_6 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        certified_states=[state_2],
        verticals=[vertical_3],
        specialties=[specialty_1],
        languages=[language_1],
    )

    practitioner_7 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        certified_states=[state_3],
        verticals=[vertical_1],
        languages=[language_2],
    )
    practitioner_8 = factories.PractitionerProfileFactory.create(
        user_id=factories.DefaultUserFactory.create().id,
        certified_states=[state_3],
        verticals=[vertical_2, vertical_3],
        specialties=[specialty_1, specialty_2, specialty_3],
        languages=[language_2, language_3],
    )

    practitioners = [
        practitioner_1,
        practitioner_2,
        practitioner_3,
        practitioner_4,
        practitioner_5,
        practitioner_6,
        practitioner_7,
        practitioner_8,
    ]

    return states, verticals, specialties, practitioners


class SearchInStateMatchingTests(TestCase):
    def setUp(self):
        self.state_1 = StateFactory.create(abbreviation="AR", name="Arkansas")
        self.state_2 = StateFactory.create(abbreviation="CA", name="California")
        self.state_3 = StateFactory.create(abbreviation="ME", name="Maine")
        self.state_4 = StateFactory.create(abbreviation="PA", name="Pennsylvania")

        self.vertical_1 = VerticalFactory.create(name="Adoption Coach")
        self.vertical_2 = VerticalFactory.create(name="OB-GYN")
        self.vertical_3 = VerticalFactory.create(name="Urologist")

        # In state matching configuration:
        # Vertical 1: AR
        # Vertical 2: CA, ME
        # Vertical 3: no states
        self.visms_1 = VerticalInStateMatchStateFactory.create(
            state_id=self.state_1.id,
            vertical_id=self.vertical_1.id,
        )
        self.visms_2 = VerticalInStateMatchStateFactory.create(
            state_id=self.state_2.id,
            vertical_id=self.vertical_2.id,
        )
        self.visms_3 = VerticalInStateMatchStateFactory.create(
            state_id=self.state_3.id,
            vertical_id=self.vertical_2.id,
        )

        # Practitioner setup:
        # Prac 1: Vert 1     state AR
        # Prac 2: Vert 2     state AR
        # Prac 3: Vert 3     state AR
        #
        # Prac 4: Vert 1     state CA
        # Prac 5: Vert 2     state CA
        # Prac 6: Vert 3     state CA
        #
        # Prac 7: Vert 1     state ME
        # Prac 8: Vert 2, 3  state ME
        self.practitioner_1 = PractitionerProfileFactory.create(
            user_id=DefaultUserFactory.create().id,
            certified_states=[self.state_1],
            verticals=[self.vertical_1],
        )
        self.practitioner_2 = PractitionerProfileFactory.create(
            user_id=DefaultUserFactory.create().id,
            certified_states=[self.state_1],
            verticals=[self.vertical_2],
        )
        self.practitioner_3 = PractitionerProfileFactory.create(
            user_id=DefaultUserFactory.create().id,
            certified_states=[self.state_1],
            verticals=[self.vertical_3],
        )

        self.practitioner_4 = PractitionerProfileFactory.create(
            user_id=DefaultUserFactory.create().id,
            certified_states=[self.state_2],
            verticals=[self.vertical_1],
        )
        self.practitioner_5 = PractitionerProfileFactory.create(
            user_id=DefaultUserFactory.create().id,
            certified_states=[self.state_2],
            verticals=[self.vertical_2],
        )
        self.practitioner_6 = PractitionerProfileFactory.create(
            user_id=DefaultUserFactory.create().id,
            certified_states=[self.state_2],
            verticals=[self.vertical_3],
        )

        self.practitioner_7 = PractitionerProfileFactory.create(
            user_id=DefaultUserFactory.create().id,
            certified_states=[self.state_3],
            verticals=[self.vertical_1],
        )
        self.practitioner_8 = PractitionerProfileFactory.create(
            user_id=DefaultUserFactory.create().id,
            certified_states=[self.state_3],
            verticals=[self.vertical_2, self.vertical_3],
        )

        self.all_practitioners = [
            self.practitioner_1,
            self.practitioner_2,
            self.practitioner_3,
            self.practitioner_4,
            self.practitioner_5,
            self.practitioner_6,
            self.practitioner_7,
            self.practitioner_8,
        ]

    def test_base_query__user_from_state_with_in_state_matching__results_filter_out_of_state_practitioner(
        self,
    ):
        user_1 = DefaultUserFactory.create()
        user_2 = DefaultUserFactory.create()
        user_3 = DefaultUserFactory.create()
        MemberProfileFactory.create(
            user_id=user_1.id,
            state=self.state_1,
        )
        MemberProfileFactory.create(
            user_id=user_2.id,
            state=self.state_2,
        )
        MemberProfileFactory.create(
            user_id=user_3.id,
            state=self.state_3,
        )

        # For User 1, we expect them to get all practitioners except for #4 and #7, given that
        # those practitioners operates in a Vertical for which we enforce in-state-matching while
        # also being out-of-state practitioners.
        practitioners_for_user_1, _ = ProviderService().search(current_user=user_1)
        self.assertEqual(
            len(practitioners_for_user_1),
            len(self.all_practitioners) - 2,
        )
        practitioner_ids = {u.id for u in practitioners_for_user_1}
        self.assertNotIn(self.practitioner_4.user_id, practitioner_ids)
        self.assertNotIn(self.practitioner_7.user_id, practitioner_ids)

        # For User 2, we expect them to get all practitioners except for #2, given that
        # practitioner #2 operates in a Vertical for which we enforce in-state-matching while
        # also being an out-of-state practitioner. Note that we DO expect to see
        # practitioner #8 -- even though they operate in Vertical B (for which we enforce
        # in-state-matching for CA), they also operate in Vertical C (for which we don't
        # enforce in-state-matching), and thus they're included.
        practitioners_for_user_2, _ = ProviderService().search(current_user=user_2)
        self.assertEqual(
            len(practitioners_for_user_2),
            len(self.all_practitioners) - 1,
        )
        self.assertNotIn(
            self.practitioner_2.user_id, [u.id for u in practitioners_for_user_2]
        )

        # For User 3, we expect them to get all practitioners except for #2 and #5, given that
        # those practitioners operates in a Vertical for which we enforce in-state-matching while
        # also being out-of-state practitioners.
        practitioners_for_user_3, _ = ProviderService().search(current_user=user_3)
        self.assertEqual(
            len(practitioners_for_user_3),
            len(self.all_practitioners) - 2,
        )
        self.assertNotIn(
            self.practitioner_2.user_id, [u.id for u in practitioners_for_user_3]
        )
        self.assertNotIn(
            self.practitioner_5.user_id, [u.id for u in practitioners_for_user_3]
        )

        # For User 1 again with in_state_match=true search, we expect them to get practitioners 1-3, given that
        # those practitioners certified_states includes the user's state.
        practitioners_for_user_1, _ = ProviderService().search(
            current_user=user_1, in_state_match=True
        )
        self.assertEqual(
            len(practitioners_for_user_1),
            3,
        )
        practitioner_ids = {u.id for u in practitioners_for_user_1}
        self.assertIn(self.practitioner_1.user_id, practitioner_ids)
        self.assertIn(self.practitioner_2.user_id, practitioner_ids)
        self.assertIn(self.practitioner_3.user_id, practitioner_ids)

    def test_base_query__user_from_state_with_no_in_state_matching__results_contain_all_practitioners(
        self,
    ):
        user = DefaultUserFactory.create()
        MemberProfileFactory.create(
            user_id=user.id,
            state_id=self.state_4.id,
        )

        practitioners_for_user, _ = ProviderService().search(current_user=user)
        self.assertEqual(
            len(practitioners_for_user),
            len(self.all_practitioners),
        )

    def test_base_query__dont_show_deleted_verticals(
        self,
    ):
        member = MemberFactory.create(
            member_profile__state=self.state_1,
        )

        # This user should currently match with all practitioners except #4 and #7
        practitioners, _ = ProviderService().search(current_user=member)
        expected_practitioner_ids = {
            self.practitioner_1.user_id,
            self.practitioner_2.user_id,
            self.practitioner_3.user_id,
            self.practitioner_5.user_id,
            self.practitioner_6.user_id,
            self.practitioner_8.user_id,
        }
        actual_practitioner_ids = {practitioner.id for practitioner in practitioners}
        assert actual_practitioner_ids == expected_practitioner_ids

        # delete vertical_2
        self.vertical_2.deleted_at = datetime.datetime.utcnow() - datetime.timedelta(
            minutes=5
        )

        # Only practitioners 2 and 5 are associated with only vertical_2
        practitioners, _ = ProviderService().search(current_user=member)
        expected_practitioner_ids = {
            self.practitioner_1.user_id,
            self.practitioner_3.user_id,
            self.practitioner_6.user_id,
            self.practitioner_8.user_id,
        }
        actual_practitioner_ids = {practitioner.id for practitioner in practitioners}
        assert actual_practitioner_ids == expected_practitioner_ids

    def test_search__no_restrictions__return_all_pracititoners(self):
        user = DefaultUserFactory.create()
        MemberProfileFactory.create(
            user_id=user.id,
            state_id=self.state_4.id,
        )

        with mock.patch(
            "storage.connector.RoutingSQLAlchemy.s_replica1",
            new_callable=PropertyMock,
        ) as mock_session:
            mock_session.return_value = db.session

            _, count = ProviderService().search(current_user=user)

            self.assertEqual(
                count,
                len(self.all_practitioners),
            )

    def test_search__restricted_list_of_practitioners__return_all_pracititoners_in_restricted_list(
        self,
    ):
        user = DefaultUserFactory.create()
        MemberProfileFactory.create(
            user_id=user.id,
            state=self.state_4,
        )

        available_practitioners = [
            self.practitioner_1,
            self.practitioner_3,
            self.practitioner_6,
        ]

        with mock.patch(
            "storage.connector.RoutingSQLAlchemy.s_replica1",
            new_callable=PropertyMock,
        ) as mock_session:
            mock_session.return_value = db.session

            _, count = ProviderService().search(
                current_user=user,
                user_ids=[prac.user_id for prac in available_practitioners],
            )

            self.assertEqual(
                count,
                len(available_practitioners),
            )

    def test_search__restricted_list_of_verticals__return_all_pracititoners_with_restricted_verticals(
        self,
    ):
        user = DefaultUserFactory.create()
        MemberProfileFactory.create(
            user_id=user.id,
            state=self.state_4,
        )

        available_verticals = [
            self.vertical_1,
            self.vertical_2,
        ]

        with mock.patch(
            "storage.connector.RoutingSQLAlchemy.s_replica1",
            new_callable=PropertyMock,
        ) as mock_session:
            mock_session.return_value = db.session

            _, count = ProviderService().search(
                current_user=user,
                verticals=[vert.name for vert in available_verticals],
            )

            self.assertEqual(
                count,
                6,  # This 6 includes the 3 practitioners from Vertical 1 and the 3 practitioners from Vertical 2
            )

    def test_search__in_state_matching_enforced__filter_out_of_state_practitioners(
        self,
    ):
        user = DefaultUserFactory.create()
        MemberProfileFactory.create(
            user_id=user.id,
            state=self.state_1,
        )

        with mock.patch(
            "storage.connector.RoutingSQLAlchemy.s_replica1",
            new_callable=PropertyMock,
        ) as mock_session:
            mock_session.return_value = db.session

            _, count = ProviderService().search(
                current_user=user,
            )

            # We expect all practitioners except #4 and #7, who work in Vertical 1 but outside State 1
            self.assertEqual(
                count,
                len(self.all_practitioners) - 2,
            )

    def test_search__in_state_matching_does_not_return_previously_seen_practitioners_if_user_ids_is_not_provided(
        self,
    ):
        user = DefaultUserFactory.create()
        MemberProfileFactory.create(
            user_id=user.id,
            state=self.state_1,
        )

        MemberPractitionerAssociationFactory.create(
            user_id=user.id,
            practitioner_id=self.practitioner_4.user_id,
            type=CareTeamTypes.APPOINTMENT,
        )

        expected_practitioner_ids = [
            practitioner.user_id
            for practitioner in self.all_practitioners
            if practitioner.user_id
            not in [self.practitioner_4.user_id, self.practitioner_7.user_id]
        ]

        practitioners, count = ProviderService().search(current_user=user)

        retrieved_practitioner_ids = [practitioner.id for practitioner in practitioners]
        self.assertCountEqual(retrieved_practitioner_ids, expected_practitioner_ids)

    def test_search__in_state_matching_allows_previously_seen_practitioners_flag_on(
        self,
    ):
        user = DefaultUserFactory.create()
        MemberProfileFactory.create(
            user_id=user.id,
            state=self.state_1,
        )

        MemberPractitionerAssociationFactory.create(
            user_id=user.id,
            practitioner_id=self.practitioner_4.user_id,
            type=CareTeamTypes.APPOINTMENT,
        )

        practitioners, count = ProviderService().search(
            current_user=user,
            user_ids=[prac.user_id for prac in self.all_practitioners],
        )

        retrieved_practitioner_ids = [practitioner.id for practitioner in practitioners]

        expected_practitioner_ids = [
            practitioner.user_id
            for practitioner in self.all_practitioners
            if practitioner.user_id != self.practitioner_7.user_id
        ]

        self.assertCountEqual(retrieved_practitioner_ids, expected_practitioner_ids)


class TestNeedsFiltering:
    def test_search__restricted_list_of_needs(
        self,
        factories,
        eight_practitioners,
    ):
        member = factories.MemberFactory.create()

        # practitioners 1, 4, 7 (indices 0, 3, 6) have vertical 1
        _, verticals, _, practitioners = eight_practitioners
        expected_practitioners = [practitioners[0], practitioners[3], practitioners[6]]
        expected_practitioner_ids = {p.user_id for p in expected_practitioners}
        vertical_1 = verticals[0]

        need = factories.NeedFactory.create(verticals=[vertical_1])

        available_needs = [need]
        available_needs_names = [need.name for need in available_needs]

        with mock.patch(
            "storage.connector.RoutingSQLAlchemy.s_replica1",
            new_callable=PropertyMock,
        ) as mock_session:
            mock_session.return_value = db.session

            actual_practitioners, count = ProviderService().search(
                current_user=member,
                needs=available_needs_names,
            )
            actual_practitioner_ids = {p.id for p in actual_practitioners}

            assert count == 3
            assert actual_practitioner_ids == expected_practitioner_ids

    def test_search__restricted_list_of_needs__no_match(
        self,
        factories,
        eight_practitioners,
    ):
        member = factories.MemberFactory.create()

        non_matching_vertical = factories.VerticalFactory.create(
            name="Non matching vert"
        )

        _, verticals, _, practitioners = eight_practitioners

        need = factories.NeedFactory.create(verticals=[non_matching_vertical])

        available_needs = [need]
        available_needs_names = [need.name for need in available_needs]

        with mock.patch(
            "storage.connector.RoutingSQLAlchemy.s_replica1",
            new_callable=PropertyMock,
        ) as mock_session:
            mock_session.return_value = db.session

            _, count = ProviderService().search(
                current_user=member,
                needs=available_needs_names,
            )

            assert count == 0

    def test_search__restricted_list_of_need_ids(
        self,
        factories,
        eight_practitioners,
    ):
        member = factories.MemberFactory.create()

        # practitioners 1, 4, 7 (indices 0, 3, 6) have vertical 1
        _, verticals, _, practitioners = eight_practitioners
        expected_practitioners = [practitioners[0], practitioners[3], practitioners[6]]
        expected_practitioner_ids = {p.user_id for p in expected_practitioners}
        vertical_1 = verticals[0]

        need = factories.NeedFactory.create(verticals=[vertical_1])

        available_needs = [need]
        available_needs_ids = [need.id for need in available_needs]

        with mock.patch(
            "storage.connector.RoutingSQLAlchemy.s_replica1",
            new_callable=PropertyMock,
        ) as mock_session:
            mock_session.return_value = db.session

            actual_practitioners, count = ProviderService().search(
                current_user=member,
                need_ids=available_needs_ids,
            )

            actual_practitioner_ids = {p.id for p in actual_practitioners}

            assert count == 3
            assert actual_practitioner_ids == expected_practitioner_ids

    def test_search__restricted_list_of_need_slugs(
        self,
        factories,
        eight_practitioners,
    ):
        member = factories.MemberFactory.create()

        # practitioners 1, 4, 7 (indices 0, 3, 6) have vertical 1
        _, verticals, _, practitioners = eight_practitioners
        expected_practitioners = [practitioners[0], practitioners[3], practitioners[6]]
        expected_practitioner_ids = {p.user_id for p in expected_practitioners}
        vertical_1 = verticals[0]

        need = factories.NeedFactory.create(verticals=[vertical_1])

        available_needs = [need]
        available_needs_slugs = [need.slug for need in available_needs]

        with mock.patch(
            "storage.connector.RoutingSQLAlchemy.s_replica1",
            new_callable=PropertyMock,
        ) as mock_session:
            mock_session.return_value = db.session

            actual_practitioners, count = ProviderService().search(
                current_user=member,
                need_slugs=available_needs_slugs,
            )

            actual_practitioner_ids = {p.id for p in actual_practitioners}

            assert count == 3
            assert actual_practitioner_ids == expected_practitioner_ids

    def test_search__restricted_list_of_need_slugs__no_match(
        self,
        factories,
        eight_practitioners,
    ):
        member = factories.MemberFactory.create()

        non_matching_vertical = factories.VerticalFactory.create(
            name="Non matching vert"
        )

        _, verticals, _, practitioners = eight_practitioners

        need = factories.NeedFactory.create(verticals=[non_matching_vertical])

        available_needs = [need]
        available_needs_slugs = [need.slug for need in available_needs]

        with mock.patch(
            "storage.connector.RoutingSQLAlchemy.s_replica1",
            new_callable=PropertyMock,
        ) as mock_session:
            mock_session.return_value = db.session

            _, count = ProviderService().search(
                current_user=member,
                need_slugs=available_needs_slugs,
            )

            assert count == 0

    def test_search__queries_for_need_by_verticals_and_specialties(
        self,
        factories,
        eight_practitioners,
    ):
        member = factories.MemberFactory.create()
        _, verticals, _, practitioners = eight_practitioners
        (
            practitioner_1,
            practitioner_2,
            practitioner_3,
            practitioner_4,
            practitioner_5,
            _,
            practitioner_7,
            practitioner_8,
        ) = practitioners

        # Need with vertical and no specialties
        # Should match practitioners 1, 4, and 7 due to matching verticals
        vertical_matching_need = factories.NeedFactory.create(
            verticals=practitioner_1.verticals
        )

        # Need with verticals and specialties
        # Should match practitioners 5 and 8 due to a matching verticals AND a matching specialty
        vertical_specialty_matching_need = factories.NeedFactory.create(
            verticals=practitioner_2.verticals, specialties=practitioner_3.specialties
        )
        expected_matching_practitioners = [
            practitioner_1,
            practitioner_4,
            practitioner_5,
            practitioner_7,
            practitioner_8,
        ]

        needs = [
            vertical_matching_need,
            vertical_specialty_matching_need,
        ]

        (
            practitioners_by_name,
            practitioners_by_name_count,
        ) = ProviderService().search(
            current_user=member,
            needs=[need.name for need in needs],
        )

        assert practitioners_by_name_count == len(expected_matching_practitioners)

        for user in practitioners_by_name:
            practitioner_profile = user.practitioner_profile
            assert practitioner_profile in expected_matching_practitioners

    @unittest.skip
    def test_search__restricted_verticals__defaults_to_unrestricted(
        self,
        factories,
        eight_practitioners,
    ):
        """
        Unresricted verticals still work and "default" specialties still apply when unrestricted
        """
        member = factories.MemberFactory.create()
        _, verticals, specialties, practitioners = eight_practitioners
        (
            practitioner_1,
            practitioner_2,
            practitioner_3,
            practitioner_4,
            practitioner_5,
            _,
            practitioner_7,
            practitioner_8,
        ) = practitioners

        # Should match practitioner 1 with default specialty, and
        #     practitioners 2 and 8 with restricted verticals/specialties
        # Practitioner 5 has the default specialty, and therefore should not show up when restricted
        vertical_1 = verticals[0]
        vertical_2 = verticals[1]
        specialty_1 = specialties[0]
        specialty_2 = specialties[1]
        vertical_specialty_matching_need = factories.NeedFactory.create(
            verticals=[vertical_1, vertical_2], specialties=[specialty_1]
        )

        # Restrict vertical 2
        nv = (
            db.session.query(NeedVertical)
            .filter(
                NeedVertical.vertical_id == vertical_2.id,
                NeedVertical.need_id == vertical_specialty_matching_need.id,
            )
            .one()
        )
        factories.NeedRestrictedVerticalFactory.create(
            need_vertical_id=nv.id,
            specialty_id=specialty_2.id,
        )

        expected_practitioner_ids = {
            practitioner_1.user_id,
            practitioner_2.user_id,
            practitioner_8.user_id,
        }

        needs = [vertical_specialty_matching_need]

        (
            practitioners_by_name,
            practitioners_by_name_count,
        ) = ProviderService().search(
            current_user=member,
            needs=[need.name for need in needs],
        )
        actual_practitioner_ids = {p.id for p in practitioners_by_name}
        assert actual_practitioner_ids == expected_practitioner_ids

    def test_search__restricted_verticals__restricted_verticals_dont_also_default(
        self,
        factories,
        eight_practitioners,
    ):
        """
        Test that when a vertical is restricted it doesn't pick up practitioners
        that match the need's default specialty as well
        """
        member = factories.MemberFactory.create()

        state_pa = factories.StateFactory.create(abbreviation="NJ", name="New Jersey")

        specialty_1 = factories.SpecialtyFactory.create(name="allergies")
        specialty_2 = factories.SpecialtyFactory.create(name="pediatric nutrition")

        vertical = factories.VerticalFactory.create(name="Adoption Coach")
        factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id,
            certified_states=[state_pa],
            verticals=[vertical],
            specialties=[specialty_1],
        )
        expected_practitioner = factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id,
            certified_states=[state_pa],
            verticals=[vertical],
            specialties=[specialty_2],
        )

        need = factories.NeedFactory.create(
            verticals=[vertical], specialties=[specialty_1]
        )

        # Restrict vertical/specialty_2
        nv = (
            db.session.query(NeedVertical)
            .filter(
                NeedVertical.vertical_id == vertical.id,
                NeedVertical.need_id == need.id,
            )
            .one()
        )
        factories.NeedRestrictedVerticalFactory.create(
            need_vertical_id=nv.id,
            specialty_id=specialty_2.id,
        )

        expected_practitioner_id = expected_practitioner.user_id
        needs = [need]

        (result, result_count,) = ProviderService().search(
            current_user=member,
            needs=[need.name for need in needs],
        )
        actual_practitioner_ids = {p.id for p in result}
        assert result_count == 1
        assert expected_practitioner_id in actual_practitioner_ids

    def test_search__restricted_verticals__default_works_with_no_specialty(
        self,
        factories,
        eight_practitioners,
    ):
        """
        Test that when a vertical is restricted it doesn't pick up practitioners
        that match the need's default specialty as well
        """
        member = factories.MemberFactory.create()

        state_pa = factories.StateFactory.create(abbreviation="NJ", name="New Jersey")

        specialty_1 = factories.SpecialtyFactory.create(name="allergies")
        specialty_2 = factories.SpecialtyFactory.create(name="pediatric_nutrition")
        vertical_1 = factories.VerticalFactory.create(
            name="womens_health_nurse_practitioner"
        )
        vertical_2 = factories.VerticalFactory.create(name="lactation_consultant ")

        practitioner_1 = factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id,
            certified_states=[state_pa],
            verticals=[vertical_1],
            specialties=[specialty_1],
        )
        practitioner_2 = factories.PractitionerProfileFactory.create(
            user_id=factories.DefaultUserFactory.create().id,
            certified_states=[state_pa],
            verticals=[vertical_2],
            specialties=[specialty_2],
        )

        # Create need with no specialties
        need = factories.NeedFactory.create(
            verticals=[vertical_1, vertical_2], specialties=[]
        )

        # Restrict vertical_1/specialty_2
        nv = (
            db.session.query(NeedVertical)
            .filter(
                NeedVertical.vertical_id == vertical_1.id,
                NeedVertical.need_id == need.id,
            )
            .one()
        )
        factories.NeedRestrictedVerticalFactory.create(
            need_vertical_id=nv.id,
            specialty_id=specialty_1.id,
        )

        expected_practitioner_ids = {practitioner_1.user_id, practitioner_2.user_id}
        needs = [need]

        (result, result_count,) = ProviderService().search(
            current_user=member,
            needs=[need.name for need in needs],
        )
        actual_practitioner_ids = {p.id for p in result}
        assert expected_practitioner_ids == actual_practitioner_ids
        assert result_count == 2


class TestProviderSteerage:
    def test_search__orders_providers_by_contract_and_availability(
        self,
        factories,
        eight_practitioners,
    ):
        member = factories.MemberFactory.create()
        now = datetime.datetime.utcnow()

        _, _, _, practitioners = eight_practitioners
        for index, practitioner in enumerate(practitioners):
            practitioner.next_availability = now + datetime.timedelta(hours=index)

        # Pair practitioners with contracts in order of tier/availability time
        non_contract_practitioner = practitioners[0]
        expected_practitioner_order_and_contract = [
            (practitioners[2], ContractType.FIXED_HOURLY),
            (practitioners[4], ContractType.W2),
            (practitioners[6], ContractType.FIXED_HOURLY_OVERNIGHT),
            (practitioners[3], ContractType.HYBRID_1_0),
            (practitioners[5], ContractType.HYBRID_2_0),
            (practitioners[1], ContractType.BY_APPOINTMENT),
            (practitioners[7], ContractType.NON_STANDARD_BY_APPOINTMENT),
        ]

        # Create contracts
        for practitioner, contract in expected_practitioner_order_and_contract:
            PractitionerContractFactory.create(
                practitioner=practitioner,
                contract_type=contract,
            )

        actual_practitioners, count = ProviderService().search(
            current_user=member,
        )

        assert count == len(practitioners)
        for index, prac_tuple in enumerate(expected_practitioner_order_and_contract):
            practitioner, contract = prac_tuple
            assert actual_practitioners[index].practitioner_profile == practitioner
            assert (
                actual_practitioners[
                    index
                ].practitioner_profile.active_contract.contract_type
                == contract
            )

        # Assert that practitioners with no active contracts are sorted at the end
        assert (
            non_contract_practitioner == actual_practitioners[-1].practitioner_profile
        )

    def test_search__orders_by_active_contract(
        self,
        factories,
        eight_practitioners,
    ):
        member = factories.MemberFactory.create()
        today = datetime.date.today()

        _, _, _, practitioners = eight_practitioners

        w2_practitioner = practitioners[0]
        fixed_hourly_practitioner = practitioners[1]
        expected_tier_1_practitioners = [w2_practitioner, fixed_hourly_practitioner]

        for practitioner in practitioners[2:]:
            PractitionerContractFactory.create(
                practitioner=practitioner,
                contract_type=ContractType.HYBRID_2_0,
            )

        two_weeks_ago = today - datetime.timedelta(days=14)
        one_week_ago = today - datetime.timedelta(days=7)
        one_week_from_today = today + datetime.timedelta(days=7)

        # Configure W2 provider contracts
        # Current W2 contract
        PractitionerContractFactory.create(
            practitioner=w2_practitioner,
            contract_type=ContractType.W2,
            start_date=two_weeks_ago,
            end_date=one_week_from_today,
        )

        # Expired appointment contract
        PractitionerContractFactory.create(
            practitioner=w2_practitioner,
            contract_type=ContractType.BY_APPOINTMENT,
            start_date=two_weeks_ago,
            end_date=one_week_ago,
        )

        # Configure Fixed Hourly provider contracts
        # Future appointment contract
        PractitionerContractFactory.create(
            practitioner=fixed_hourly_practitioner,
            contract_type=ContractType.BY_APPOINTMENT,
            start_date=one_week_from_today,
        )

        # Current Fixed Hourly contract
        PractitionerContractFactory.create(
            practitioner=fixed_hourly_practitioner,
            contract_type=ContractType.FIXED_HOURLY,
            start_date=two_weeks_ago,
            end_date=one_week_from_today,
        )

        actual_practitioners, count = ProviderService().search(
            current_user=member,
        )

        assert count == len(practitioners)

        tier_1_practitioners = actual_practitioners[0:2]
        for tier_1_practitioner in tier_1_practitioners:
            assert (
                tier_1_practitioner.practitioner_profile
                in expected_tier_1_practitioners
            )

    def test_search__only_does_steerage_by_default(
        self,
        factories,
        eight_practitioners,
    ):
        member = factories.MemberFactory.create()
        now = datetime.datetime.utcnow()
        three_weeks_from_now = now + datetime.timedelta(days=21)

        _, _, _, practitioners = eight_practitioners
        for index, practitioner in enumerate(practitioners):
            practitioner.next_availability = three_weeks_from_now - datetime.timedelta(
                days=index
            )

        PractitionerContractFactory.create(
            practitioner=practitioners[0],
            contract_type=ContractType.W2,
        )

        PractitionerContractFactory.create(
            practitioner=practitioners[1],
            contract_type=ContractType.W2,
        )

        actual_practitioners, count = ProviderService().search(
            current_user=member, order_by="next_availability"
        )

        assert count == len(practitioners)
        expected_practitioner_list = list(practitioners)
        expected_practitioner_list.reverse()
        for index, practitioner in enumerate(expected_practitioner_list):
            assert actual_practitioners[index].practitioner_profile == practitioner

    def test_search__bypasses_utilization_filter_when_feature_flag_is_off(
        self,
        factories,
        eight_practitioners,
    ):
        member = factories.MemberFactory.create()
        _, _, _, practitioners = eight_practitioners

        tomorrow = datetime.datetime.utcnow() + datetime.timedelta(days=1)
        for index, practitioner in enumerate(practitioners):
            practitioner.next_availability = tomorrow + datetime.timedelta(
                minutes=index
            )
            PractitionerContractFactory.create(
                practitioner=practitioner,
                contract_type=ContractType.HYBRID_2_0,
            )

            # 2 hours of availability for each practitioner
            factories.ScheduleFactory.create(user=practitioner.user)
            factories.ScheduleEventFactory.create(
                schedule=practitioner.user.schedule,
                starts_at=practitioner.next_availability,
                ends_at=practitioner.next_availability
                + datetime.timedelta(minutes=120),
            )

        for practitioner in practitioners[0:-1]:
            # 100% utilization for all practitioners except practitioner 8
            factories.AppointmentFactory.create_with_practitioner(
                practitioner=practitioner.user,
                scheduled_start=practitioner.next_availability,
                scheduled_end=practitioner.next_availability
                + datetime.timedelta(minutes=120),
            )

        actual_practitioners, count = ProviderService().search(current_user=member)

        # Assert that practitioner 8 (0% utilization) is not ranked above all others
        assert len(practitioners) == count
        for index, actual_practitioner in enumerate(actual_practitioners):
            assert actual_practitioner.practitioner_profile == practitioners[index]


class TestBusinessModelCases:
    def test_search__show_in_marketplace(
        self,
        factories,
        eight_practitioners,
    ):
        """
        Tests that only practitioners with show_in_marketplace enabled
        are shown to marketplace users
        """

        member = factories.MemberFactory.create()
        _, _, _, practitioners = eight_practitioners
        all_practitioner_ids = [p.user_id for p in practitioners]

        for prac in practitioners[4:]:
            prac.show_in_marketplace = False

        expected_practitioner_ids = {
            practitioners[0].user_id,
            practitioners[1].user_id,
            practitioners[2].user_id,
            practitioners[3].user_id,
        }

        actual_practitioners, count = ProviderService().search(
            current_user=member,
            user_ids=all_practitioner_ids,
        )
        actual_practitioner_ids = {p.id for p in actual_practitioners}

        assert count == 4
        assert actual_practitioner_ids == expected_practitioner_ids

    def test_search__show_in_enterprise(
        self,
        eight_practitioners,
        enterprise_user,
    ):
        """
        Tests that only practitioners with show_in_enterprise enabled
        are shown to enterprise users
        """

        _, _, _, practitioners = eight_practitioners
        all_practitioner_ids = [p.user_id for p in practitioners]

        for prac in practitioners[4:]:
            prac.show_in_enterprise = False

        expected_practitioner_ids = {
            practitioners[0].user_id,
            practitioners[1].user_id,
            practitioners[2].user_id,
            practitioners[3].user_id,
        }

        actual_practitioners, count = ProviderService().search(
            current_user=enterprise_user,
            user_ids=all_practitioner_ids,
        )
        actual_practitioner_ids = {p.id for p in actual_practitioners}

        assert count == 4
        assert actual_practitioner_ids == expected_practitioner_ids


class TestLanguagesFiltering:
    def test_search__restricted_list_of_language_ids(
        self,
        factories,
        eight_practitioners,
        three_languages,
        enterprise_user,
    ):
        _, _, _, practitioners = eight_practitioners

        # practitioners 1, 5, 6 have language 1
        expected_practitioners = [practitioners[0], practitioners[4], practitioners[5]]
        expected_practitioner_ids = {p.user_id for p in expected_practitioners}

        language_1 = three_languages[0]

        with mock.patch(
            "storage.connector.RoutingSQLAlchemy.s_replica1",
            new_callable=PropertyMock,
        ) as mock_session:
            mock_session.return_value = db.session

            actual_practitioners, count = ProviderService().search(
                current_user=enterprise_user,
                language_ids=[language_1.id],
            )

            actual_practitioner_ids = {p.id for p in actual_practitioners}

            assert count == 3
            assert actual_practitioner_ids == expected_practitioner_ids

    def test_search__restricted_list_of_language_ids__no_match(
        self,
        factories,
        eight_practitioners,
        enterprise_user,
    ):
        non_matching_language = factories.LanguageFactory.create(
            name="Non matching lang"
        )

        _, _, _, practitioners = eight_practitioners

        with mock.patch(
            "storage.connector.RoutingSQLAlchemy.s_replica1",
            new_callable=PropertyMock,
        ) as mock_session:
            mock_session.return_value = db.session

            # Search for the non-matching language
            _, count = ProviderService().search(
                current_user=enterprise_user,
                language_ids=[non_matching_language.id],
            )

            assert count == 0
