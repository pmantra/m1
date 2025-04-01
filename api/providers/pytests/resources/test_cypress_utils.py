from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from appointments.models.schedule import Schedule
from authn.models.user import User
from authz.models.roles import _role_id_cache
from common.constants import Environment
from models.products import Product
from models.profiles import MemberPractitionerAssociation
from providers.domain.model import Provider


@pytest.fixture()
def cypress_user(factories):
    return factories.EnterpriseUserFactory.create()


@pytest.fixture(autouse=True)
def clear_role_cache():
    """
    The "default_role()" function uses a variable to cache roles, which will lead
    to errors in this testing environment as role_ids change between tests.

    Clearing this cache between tests will solve this issue
    """
    _role_id_cache.clear()


class TestPostTestProvider:
    def test_create_test_provider__404_in_production(
        self, db, client, api_helpers, cypress_user
    ):
        """
        Tests that POST /cypress_utils/providers does not work in production
        """
        with patch("common.constants.Environment.current") as env_mock:
            env_mock.return_value = Environment.PRODUCTION
            res = client.post(
                "/api/v1/cypress_utils/providers",
                headers=api_helpers.json_headers(cypress_user),
                json={},
            )

        assert res.status_code == 404

    def test_create_test_provider(
        self, db, client, api_helpers, factories, cypress_user
    ):
        """
        Tests that providers for cypress tests are created when calling the POST
        /providers/cypress_utils endpoint
        """
        factories.CancellationPolicyFactory.create(name="moderate")

        res = client.post(
            "/api/v1/cypress_utils/providers",
            headers=api_helpers.json_headers(cypress_user),
            json={},
        )

        assert res.status_code == 200
        data = res.json

        created_provider_id = data["id"]
        created_provider = (
            db.session.query(Provider).filter_by(user_id=created_provider_id).one()
        )
        # Check default parameters
        assert created_provider.state.name == "New York"
        assert created_provider.certified_states[0].name == "New York"
        assert created_provider.vertical.name == "Care Advocate"
        assert created_provider.timezone == "America/New_York"

        # create availability for the practitioner
        now = datetime.utcnow()
        tomorrow = now + timedelta(hours=24)
        factories.ScheduleEventFactory.create(
            schedule=created_provider.user.schedule,
            starts_at=tomorrow - timedelta(hours=2),
            ends_at=tomorrow + timedelta(hours=2),
        )

        # Test that the practitioner has availability
        query_str = {
            "starts_at": tomorrow.isoformat(),
            "ends_at": (tomorrow + timedelta(hours=1)).isoformat(),
        }
        res = client.get(
            f"/api/v1/products/{created_provider.user.default_product.id}/availability",
            headers=api_helpers.json_headers(cypress_user),
            query_string=query_str,
        )
        availabilities = res.json["data"]

        assert len(availabilities) >= 1

    def test_create_test_provider__accepts_state_name(
        self, db, client, api_helpers, factories, cypress_user
    ):
        """
        Tests that providers for cypress tests are created with the correct state when passed as a param
        """
        factories.CancellationPolicyFactory.create(name="moderate")

        _role_id_cache.clear()
        state_name = "California"
        factories.StateFactory.create(
            name=state_name,
            abbreviation="CA",
        )

        res = client.post(
            "/api/v1/cypress_utils/providers",
            headers=api_helpers.json_headers(cypress_user),
            json={"state_name": state_name},
        )

        assert res.status_code == 200
        data = res.json

        created_provider_id = data["id"]
        created_provider = (
            db.session.query(Provider).filter_by(user_id=created_provider_id).one()
        )

        assert created_provider.state.name == state_name
        assert created_provider.certified_states[0].name == state_name

    def test_create_test_provider__accepts_vertical_name(
        self, db, client, api_helpers, factories, cypress_user
    ):
        """
        Tests that providers for cypress tests are created with the correct vertical when passed as a param
        """
        factories.CancellationPolicyFactory.create(name="moderate")

        vertical_name = "Wellness Coach"
        factories.VerticalFactory.create(
            name=vertical_name,
        )

        res = client.post(
            "/api/v1/cypress_utils/providers",
            headers=api_helpers.json_headers(cypress_user),
            json={"vertical_name": vertical_name},
        )

        assert res.status_code == 200
        data = res.json

        created_provider_id = data["id"]
        created_provider = (
            db.session.query(Provider).filter_by(user_id=created_provider_id).one()
        )

        assert created_provider.vertical.name == vertical_name

    def test_create_test_provider__accepts_timezone(
        self, db, client, api_helpers, factories, cypress_user
    ):
        """
        Tests that providers for cypress tests are created with the correct timezone when passed as a param
        """
        factories.CancellationPolicyFactory.create(name="moderate")

        timezone = "UTC"

        res = client.post(
            "/api/v1/cypress_utils/providers",
            headers=api_helpers.json_headers(cypress_user),
            json={"timezone": timezone},
        )

        assert res.status_code == 200
        data = res.json

        created_provider_id = data["id"]
        created_provider = (
            db.session.query(Provider).filter_by(user_id=created_provider_id).one()
        )

        assert created_provider.timezone == timezone


class TestDeleteProvider:
    def test_delete_test_provider__404_in_production(
        self,
        db,
        client,
        api_helpers,
        cypress_user,
    ):
        """
        Tests that DELETE /cypress_utils/providers/:id does not work in production
        """
        provider_id = 9999
        with patch("common.constants.Environment.current") as env_mock:
            env_mock.return_value = Environment.PRODUCTION
            res = client.delete(
                f"/api/v1/cypress_utils/providers/{provider_id}",
                headers=api_helpers.json_headers(cypress_user),
            )

        assert res.status_code == 404

    def test_delete_test_provider(
        self, db, client, api_helpers, cypress_user, factories
    ):
        """
        Tests that deleting a cypress test provider works
        """
        factories.CancellationPolicyFactory.create(name="moderate")
        res = client.post(
            "/api/v1/cypress_utils/providers",
            headers=api_helpers.json_headers(cypress_user),
            json={},
        )
        provider_id = res.json["id"]

        provider = (
            db.session.query(Provider).filter_by(user_id=provider_id).one_or_none()
        )
        assert provider is not None

        # Delete provider by id
        res = client.delete(
            f"/api/v1/cypress_utils/providers/{provider_id}",
            headers=api_helpers.json_headers(cypress_user),
        )

        deleted_provider = (
            db.session.query(Provider).filter_by(user_id=provider_id).one_or_none()
        )
        deleted_user = db.session.query(User).filter_by(id=provider_id).one_or_none()

        deleted_mpas = (
            db.session.query(MemberPractitionerAssociation)
            .filter_by(practitioner_id=provider_id)
            .all()
        )
        deleted_products = (
            db.session.query(Product).filter_by(user_id=provider_id).all()
        )
        deleted_schedules = (
            db.session.query(Schedule).filter_by(user_id=provider_id).all()
        )

        assert deleted_provider is None
        assert deleted_user is None
        assert len(deleted_mpas) == 0
        assert len(deleted_products) == 0
        assert len(deleted_schedules) == 0
