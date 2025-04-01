import factory
import pytest

from care_advocates.models.transitions import CareAdvocateMemberTransitionTemplate
from l10n.db_strings.slug_backfill import BackfillL10nSlugs
from models.verticals_and_specialties import Vertical
from pytests import factories
from storage.connection import db


class TestBackfillL10nSlugs:
    @pytest.mark.parametrize(
        "name_to_convert, expected_slug",
        [
            ("Women's Fertility", "womens_fertility"),
            ("OB-GYN", "obgyn"),
            ("High-risk OB (MFM)", "highrisk_ob_mfm"),
            ("LGBTQIA+ family building", "lgbtqia_family_building"),
            ("Finding a sperm/egg/embryo donor", "finding_a_sperm_egg_embryo_donor"),
            ("COVID-19, cold, and flu", "covid19_cold_and_flu"),
        ],
    )
    def test_convert_name_to_slug(self, name_to_convert, expected_slug):
        assert (
            BackfillL10nSlugs().convert_name_to_slug(name_to_convert) == expected_slug
        )

    def test_generate_question_slug(self):
        questionnaire_oid = "first_oid"
        question_set_oid = "second_oid"
        question_oid = "third_oid"
        expected = "first_oid_second_oid_third_oid"
        actual = BackfillL10nSlugs.generate_question_slug(
            questionnaire_oid,
            question_set_oid,
            question_oid,
        )

        assert actual == expected

    def test_generate_answer_slug(self):
        questionnaire_oid = "first_oid"
        question_set_oid = "second_oid"
        question_oid = "third_oid"
        answer_oid = "fourth_oid"
        expected = "first_oid_second_oid_third_oid_fourth_oid"
        actual = BackfillL10nSlugs.generate_answer_slug(
            questionnaire_oid,
            question_set_oid,
            question_oid,
            answer_oid,
        )

        assert actual == expected

    def test_backfill_slugs_with_name(self):
        # given models
        (
            factories.VerticalFactoryNoSlug.create_batch(
                size=5,
                name=factory.Iterator(
                    [
                        "Adoption Coach",
                        "Career Coach",
                        "OB-GYN",
                        "Doula",
                        "Nurse Practitioner",
                    ]
                ),
            )
        )
        expected_slugs = [
            "adoption_coach",
            "career_coach",
            "obgyn",
            "doula",
            "nurse_practitioner",
        ]
        # when we call the backfill
        BackfillL10nSlugs().backfill_slugs_with_name(Vertical, dry_run=False)
        # then
        created_slugs = db.session.query(Vertical.slug).all()
        assert set([slug[0] for slug in created_slugs]) == set(expected_slugs)

    def test_backfill_slugs_with_name__duplicate_slug(self):
        # given models with names that should result in duplicate slugs
        verticals = factories.VerticalFactoryNoSlug.create_batch(
            size=5,
            name=factory.Iterator(
                ["Adoption Coach", "Adoption_Coach", "OB-GYN", "OBGYN", "ObGyN "]
            ),
        )
        expected_slugs = [
            "adoption_coach",
            f"adoption_coach_{verticals[1].id}",
            "obgyn",
            f"obgyn_{verticals[3].id}",
            f"obgyn_{verticals[4].id}",
        ]
        # when we call the backfill
        BackfillL10nSlugs().backfill_slugs_with_name(Vertical, dry_run=False)
        # then
        created_slugs = db.session.query(Vertical.slug).all()
        assert set([slug[0] for slug in created_slugs]) == set(expected_slugs)

    def test_backfill_ca_member_transition_slugs(self):
        # given transition templates
        (
            factories.CareAdvocateMemberTransitionTemplateFactory.create_batch(
                size=2, message_type=factory.Iterator(["FAREWELL", "FOLLOWUP_INTRO"])
            )
        )
        expected_slugs = ["farewell", "followup_intro"]
        # when we call the backfill
        BackfillL10nSlugs().backfill_ca_member_transition_slugs(dry_run=False)
        # then
        created_slugs = db.session.query(
            CareAdvocateMemberTransitionTemplate.slug
        ).all()
        assert set([slug[0] for slug in created_slugs]) == set(expected_slugs)
