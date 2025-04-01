import csv
import io

import flask_login as login
from flask import Blueprint, flash, redirect, request

from admin.common import https_url
from models.profiles import PractitionerProfile
from models.verticals_and_specialties import Specialty, Vertical
from storage.connection import db
from utils.log import logger

URL_PREFIX = "specialty-practitioners"

log = logger(__name__)
specialty_practitioners = Blueprint(URL_PREFIX, __name__)


@specialty_practitioners.route("/bulk-action", methods=["POST"])
@login.login_required
def specialty_bulk_action():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    if not request.form.get("specialty_id"):
        flash("Missing specialty ID!")
        return redirect(https_url("specialty.index_view"))

    specialty = Specialty.query.get_or_404(request.form["specialty_id"])
    association = specialty.practitioners
    action_type = request.form.get("action_type", "add")

    vertical_id = request.form.get("vertical_id", "")
    if not vertical_id.isnumeric():
        vertical_id = ""
    practitioners_csv = request.files.get("csv")
    if not vertical_id and not practitioners_csv:
        flash("You must provide either vertical_id or a practitioners csv!")
        return redirect(https_url("specialty.index_view"))
    elif vertical_id and practitioners_csv:
        flash("You must provide either vertical_id or a csv file not both!")
        return redirect(https_url("specialty.index_view"))

    targeted_practitioners = []
    if vertical_id:
        vertical = Vertical.query.get_or_404(vertical_id)
        targeted_practitioners = vertical.practitioners
    elif practitioners_csv:
        with io.StringIO(
            practitioners_csv.stream.read().decode("utf-8"), newline=None
        ) as stream:
            reader = csv.DictReader(stream, fieldnames=["user_id"])
            headers = next(reader, [])
            if len(headers) != 1:
                flash("CSV file has a wrong header!")
                return redirect(https_url("specialty.index_view"))

            for row in reader:
                try:
                    pp = PractitionerProfile.query.get(row["user_id"])
                    targeted_practitioners.append(pp)
                except Exception as e:
                    log.info(f"Invalid user_id {row['user_id']}: {e}")
                    continue

    for pp in targeted_practitioners:
        if action_type == "add":
            association.append(pp)
        elif action_type == "delete":
            if pp in association:
                association.remove(pp)
            else:
                log.info("%s does not have % currently.", pp, specialty)

    db.session.add(specialty)
    db.session.commit()

    flash(f'All set bulk add/delete "{specialty.name}" for specified practitioners.')
    return redirect(https_url("specialty.index_view"))
