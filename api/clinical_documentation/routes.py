from clinical_documentation.resource.member_questionnaires import (
    MemberQuestionnairesResource,
)
from clinical_documentation.resource.mpractice_template import MPracticeTemplateResource
from clinical_documentation.resource.mpractice_templates import (
    MPracticeTemplatesResource,
)
from clinical_documentation.resource.post_appointment_note import (
    PostAppointmentNoteResource,
)
from clinical_documentation.resource.provider_addenda import ProviderAddendaResource
from clinical_documentation.resource.questionnaire_answers import (
    QuestionnaireAnswersResource,
)
from clinical_documentation.resource.structured_internal_notes import (
    StructuredInternalNoteResource,
)


def add_routes(api):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    api.add_resource(
        PostAppointmentNoteResource,
        "/v2/clinical_documentation/post_appointment_notes",
    )
    api.add_resource(
        MemberQuestionnairesResource,
        "/v2/clinical_documentation/member_questionnaires",
    )
    api.add_resource(
        ProviderAddendaResource,
        "/v2/clinical_documentation/provider_addenda",
    )
    api.add_resource(
        StructuredInternalNoteResource,
        "/v2/clinical_documentation/structured_internal_notes",
    )
    api.add_resource(
        QuestionnaireAnswersResource, "/v2/clinical_documentation/questionnaire_answers"
    )
    api.add_resource(MPracticeTemplatesResource, "/v1/clinical_documentation/templates")
    api.add_resource(
        MPracticeTemplateResource,
        "/v1/clinical_documentation/templates/<int:template_id>",
    )
    return api
