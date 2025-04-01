from unittest import mock

import pytest
from otpauth import OtpAuth

from authz.models.roles import ROLES
from pytests.factories import CapabilityFactory, PractitionerUserFactory, RoleFactory
from utils.passwords import encode_password


@pytest.fixture
def staff_user():
    password = "testpass"
    staff = PractitionerUserFactory.create(
        password=encode_password(password), otp_secret="admin"
    )
    role = RoleFactory.create(
        name=ROLES.staff,
        capabilities=[CapabilityFactory.create(object_type="admin_all", method="get")],
    )
    staff.roles.append(role)
    return staff


class TestAdminLogin:
    def test_login(self, admin_client, staff_user):
        with mock.patch("authn.domain.service.authn", autospec=True) as m, mock.patch(
            "admin.login.authn", new=m
        ):
            service = m.AuthenticationService()
            service.check_password.return_value = True
            res = admin_client.post(
                "/admin/login/",
                data={
                    "email": staff_user.email,
                    "password": "testpass",
                    "totp": OtpAuth(staff_user.otp_secret).totp(),
                },
                follow_redirects=True,
            )

        assert res.status_code == 200
        html = res.data.decode("utf8")
        assert "Login to Maven" not in html
        assert "Errors:" not in html
        assert "Logout" in html

    def test_totp_validated(self, admin_client, staff_user):
        with mock.patch("authn.domain.service.authn", autospec=True) as m, mock.patch(
            "admin.login.authn", new=m
        ):
            service = m.AuthenticationService()
            service.check_password.return_value = True
            res = admin_client.post(
                "/admin/login/",
                data={
                    "email": staff_user.email,
                    "password": "testpass",
                    "totp": "notvalid",
                },
                follow_redirects=True,
            )
        assert b"Invalid TOTP" in res.data

    def test_logout(self, admin_client):
        res = admin_client.get("/admin/logout/")
        html = res.data.decode("utf8")
        assert "Redirecting" in html

    def test_login_logout(self, admin_client, staff_user):
        with mock.patch("authn.domain.service.authn", autospec=True) as m, mock.patch(
            "admin.login.authn", new=m
        ):
            service = m.AuthenticationService()
            service.check_password.return_value = True
            res = admin_client.post(
                "/admin/login/",
                data={
                    "email": staff_user.email,
                    "password": "testpass",
                    "totp": OtpAuth(staff_user.otp_secret).totp(),
                },
                follow_redirects=True,
            )

        res = admin_client.get("/admin/logout/")
        html = res.data.decode("utf8")
        assert "Redirecting" in html
