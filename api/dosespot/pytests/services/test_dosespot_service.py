from dosespot.services.dosespot_service import create_dosespot_patient_data
from storage.connection import db


def test_create_dosespot_patient_data(appointment, set_member_address):
    # Arrange
    member = appointment.member

    # Act
    result = create_dosespot_patient_data(appointment)

    # Assert
    assert result["FirstName"] == member.first_name[:35]
    assert result["City"] == member.member_profile.address.city
    assert result["NonDoseSpotMedicalRecordNumber"] == str(member.id)[:35]


def test_create_dosespot_patient_data_trims_long_fields(
    appointment, set_long_named_member_address
):
    # Arrange
    member = appointment.member
    member.first_name = "Superduperextrasuperduperlongfirstname"
    member.last_name = "Superduperextrasuperduperlonglastname"
    db.session.commit()

    # Act
    result = create_dosespot_patient_data(appointment)

    # Assert
    assert len(result["FirstName"]) == 35
    assert len(result["LastName"]) == 35
    assert len(result["Address1"]) == 35
