import pytest

from appointments.utils.query_utils import load_queries_from_file


class TestQueryUtils:
    def test_load_queries_from_file(self):
        # TODO: consider using tempfile
        result = load_queries_from_file("appointments/pytests/utils/test.sql")

        assert result == [
            "SELECT a.id FROM appointment WHERE appointment.id = :appointment_id"
        ]

    def test_load_queries_from_file_file_not_found(self):
        file_path = "sd"

        with pytest.raises(FileNotFoundError):
            load_queries_from_file(file_path)
