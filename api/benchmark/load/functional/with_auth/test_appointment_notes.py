import logging
import os
from json import JSONDecodeError

from locust import events, task
from maven.benchmarking.base_user_with_auth import BaseUserWithAuth


@events.quitting.add_listener
def _(environment, **kw):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if environment.stats.total.fail_ratio > 0.01:
        logging.error("Test failed due to failure ratio > 1%")
        environment.process_exit_code = 1
    elif environment.stats.total.avg_response_time > 2000:
        logging.error("Test failed due to average response time ratio > 2000 ms")
        environment.process_exit_code = 1
    elif environment.stats.total.get_response_time_percentile(0.95) > 2500:
        logging.error("Test failed due to 95th percentile response time > 2500 ms")
        environment.process_exit_code = 1
    else:
        environment.process_exit_code = 0


# override the on start and on stop to use an existing user and do not want to delete the user after
class GetWithAuthUser(BaseUserWithAuth):
    def on_start(self) -> None:
        self.client.headers = {"Content-Type": "application/json"}
        # get user
        self.client.email = os.getenv("LOCUST_USER_EMAIL")
        self.client.password = os.getenv("LOCUST_USER_PASSWORD")
        self.client.user_id = os.getenv("LOCUST_USER_ID")
        self.client.headers["X-Maven-User-ID"] = os.getenv("LOCUST_USER_ID")
        # get token
        self.client.token = None
        self.client.expiration = None
        self.client.refresh_token = None
        self.get_token()

    def on_stop(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        pass

    @task(weight=5)
    def post_appointment_notes(self):  # type: ignore[no-untyped-def] # Function is missing a return type annotation
        appointment_id = os.getenv("APPOINTMENT_ID")
        questionnaire_id = os.getenv("QUESTIONNAIRE_ID")
        question_id = os.getenv("QUESTION_ID")

        body = {
            "post_session": {
                "draft": True,
                "notes": "test of the post session notes",
            },
            "structured_internal_note": {
                "recorded_answer_set": {
                    "source_user_id": self.client.user_id,
                    "draft": True,
                    "appointment_id": appointment_id,
                    "questionnaire_id": questionnaire_id,
                    "recorded_answers": [
                        {
                            "user_id": self.client.user_id,
                            "payload": {"text": "internal structured test nav"},
                            "answer_id": None,
                            "question_type": "TEXT",
                            "question_id": question_id,
                            "appointment_id": appointment_id,
                            "date": None,
                            "text": "internal structured test nav",
                        }
                    ],
                    "submitted_at": "2023-10-23T10:00:00.000Z",
                }
            },
        }
        with self.client.post(
            f"/api/v1/appointments/{appointment_id}/notes",
            json=body,
            catch_response=True,
        ) as response:
            try:
                if not response.json()["post_session"]:
                    response.failure("Did not receive post session note")
            except JSONDecodeError:
                response.failure("Response could not be decoded as JSON")
            except KeyError:
                response.failure("Response did not contain expected key 'email'")
