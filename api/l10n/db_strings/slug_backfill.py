import re

from appointments.models.cancellation_policy import CancellationPolicy
from appointments.models.needs_and_categories import Need, NeedCategory
from care_advocates.models.transitions import CareAdvocateMemberTransitionTemplate
from models.verticals_and_specialties import Specialty, Vertical
from storage.connection import db
from utils.log import logger

log = logger(__name__)


class BackfillL10nSlugs:
    def convert_name_to_slug(self, name_to_convert: str) -> str:
        # convert spaces and / to _
        name_without_spaces = (
            name_to_convert.strip().replace(" ", "_").replace("/", "_")
        )
        # remove multiple underscores and any other special chars
        slug_name = (
            re.sub("[^A-Za-z0-9_]+", "", name_without_spaces)
            .replace("___", "_")
            .replace("__", "_")
        )
        return slug_name.lower()

    @staticmethod
    def generate_question_slug(
        questionnaire_oid: str,
        question_set_oid: str,
        question_oid: str,
    ) -> str:
        return f"{questionnaire_oid}_{question_set_oid}_{question_oid}"

    @staticmethod
    def generate_answer_slug(
        questionnaire_oid: str,
        question_set_oid: str,
        question_oid: str,
        answer_oid: str,
    ) -> str:
        return f"{questionnaire_oid}_{question_set_oid}_{question_oid}_{answer_oid}"

    def backfill_slugs_with_name(self, model, dry_run=True) -> None:  # type: ignore[no-untyped-def] # Function is missing a type annotation
        results = db.session.query(model).all()
        added_slugs = set()
        try:
            for result in results:
                if result.slug:
                    # don't overwrite existing slug
                    continue
                generated_slug = self.convert_name_to_slug(result.name)
                # check for duplicates
                if generated_slug not in added_slugs:
                    result.slug = generated_slug
                else:
                    log.warning(
                        "Duplicate slug values found - appending ID to slug",
                        slug=generated_slug,
                        name=result.name,
                        id=result.id,
                    )
                    result.slug = f"{generated_slug}_{result.id}"
                added_slugs.add(result.slug)
                log.info("Added slug", slug=result.slug, name=result.name)
            if not dry_run:
                db.session.commit()
        except Exception as e:
            log.error("Error adding slug", error=e)

    def backfill_ca_member_transition_slugs(self, dry_run: bool = True) -> None:
        templates = db.session.query(CareAdvocateMemberTransitionTemplate).all()
        added_slugs = set()
        try:
            for template in templates:
                if template.slug:
                    # don't overwrite existing slug
                    continue
                generated_slug = self.convert_name_to_slug(template.message_type)
                # check for duplicates
                if generated_slug not in added_slugs:
                    template.slug = generated_slug
                else:
                    log.warning(
                        "Duplicate slug values found - appending ID to slug",
                        slug=template.slug,
                        message_type=template.message_type,
                    )
                    template.slug = f"{generated_slug}_{template.id}"
                added_slugs.add(template.slug)
                log.info(
                    "Added slug", slug=template.slug, message_type=template.message_type
                )
            if not dry_run:
                db.session.commit()
        except Exception as e:
            log.error("Error adding slug", error=e)

    def backfill_slug_columns(self, dry_run: bool = True) -> None:
        models_with_name = [Vertical, Need, NeedCategory, Specialty, CancellationPolicy]
        log.info("Starting to backfill slugs")
        for model in models_with_name:
            self.backfill_slugs_with_name(model, dry_run)
        self.backfill_ca_member_transition_slugs(dry_run)
        log.info("Backfill complete")
