from unittest.mock import patch

from common.services.healthchecks import ReadinessResource


def throw_exception(self):
    raise AttributeError("random application exception")


class TestExceptionAwareApi:
    @patch.object(ReadinessResource, "get", throw_exception)
    def test_structured_exception_log(self, app, logs):
        # we are only interested in the exception message
        original_setting = app.config["PROPAGATE_EXCEPTIONS"]
        app.config["PROPAGATE_EXCEPTIONS"] = False
        client = app.test_client()
        resp = client.get("/api/readyz")
        app.config["PROPAGATE_EXCEPTIONS"] = original_setting

        # we expect a server error
        assert resp.status_code == 500

        # find the log record
        log_record = next(
            (r for r in logs if "Unhandled application exception" in r["event"]),
            None,
        )
        # ensure it has the things we care about
        assert log_record is not None
        assert log_record["exception"] is not None
        assert "random application exception" in str(log_record["exception"][1])
