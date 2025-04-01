from typing import Any, Dict, Union

from flask import jsonify, make_response, request
from flask_babel import lazy_gettext

from appointments.models.appointment import Appointment
from appointments.services.common import deobfuscate_appointment_id
from common import stats
from common.services.api import PermissionedUserResource
from utils.constants import VIDEO_PROBLEM_REPORTED
from utils.log import logger

log = logger(__name__)

# when adding more options please create a new ID and text rather than edit an existing ID's text
Q1_OPTIONS = [
    {"id": 1, "text": lazy_gettext("report_problem_q1_o1")},
    {"id": 2, "text": lazy_gettext("report_problem_q1_o2")},
    {"id": 3, "text": lazy_gettext("report_problem_q1_o3")},
    {"id": 4, "text": lazy_gettext("report_problem_q1_o4")},
]
Q1_OPTIONS_DICT = {option["id"]: option["text"] for option in Q1_OPTIONS}
Q1_TEXT = lazy_gettext("report_problem_q1_text")
QUESTIONS = [
    {
        "id": 1,
        "question": Q1_TEXT,
        "options": Q1_OPTIONS,
    }
]
TITLE_TEXT = lazy_gettext("report_problem_title")
HEADER_TEXT = lazy_gettext("report_problem_header")
APPOINTMENT_MISSING_ERROR = lazy_gettext("report_problem_app_missing")


class ReportProblemResource(PermissionedUserResource):
    def get(self) -> Union[Dict[str, Any], Any]:
        """
        Retrieves the multi-select options for the "report a problem" modal on video appointments
        """
        try:
            response_data = {
                "title_text": TITLE_TEXT,
                "header_text": HEADER_TEXT,
                "questions": QUESTIONS,
            }
            return make_response(jsonify(response_data), 200)
        except Exception as e:
            log.error("Error trying to retrieve report problem options", error=str(e))
            return make_response(
                jsonify({"error": "Failed to retrieve report problem options"}), 500
            )

    def post(self) -> Union[Dict[str, Any], Any]:
        """
        Given an appointment ID and a list of appointment problems, log them to datadog
        """
        data = request.get_json()
        appointment_id = None
        appointment = None
        if appointment_api_id_param := data.get("appointment_api_id"):
            appointment_id = deobfuscate_appointment_id(int(appointment_api_id_param))
            appointment = Appointment.query.get(appointment_id)
        if not appointment:
            log.warning(
                "Missing appointment when reporting a video problem",
                appointment_id=appointment_id,
            )
            return make_response(
                jsonify({"message": str(APPOINTMENT_MISSING_ERROR)}),
                400,
            )
        reported_problems = data.get("option_ids")
        problem_list = []
        for option in reported_problems:
            option_id = option.get("id")
            # taking the option IDs given from the clients and getting the matching text
            if option_id in Q1_OPTIONS_DICT:
                problem = Q1_OPTIONS_DICT.get(option_id)
                problem_list.append(problem)
                stats.increment(
                    metric_name=VIDEO_PROBLEM_REPORTED,
                    pod_name=stats.PodNames.VIRTUAL_CARE,
                    tags=[f"problem:{problem}"],
                )

        log.info(
            "Participant reported a problem on their video appointment",
            appointment_id=appointment_id,
            problems=problem_list,
            user_id=self.user.id,
            role=self.user.role_name,
            zoom_session_id=data.get("zoom_session_id"),
        )
        return make_response({}, 200)
