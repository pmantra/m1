import flask_login as login
from flask import Blueprint, redirect, request

from admin.common import _get_referer_path
from health.services.member_risk_service import MemberRiskService
from utils.log import logger

URL_PREFIX = "risk_flags"

log = logger(__name__)
risk_blueprint = Blueprint(URL_PREFIX, __name__)  # noqa


@risk_blueprint.route("/member_risk_edit", methods=["POST"])
@login.login_required
def member_risk_flag_edit():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    redirect_path = _get_referer_path()
    user_id = request.form.get("user_id", type=int)
    risk_name = request.form.get("risk_name")
    if risk_name:
        risk_name = risk_name.strip()
    try:
        risk_value = request.form.get("risk_value", type=int)
    except Exception:
        risk_value = None
    if user_id and risk_name:
        mrs = MemberRiskService(user_id)
        if "set_risk" in request.form:
            mrs.set_risk(risk_name, risk_value)
        elif "clear_risk" in request.form:
            mrs.clear_risk(risk_name)

    return redirect(redirect_path)
