import json

import pytest

from data_admin.utils import extract_parameters_from_form, substitute_parameters


@pytest.fixture
def parameterized_fixture_data():
    """Test fixture with parameters and default values"""
    return {
        "parameters": [
            {
                "name": "test_param",
                "description": "Test parameter",
                "default": "default_value",
            }
        ],
        "objects": [
            {
                "type": "user",
                "email": "test+{test_param}@mavenclinic.com",
                "password": "simpleisawesome1*",
                "first_name": "{test_param}_first_name",
                "last_name": "{test_param}_last_name",
            }
        ],
    }


def test_parameterized_fixture_override_defaults(
    data_admin_app, parameterized_fixture_data
):
    """Test that provided values override defaults"""
    with data_admin_app.test_request_context():
        # Create form data with all parameters
        form_data = {
            "fixture_name": "test_fixture",
            "param_test_param": "override_value",
        }

        # Extract parameters and apply substitution
        parameters = extract_parameters_from_form(form_data, parameterized_fixture_data)
        specs = substitute_parameters(parameterized_fixture_data["objects"], parameters)

        # Verify the substituted values use the provided override
        assert specs[0]["email"] == "test+override_value@mavenclinic.com"
        assert specs[0]["first_name"] == "override_value_first_name"
        assert specs[0]["last_name"] == "override_value_last_name"


def test_parameterized_fixture_integration(
    data_admin_app, parameterized_fixture_data, monkeypatch
):
    """Test the complete flow through the Flask view"""
    with data_admin_app.test_request_context():
        # Mock the fixture file reading
        def mock_open(*args, **kwargs):
            class MockFile:
                def read(self):
                    return json.dumps(parameterized_fixture_data)

            return MockFile()

        monkeypatch.setattr("builtins.open", mock_open)

        # Make the request
        response = data_admin_app.test_client().post(
            "/data-admin/upload/spec",
            data={
                "fixture_name": "test_fixture",
                "param_test_param": "integration_test",
            },
        )

        # Verify the response
        assert response.status_code == 302  # Redirect after successful creation
