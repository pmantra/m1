import pytest

from appointments.repository.appointment import AppointmentRepository
from pytests import factories


@pytest.fixture
def appointment():
    return factories.AppointmentFactory.create()


class TestAppointmentRepository:
    def test_get_by_id_not_exist(self):
        # Act
        result = AppointmentRepository().get_by_id(5555555)

        # Assert
        assert result is None

    def test_get_by_id(self, appointment):
        # Act
        result = AppointmentRepository().get_by_id(appointment.id)

        # Assert
        assert result is appointment
