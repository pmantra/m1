from flask import make_response
from maven import feature_flags

from clinical_documentation.schema.questionnaire import (
    GetMemberQuestionnairesResponseSchemaV3,
)
from clinical_documentation.services.member_questionnaire_service import (
    MemberQuestionnairesService,
)
from common.services.api import AuthenticatedResource
from utils import launchdarkly


class MemberQuestionnairesResource(AuthenticatedResource):
    def get(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        """
        Return all of the questionnaire types that are potentially relevant to
        members viewing an appointment.
        """
        l10n_flag = feature_flags.bool_variation(
            "release-disco-be-localization",
            launchdarkly.user_context(self.user),
            default=False,
        )

        questionnaires = MemberQuestionnairesService().get_questionnaires()

        if l10n_flag:
            MemberQuestionnairesService.localize_questionnaires(questionnaires)

        schema = GetMemberQuestionnairesResponseSchemaV3()
        return make_response(schema.dump({"questionnaires": questionnaires}), 200)
