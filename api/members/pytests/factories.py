import datetime

import factory

import pytests.factories as factories
from conftest import BaseMeta
from members.models.async_encounter_summary import (
    AsyncEncounterSummary,
    AsyncEncounterSummaryAnswer,
)

SQLAlchemyModelFactory = factory.alchemy.SQLAlchemyModelFactory


class AsyncEncounterSummaryFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AsyncEncounterSummary

    id = factory.Sequence(lambda n: n + 1)
    provider = factory.SubFactory(factories.PractitionerUserFactory)
    user = factory.SubFactory(factories.EnterpriseUserFactory)
    questionnaire = factory.SubFactory(factories.QuestionnaireFactory)
    encounter_date = datetime.datetime.now()


class AsyncEncounterSummaryAnswerFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = AsyncEncounterSummaryAnswer

    id = factory.Sequence(lambda n: n + 1)
    async_encounter_summary = factory.SubFactory(AsyncEncounterSummaryFactory)
    question = factory.SubFactory(factories.QuestionFactory)
    text = "test answer"
    date = datetime.datetime.now()
