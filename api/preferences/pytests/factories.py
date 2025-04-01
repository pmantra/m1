from __future__ import annotations

import random

import factory

from preferences import models
from pytests import factories


class PreferenceFactory(factory.Factory):
    class Meta:
        model = models.Preference

    name = factory.Faker("word")
    default_value = str(random.randint(0, 1))
    type = "bool"


class MemberPreferenceFactory(factory.Factory):
    class Meta:
        model = models.MemberPreference

    value = str(random.randint(0, 1))
    preference_id = factory.Sequence(lambda n: n + 1)

    @classmethod
    def create_with_preference(cls, preference: models.Preference, **kwargs):
        user = factories.EnterpriseUserFactory.create()
        return cls.create(
            member_id=user.member_profile.user_id,
            preference_id=preference.id,
            **kwargs,
        )
