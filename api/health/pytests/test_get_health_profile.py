class TestGetHealthProfile:
    def test_empty_health_profile(self, default_user, client, api_helpers):
        default_user.health_profile.json = {}
        res = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert res.status_code == 200
        assert res.json == {}

    def test_view_own_data(self, default_user, client, api_helpers):
        res = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert res.status_code == 200
        assert res.json["due_date"] == default_user.health_profile.due_date.isoformat()

    def test_allowed_practitioner(self, client, api_helpers, factories):
        practitioner = factories.PractitionerUserFactory.create()
        appointment = factories.AppointmentFactory.create_with_practitioner(
            practitioner=practitioner
        )
        res = client.get(
            f"/api/v1/users/{appointment.member.id}/health_profile",
            headers=api_helpers.json_headers(practitioner),
        )
        assert res.status_code == 200
        assert (
            res.json["due_date"]
            == appointment.member.health_profile.due_date.isoformat()
        )

    def test_disallowed_practitioner(
        self, default_user, client, api_helpers, factories
    ):
        practitioner = factories.PractitionerUserFactory.create()
        appointment = factories.AppointmentFactory.create_with_practitioner(
            practitioner=practitioner
        )
        assert appointment.member.id != default_user.id
        res = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(practitioner),
        )
        assert res.status_code == 403

    # Note: Bank of America Security Audit issue
    # see https://app.clubhouse.io/maven-clinic/story/32226/remediate-user-id-enumeration-889230-p3
    # We will want to return the same code for valid and invalid users
    def test_invalid_user_error(self, default_user, client, api_helpers, factories):
        practitioner = factories.PractitionerUserFactory.create()
        res = client.get(
            f"/api/v1/users/{default_user.id}/health_profile",
            headers=api_helpers.json_headers(practitioner),
        )
        assert res.status_code == 403

    def test_nonexistent_user_error(self, default_user, client, api_helpers):
        res = client.get(
            f"/api/v1/users/{-500}/health_profile",
            headers=api_helpers.json_headers(default_user),
        )
        assert res.status_code == 404
