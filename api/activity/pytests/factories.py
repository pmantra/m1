from __future__ import annotations

import datetime

import factory

from activity import models


class UserActivityFactory(factory.Factory):
    class Meta:
        model = models.UserActivity

    user_id = factory.Sequence(lambda n: n + 1)
    activity_type = models.UserActivityType.LAST_LOGIN
    activity_date = datetime.datetime.utcnow()
