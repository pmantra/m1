import datetime

import flask_login as login
from flask import Blueprint, Response, flash, redirect, request, stream_with_context

from admin.common import https_url
from utils.log import logger
from utils.reporting import (
    all_invoices_csv,
    appointments_csv,
    invoices_by_date_csv,
    messaging_report_csv,
    practitioner_fees_csv,
)

URL_PREFIX = "reporting"

log = logger(__name__)
reporting = Blueprint(URL_PREFIX, __name__)


@reporting.route("/fees", methods=["POST"])
@login.login_required
def fees_report():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    start_at = _parse_date(request.form.get("start_date"), start=True)
    end_at = _parse_date(request.form.get("end_date"))

    if not (start_at and end_at):
        flash("Please enter a valid start/end date!")
        return redirect(https_url("admin.index"))

    report = practitioner_fees_csv(start_at, end_at)
    return _return_report(report, "fees.csv")


@reporting.route("/appointments", methods=["POST"])
@login.login_required
def appointments_report():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    start_at = _parse_date(request.form.get("start_date"), start=True)
    end_at = _parse_date(request.form.get("end_date"))

    if not (start_at and end_at):
        flash("Please enter a valid start/end date!")
        return redirect(https_url("admin.index"))

    report = appointments_csv(start_at, end_at)
    return _return_report(report, "appointments.csv")


@reporting.route("/messaging", methods=["POST"])
@login.login_required
def messaging_report():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    start_at = _parse_date(request.form.get("start_date"), start=True)
    end_at = _parse_date(request.form.get("end_date"))

    if not (start_at and end_at):
        log.debug("%s %s", start_at, end_at)
        flash("Please enter a valid start/end date!")
        return redirect(https_url("admin.index"))

    report = messaging_report_csv(start_at, end_at)
    return _return_report(report, "messaging.csv")


@reporting.route("/invoices/all")
@login.login_required
def invoices_report():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    report = all_invoices_csv()
    return _return_report(report, "invoices.csv")


@reporting.route("/invoices", methods=["POST"])
@login.login_required
def invoices_report_by_date():  # type: ignore[no-untyped-def] # Function is missing a return type annotation
    start_at = _parse_date(request.form.get("start_date"), start=True)
    end_at = _parse_date(request.form.get("end_date"))
    distributed_practitioner = request.form.get("distributed_practitioner")

    if not (start_at and end_at):
        flash("Please enter a valid start/end date!")
        return redirect(https_url("admin.index"))

    report = invoices_by_date_csv(start_at, end_at, distributed_practitioner)
    return _return_report(report, "invoices.csv")


def _return_report(report_generator, filename="report.csv"):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    response = Response(stream_with_context(report_generator))

    response.headers["Content-Description"] = "File Transfer"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Content-Type"] = "text/csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"

    return response


def _parse_date(date_str, start=False):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    try:
        dt = datetime.datetime.strptime(date_str, "%d-%m-%Y")
    except ValueError:
        log.info(f"Bad date in admin: {date_str}")
        return
    else:
        if start:
            return dt.replace(minute=0, microsecond=0, hour=0, second=0)
        else:
            return dt.replace(minute=59, microsecond=999999, hour=23, second=59)
