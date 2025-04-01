import pytest

from assessments.utils.assessment_exporter import (
    AssessmentExportLogic,
    AssessmentExportTopic,
)
from models.enterprise import NeedsAssessmentTypes
from pytests.factories import AssessmentFactory
from storage.connection import db


@pytest.fixture(scope="function")
def fake_base_url():
    return (
        "https://healthcare.googleapis.com/v1/projects/fake/"
        "locations/fake/datasets/fake/fhirStores/fake/fhir"
    )


@pytest.fixture(scope="function")
def member(default_user, factories):
    default_user.member_profile = factories.MemberProfileFactory.create(
        user_id=default_user.id
    )
    return default_user


@pytest.fixture(scope="function")
def fhir_assessment(factories):
    assessment_type = NeedsAssessmentTypes.PREGNANCY_ONBOARDING
    alc = factories.AssessmentLifecycleFactory(
        name=assessment_type.value, type=assessment_type
    )
    db.session.add(alc)
    db.session.commit()
    return AssessmentFactory(
        lifecycle=alc,
        quiz_body={
            "questions": [
                {
                    "id": 1,
                    "export": {
                        AssessmentExportTopic.FHIR.value: {
                            "question_name": "conditions_active",
                            "export_logic": AssessmentExportLogic.FILTER_NULLS.value,
                        }
                    },
                },
                {
                    "id": 2,
                    "export": {
                        AssessmentExportTopic.FHIR.value: {
                            "question_name": "conditions_experienced",
                            "export_logic": AssessmentExportLogic.FILTER_NULLS.value,
                        }
                    },
                },
                {
                    "id": 3,
                    "export": {
                        AssessmentExportTopic.FHIR.value: {
                            "question_name": "existing_conditions",
                            "export_logic": AssessmentExportLogic.RAW.value,
                        }
                    },
                },
            ]
        },
    )
