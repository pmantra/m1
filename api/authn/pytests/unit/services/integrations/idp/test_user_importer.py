from authn.pytests import factories
from authn.services.integrations import idp


class TestUserImporter:
    @staticmethod
    def test_build_payload():
        # Given
        user = factories.UserFactory.create()
        password = "pbkdf2:sha256:10000$abcd$abcd1234"
        user.password = password
        # The above password with the appropriate hex/b64 encoding results in the below "value"
        expected_payload = {
            "email": user.email,
            "name": user.email,
            "email_verified": True,
            "custom_password_hash": {
                "algorithm": "pbkdf2",
                "hash": {
                    "value": "$pbkdf2-sha256$i=10000,l=32$YWJjZA$q80SNA",
                    "encoding": "utf8",
                },
            },
            "app_metadata": {"maven_user_id": user.id},
        }

        # When
        payload = idp.import_helper.build_payload(user)

        # Then
        assert payload == expected_payload
