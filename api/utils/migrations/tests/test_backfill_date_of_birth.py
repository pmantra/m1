from health.models.health_profile import HealthProfile
from pytests.factories import DefaultUserFactory, HealthProfileFactory
from utils.log import logger
from utils.migrations.backfill_date_of_birth import backfill_date_of_birth

log = logger(__name__)


def test_backfill():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    user1 = DefaultUserFactory.create()
    user2 = DefaultUserFactory.create()
    HealthProfileFactory.create(user=user1, json={"birthday": "2022-01-02"})
    HealthProfileFactory.create(user=user2, json={"birthday": "hello buddy!"})

    num_profiles = HealthProfile.query.count()
    assert num_profiles == 2

    backfill_date_of_birth(False)

    profiles = HealthProfile.query.all()
    assert profiles[0].date_of_birth.strftime("%Y-%m-%d") == "2022-01-02"
    assert profiles[1].date_of_birth is None
