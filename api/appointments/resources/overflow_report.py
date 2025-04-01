import datetime

from flask import request
from flask_restful import abort

from appointments.models.appointment import Appointment
from appointments.models.constants import APPOINTMENT_STATES
from appointments.resources.constants import OverflowReportArgs, OverflowReportRequest
from appointments.tasks.appointments import appointment_completion
from common.services.api import UnauthenticatedResource
from storage.connection import db
from utils import security
from utils.log import logger

log = logger(__name__)


class OverflowReportResource(UnauthenticatedResource):
    def get_post_request(self, request_json: dict) -> OverflowReportRequest:
        return OverflowReportRequest(
            token=str(request_json["token"]), report=str(request_json["report"])
        )

    def post(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        schema = OverflowReportArgs()
        request_json = request.json if request.is_json else None
        args = schema.load(request_json).data
        try:
            python_args = self.get_post_request(request_json)
            if python_args == args:
                log.info("FM - OverflowReportResource POST identical")
            else:
                log.info(
                    "FM - OverflowReportResource POST discrepancy",
                    token_eq=python_args.get("token") == args.get("token"),
                    report_eq=python_args.get("report") == args.get("report"),
                )
        except Exception:
            log.info("FM - OverflowReportResource POST error")

        if args.get("report") not in ["YES", "NO"]:
            abort(400)

        appointment_id = security.check_overflowing_appointment_token(args["token"])
        if not appointment_id:
            log.warning("Expired or Bad Overflow Report Token")
            return abort(403, message="Bad Token!")
        else:
            log.debug("Processing report for Appt ID %s", appointment_id)

            if appointment_id:
                appointment = Appointment.query.get_or_404(appointment_id)
            else:
                abort(404)

            if appointment.state != APPOINTMENT_STATES.overflowing:
                log.info("Report for %s not in OVERFLOWING", appointment)
                abort(400, message="Appointment not overflowing...")
            if not appointment.started_at:
                log.info("%s: both ends have not joined... no-show!", appointment)
                abort(400, message="Appointment not overflowing...")

            if args["report"] == "YES":
                now = datetime.datetime.utcnow()

                appointment.member_ended_at = now
                appointment.practitioner_ended_at = now
                appointment.json["completed_via_report"] = True
                appointment.json["completed_at"] = str(now)

                log.debug("Saving report-completed appt: %s", appointment)
                db.session.add(appointment)
                db.session.commit()
                log.debug("Saved %s", appointment)

                appointment_completion.delay(appointment_id)

            elif args["report"] == "NO":
                now = datetime.datetime.utcnow()

                appointment.json["practitoner_responded_overflow"] = True
                appointment.json["practitoner_responded_overflow_at"] = str(now)

                log.debug("Saving reported-bad appt: %s", appointment)
                db.session.add(appointment)
                db.session.commit()
                log.debug("Saved %s", appointment)

            log.info("Processed report (%s) for %s", args["report"], appointment)
            return "", 204
