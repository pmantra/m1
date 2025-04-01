def test_get(fertility_clinic_location, fertility_clinic_location_repository):
    assert (
        fertility_clinic_location_repository.get(
            fertility_clinic_location_id=fertility_clinic_location.id
        ).id
        == fertility_clinic_location.id
    )


def test_get_by_clinic_id(fertility_clinic, fertility_clinic_location_repository):
    # Act
    clinic_locations = fertility_clinic_location_repository.get_by_clinic_id(
        fertility_clinic_id=fertility_clinic.id
    )

    # Assert
    for clinic_location in clinic_locations:
        assert clinic_location in fertility_clinic.locations


def test_get_with_clinic(
    fertility_clinic_location_repository, fertility_clinic, fertility_clinic_location
):
    clinic_loc = fertility_clinic_location_repository.get_with_clinic(
        fertility_clinic_location.id
    )
    assert clinic_loc.fertility_clinic == fertility_clinic
