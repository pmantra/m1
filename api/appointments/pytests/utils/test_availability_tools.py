from appointments.utils.booking import AvailabilityTools


class TestAvailabilityTools:
    def test_has_had_ca_intro_appointment__true(self, factories):
        # Given, a member that has already had a CA appt
        appt = factories.AppointmentFactory()
        member = appt.member_schedule.user
        practitioner = appt.product.practitioner
        CA_vertical = factories.VerticalFactory.create(name="Care Advocate")
        practitioner.practitioner_profile.verticals = [CA_vertical]

        # When
        has_had_ca_intro_appt = AvailabilityTools.has_had_ca_intro_appointment(member)

        # Then
        assert has_had_ca_intro_appt

    def test_has_had_ca_intro_appointment__false_obgyn_appt(self, factories):

        # Given, a member that has only had an appt with an obgyn
        appt = factories.AppointmentFactory()
        member = appt.member_schedule.user
        practitioner = appt.product.practitioner
        OBGYN_vertical = factories.VerticalFactory.create(name="OB-GYN")
        practitioner.practitioner_profile.verticals = [OBGYN_vertical]

        # When
        has_had_ca_intro_appt = AvailabilityTools.has_had_ca_intro_appointment(member)

        # Then
        assert has_had_ca_intro_appt is False

    def test_has_had_ca_intro_appointment__false_no_appts(self, factories):

        # Given, a member that has not had any appt
        member = factories.DefaultUserFactory()
        # When
        has_had_ca_intro_appt = AvailabilityTools.has_had_ca_intro_appointment(member)

        # Then
        assert has_had_ca_intro_appt is False
