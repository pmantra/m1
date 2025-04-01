class TestGetAllAaIds:
    def test_get_all_aa_ids__no_aa_exist(self, assignable_advocate_repository):
        # Given no care advocates exist

        # When
        all_existing_ca_ids = assignable_advocate_repository.get_all_aa_ids()

        # Then
        assert all_existing_ca_ids == []

    def test_get_all_aa_ids__aa_exist(self, factories, assignable_advocate_repository):
        # Given some CAs exist
        prac1 = factories.PractitionerUserFactory.create()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac1)
        prac2 = factories.PractitionerUserFactory.create()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac2)

        # When
        all_existing_ca_ids = assignable_advocate_repository.get_all_aa_ids()

        # Then
        assert all_existing_ca_ids == [prac1.id, prac2.id]


class TestGetAllByPractitionerIds:
    def test_get_all_by_practitioner_ids__some_aas(
        self, factories, assignable_advocate_repository
    ):
        # Given some CAs exist
        prac1 = factories.PractitionerUserFactory.create()
        aa1 = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=prac1
        )
        prac2 = factories.PractitionerUserFactory.create()
        aa2 = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=prac2
        )
        prac3 = factories.PractitionerUserFactory.create()
        factories.AssignableAdvocateFactory.create_with_practitioner(practitioner=prac3)

        # When we pass in some of the existing CA's
        all_aas = assignable_advocate_repository.get_all_by_practitioner_ids(
            ids=[prac1.id, prac2.id]
        )

        # Then
        results_list = [aas.practitioner_id for aas in all_aas]
        assert results_list == [aa1.practitioner_id, aa2.practitioner_id]

    def test_get_all_by_practitioner_ids__all_aas(
        self, factories, assignable_advocate_repository
    ):
        # Given some CAs exist
        prac1 = factories.PractitionerUserFactory.create()
        aa1 = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=prac1
        )
        prac2 = factories.PractitionerUserFactory.create()
        aa2 = factories.AssignableAdvocateFactory.create_with_practitioner(
            practitioner=prac2
        )

        # When we pass in all of the existing CA's
        all_aas = assignable_advocate_repository.get_all_by_practitioner_ids(
            ids=[prac1.id, prac2.id]
        )

        # Then
        results_list = [aas.practitioner_id for aas in all_aas]
        assert results_list == [aa1.practitioner_id, aa2.practitioner_id]
