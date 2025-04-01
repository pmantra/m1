import csv
import io

import flask_login as login
from flask import Blueprint, flash, redirect, request

from admin.common import https_url
from appointments.models.payments import FeeAccountingEntry
from authn.models.user import MFAState, User
from storage.connection import db
from utils.log import logger

URL_PREFIX = "practitioner_management"

log = logger(__name__)
practitioner_blueprint = Blueprint(URL_PREFIX, __name__)


@practitioner_blueprint.route("/delete_fees", methods=["POST"])
@login.login_required
def delete_fees_in_bulk():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    fee_id_type = request.form.get("fee_id_type")
    if fee_id_type not in ("message", "appointment"):
        flash("Invalid fee ID type!")
        return redirect(https_url("admin.index"))

    fee_ids = request.files.get("csv")
    if not fee_ids:
        flash("Attach a CSV!")
        return redirect(https_url("admin.index"))

    stream = io.StringIO(fee_ids.stream.read().decode("utf8"), newline=None)
    reader = csv.reader(stream)

    if max(len(r) for r in reader) > 1:
        flash("Only 1 column of IDs is allowed")
        return redirect(https_url("admin.index"))

    fee_ids = []
    stream.seek(0)
    for row in reader:
        if row and row[0]:
            try:
                fee_ids.append(int(row[0]))
            except ValueError:
                flash(f"Bad ID: {row[0]}")
                return redirect(https_url("admin.index"))

    if not fee_ids:
        flash("No IDs provided!")
        return redirect(https_url("admin.index"))

    base_query = db.session.query(FeeAccountingEntry)
    if fee_id_type == "message":
        fees = base_query.filter(FeeAccountingEntry.message_id.in_(fee_ids)).all()
    elif fee_id_type == "appointment":
        fees = base_query.filter(FeeAccountingEntry.appointment_id.in_(fee_ids)).all()

    if len(fees) > len(set(fee_ids)):
        flash("Too many fees for the IDs provided!")
        return redirect(https_url("admin.index"))
    else:
        log.info(f"Going to delete {len(fees)} fees")
        for fee in fees:
            log.info(f"Going to delete {fee}")
            db.session.delete(fee)

        log.info("Finished with bulk fee deletion...")
        db.session.commit()
        flash(f"All set deleting {len(fees)} fees")
        return redirect(https_url("admin.index"))


@practitioner_blueprint.route("/disable_mfa", methods=["POST"])
@login.login_required
def disable_practitioner_mfa():  # type: ignore[no-untyped-def] # Function is missing a return type annotation

    # TODO: after https://app.shortcut.com/maven-clinic/story/147741/maintain-enabled-mfa-state-for-providers-updating-mfa-phone-number
    # this can be simplified to User.is_practitioner, User.mfa_state == MFAState.ENABLED, User.sms_phone_number != ''
    mfa_enabled_practitioners = User.query.filter(
        User.is_practitioner,
        User.mfa_state != MFAState.DISABLED,
        User.sms_phone_number != "",
    ).all()

    for practitioner_user in mfa_enabled_practitioners:
        practitioner_user.mfa_state = MFAState.DISABLED
        db.session.add(practitioner_user)

    db.session.commit()

    flash(f"Disabled MFA for {len(mfa_enabled_practitioners)} practitioners")
    return redirect(https_url("admin.index"))


@practitioner_blueprint.route("/enable_mfa", methods=["POST"])
@login.login_required
def enable_practitioner_mfa():  # type: ignore[no-untyped-def] # Function is missing a return type annotation

    mfa_disabled_practitioners = User.query.filter(
        User.is_practitioner,
        User.mfa_state == MFAState.DISABLED,
        User.sms_phone_number != "",
    ).all()

    count_enabled = 0

    for practitioner_user in mfa_disabled_practitioners:
        if (
            practitioner_user.sms_phone_number is None
            or practitioner_user.sms_phone_number == ""
        ):
            continue
        practitioner_user.mfa_state = MFAState.ENABLED
        db.session.add(practitioner_user)
        count_enabled += 1

    db.session.commit()

    flash(f"Enabled MFA for {count_enabled} practitioners")
    return redirect(https_url("admin.index"))
