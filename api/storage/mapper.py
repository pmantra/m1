# flake8: noqa
"""Helper module to allow for eagerly initializing the sqlalchemy mapper.

Most views are dependent upon authentication, so are implicitly dependent
upon the user.User model.

Unfortunately, that model has a number of backrefs to downstream objects,
which means these models must be accessible in the import path.

Once the User model is extracted, this will likely need to remain,
with the core model(s) becoming the Profile(s).

Adding model imports to this module will add them to the mapper path,
which may be useful to resolve latency issues, at the cost of longer startup times.
"""
from sqlalchemy import orm

from appointments.models import cancellation_policy, schedule
from authn.models import user
from authz.models import roles
from care_advocates.models import matching_rules
from models import advertising, forum, images, profiles, referrals

start_mappers = orm.configure_mappers
