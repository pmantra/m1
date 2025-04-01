# flake8: noqa
import itertools
from typing import Iterable

from flask import Flask
from flask_admin import Admin

from . import (
    admin,
    auth,
    authz,
    base,
    bookings,
    content,
    developer,
    enterprise,
    forum,
    index,
    payments,
    practitioners,
    user,
    wallet,
    wallet_config,
    wallet_reporting,
)

URLS = (
    user,
    practitioners,
    forum,
    enterprise,
    wallet_config,
    wallet,
    wallet_reporting,
    content,
    bookings,
    payments,
    developer,
    admin,
    authz,
)


def get_views() -> Iterable[base.AdminViewT]:
    yield from itertools.chain(*(x.get_views() for x in URLS))


def get_links() -> Iterable[base.AuthenticatedMenuLink]:
    yield from itertools.chain(*(x.get_links() for x in URLS))


def init_admin(application: Flask) -> Admin:
    admin_ = Admin(application, index_view=index.MavenIndexView(), name="Maven Admin")
    with application.app_context():
        admin_.add_views(*get_views())
        admin_.add_links(*get_links())

    return admin_
