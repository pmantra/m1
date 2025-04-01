# flake8: noqa
from flask import Flask

from admin.common import ROOT_URL_PREFIX

from .actions import actions as actions_blueprint
from .auto_practioner_invite import auto_practitioner_invite
from .enterprise import enterprise_setup
from .matching_rules import care_advocate_matching
from .practitioner import practitioner_blueprint
from .rbac import rbac
from .reporting import reporting
from .risk_flags import risk_blueprint
from .specialty_practioners import specialty_practitioners
from .wallet import wallet

URLS = (
    actions_blueprint,
    auto_practitioner_invite,
    care_advocate_matching,
    enterprise_setup,
    practitioner_blueprint,
    reporting,
    specialty_practitioners,
    wallet,
    rbac,
    risk_blueprint,
)


def register_blueprints(
    application: Flask, root_url_prefix: str = ROOT_URL_PREFIX
) -> None:
    for bp in URLS:
        application.register_blueprint(bp, url_prefix=f"{root_url_prefix}/{bp.name}")
