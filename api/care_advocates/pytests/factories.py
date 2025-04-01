from factory.alchemy import SQLAlchemyModelFactory

from care_advocates.models.matching_rules import MatchingRule, MatchingRuleSet
from conftest import BaseMeta


class MatchingRuleSetFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MatchingRuleSet


class MatchingRuleFactory(SQLAlchemyModelFactory):
    class Meta(BaseMeta):
        model = MatchingRule
