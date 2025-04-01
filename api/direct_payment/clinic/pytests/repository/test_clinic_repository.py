class TestFertilityClinicRepository:
    def test_get(self, fertility_clinic, fertility_clinic_repository):
        assert (
            fertility_clinic_repository.get(fertility_clinic_id=fertility_clinic.id).id
            == fertility_clinic.id
        )

    def test_put(self, fertility_clinic, fertility_clinic_repository):
        # Arrange
        request_data = {"payments_recipient_data": "456"}

        # Act
        updated_clinic = fertility_clinic_repository.put(
            fertility_clinic_id=fertility_clinic.id,
            payments_recipient_id=request_data["payments_recipient_data"],
        )

        # Assert
        assert updated_clinic.payments_recipient_id == "456"
