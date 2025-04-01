from unittest import mock

from data_admin.views import apply_specs


def test_admin_practitioner_fixture(data_admin_app, load_fixture):
    fixture = load_fixture("create_practitioner/create_admin.json")

    with data_admin_app.test_request_context(), mock.patch(
        "data_admin.makers.user._add_a_user_benefit_id"
    ):
        created, errors = apply_specs(fixture)

    assert errors == []
    assert len(created) == 3
    _, staff_role, admin = created
    assert admin.otp_secret == "admin"
    assert staff_role in admin.roles
    assert len(staff_role.capabilities) == 2
