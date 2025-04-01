import contextlib
from unittest import mock

import marshmallow_v1
from sqlalchemy.exc import ResourceClosedError

from storage import connector
from utils.log import logger
from views.schemas.common import RAISE_ATTRIBUTE_ERRORS_FLAG

log = logger(__name__)


@contextlib.contextmanager
def undo(db: connector.RoutingSQLAlchemy):
    nested = db.session.begin_nested()
    yield
    try:
        nested.rollback()
    # This means the transaction was already rolled back upstream,
    #   probably because of a database error.
    # We're okay to ignore since we're leaving this transaction/change-set behind anyway.
    except ResourceClosedError:
        pass
    db.session.expire_all()
    db.session.expunge_all()


@contextlib.contextmanager
def restore(db: connector.RoutingSQLAlchemy, *targets, benchmark: bool = True):
    from schemas.io import restore

    with undo(db):
        restore(targets, benchmark=benchmark)
        yield


# -----------------------------------------------------------
# enable_serialization_attribute_errors is a test utility that can be used to
# identify exceptions that are thrown inside method resolution of fields in
# Marshmallow Schemas. Normally if a application level AttributeError is raised
# during serialization, it will be swallowed and the field will be nulled in the
# response.
#
# The explicit use of `required=True` will cause the exception to be raised. We
# currently do not us this property consistently in our schemas causing many
# runtime exceptions to be missed during testing.


@contextlib.contextmanager
def enable_serialization_attribute_errors():
    log.warning("⚠️ Enabling serialization attribute errors")
    with mock.patch.object(
        target=marshmallow_v1.fields.Method,
        attribute=RAISE_ATTRIBUTE_ERRORS_FLAG,
        create=True,
    ):
        yield
    pass
