class TestAdminListUsers:
    def test_view_list(self, admin_client, enterprise_user):
        # when we view the list of users
        res = admin_client.get("/admin/user/", follow_redirects=True)

        # then this user should be visible
        assert res.status_code == 200
        html = res.data.decode("utf8")
        assert enterprise_user.email in html
        assert enterprise_user.username in html
