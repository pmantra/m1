#!/usr/bin/env python3
"""
set_partner_module.py

Assign a set of existing modules to be partners.

Usage:
  set_partner_module.py <module-a> <module-b>

Options:
  -h --help     Show this screen.
"""
from sys import path

from docopt import docopt

path.insert(0, "/api")
try:
    from app import create_app
    from models.programs import Module
    from storage.connection import db
    from utils.log import logger
except ImportError:
    raise
log = logger(__name__)


def migrate(module_a, module_b):  # type: ignore[no-untyped-def] # Function is missing a type annotation

    ma = Module.query.filter_by(name=module_a).one()
    mb = Module.query.filter_by(name=module_b).one()

    for m in (ma, mb):
        if m.partner_module:
            raise AssertionError(
                f"Module {m} already has a partner module {m.partner_module}."
            )

    ma.partner_module = mb
    db.session.commit()

    log.info("All Done.")


if __name__ == "__main__":
    args = docopt(__doc__)
    with create_app().app_context():
        migrate(module_a=args["<module-a>"], module_b=args["<module-b>"])
