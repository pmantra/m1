import datetime
import os
from unittest.mock import MagicMock, patch

import factory
import pytest

from admin import login, views
from admin.blueprints import enterprise
from eligibility.pytests import factories as e9y_factories
from pytests import factories


class EnterpriseSetupFormFactory(factory.Factory):
    class Meta:
        model = dict

    user_id = factory.Sequence(lambda n: n + 1)
    member_id = factory.Sequence(lambda n: n + 1)
    track_name = ""
    association_source = "e9y"
    life_event_date = ""
    life_event_type = ""
    confirmation = True
    verification_creator = ""
    zendesk_id = ""


# This change is to overcome the following issue after flask version upgrade
# The setup method 'register_blueprint' can no longer be called on the application.
# It has already handled its first request, any changes will not be applied consistently.
@pytest.fixture
def app_with_blueprints(mock_queue, backend):
    """An application instance for local testing mimicking the global app fixture."""
    from admin.factory import setup_flask_app

    app = setup_flask_app()
    app.testing = True
    app.env = "testing"
    app.template_folder = "templates"

    app.config["SERVER_NAME"] = f"local-test-{os.uname().nodename}"
    # register blueprints logic
    # app.config["LOGIN_DISABLED"] = True
    app.secret_key = "keep-it-secret-keep-it-safe"
    views.init_admin(app)
    login.init_login(app)
    with patch("utils.cache.RedisLock"):
        with app.app_context():
            return app


def test_setup_no_track_selection(verification_service, app_with_blueprints):
    # Given
    user = factories.DefaultUserFactory.create()
    organization = factories.OrganizationFactory.create()
    member = e9y_factories.EligibilityMemberFactory.create(
        organization_id=organization.id
    )
    verification_service.e9y.grpc.member_id_search.return_value = member
    verification_service.e9y.grpc.get_verification.return_value = None
    verification_service.e9y.grpc.create_verification.return_value = (
        e9y_factories.VerificationFactory.create(),
        None,
    )
    form_input = EnterpriseSetupFormFactory.create(
        user_id=user.id,
        member_id=member.id,
    )
    # When
    with app_with_blueprints.test_request_context(data=form_input):
        with patch("flask_login.utils._get_user") as current_user:
            flask_user = MagicMock()
            flask_user.id = 1
            current_user.return_value = flask_user
            enterprise.onboard_member()
            association = verification_service.employees.get_by_user_id(user_id=user.id)
            # Then
            assert association is not None


def test_setup_bad_member_id(verification_service, app_with_blueprints):
    # Given
    user = factories.DefaultUserFactory.create()
    verification_service.e9y.grpc.member_id_search.return_value = None
    form_input = EnterpriseSetupFormFactory.create(
        user_id=user.id,
        member_id=1,
        track_name="",
        association_source="e9y",
    )
    # When
    with app_with_blueprints.test_request_context(data=form_input):
        with patch("flask_login.utils._get_user") as current_user:
            flask_user = MagicMock()
            flask_user.id = 1
            current_user.return_value = flask_user
            enterprise.onboard_member()
            association = verification_service.employees.get_by_user_id(user_id=user.id)
            # Then
            assert association == []


def test_setup_pregnancy_with_due_date(verification_service, app_with_blueprints):
    # Given
    user = factories.DefaultUserFactory.create()
    target_track = "pregnancy"
    organization = factories.OrganizationFactory.create(allowed_tracks=[target_track])
    due_date = datetime.date.today() + datetime.timedelta(days=90)
    member = e9y_factories.EligibilityMemberFactory.create(
        organization_id=organization.id
    )
    verification_service.e9y.grpc.member_id_search.return_value = member
    verification_service.e9y.grpc.get_verification.return_value = None

    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=organization.id,
        active_effective_range=True,
    )

    verification_service.e9y.grpc.create_verification.return_value = verification
    form_input = EnterpriseSetupFormFactory.create(
        user_id=user.id,
        member_id=member.id,
        track_name=target_track,
        association_source="e9y",
        life_event_date=due_date.isoformat(),
        life_event_type="due_date",
    )

    # When
    with app_with_blueprints.test_request_context(data=form_input):
        with patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
            return_value=verification,
        ), patch("eligibility.verify_member", return_value=verification,), patch(
            "flask_login.utils._get_user"
        ) as current_user:
            flask_user = MagicMock()
            flask_user.id = 1
            current_user.return_value = flask_user
            enterprise.onboard_member()
            # Then
            assert user.active_tracks[0].modified_by == "1"
            assert user.active_tracks[0].name == target_track


def test_setup_postpartum_with_child_birthday(
    verification_service, app_with_blueprints
):
    # Given
    user = factories.DefaultUserFactory.create()
    target_track = "postpartum"
    organization = factories.OrganizationFactory.create(allowed_tracks=[target_track])
    birthday = datetime.date.today() - datetime.timedelta(days=90)
    member = e9y_factories.EligibilityMemberFactory.create(
        organization_id=organization.id
    )
    verification_service.e9y.grpc.get_verification.return_value = None

    verification = e9y_factories.VerificationFactory.create(
        user_id=user.id,
        organization_id=organization.id,
        active_effective_range=True,
    )

    verification_service.e9y.grpc.create_verification.return_value = verification

    verification_service.e9y.grpc.member_id_search.return_value = member
    form_input = EnterpriseSetupFormFactory.create(
        user_id=user.id,
        member_id=member.id,
        track_name=target_track,
        association_source="e9y",
        life_event_date=birthday.isoformat(),
        life_event_type="child_birthday",
    )

    # When
    with app_with_blueprints.test_request_context(data=form_input):
        with patch(
            "eligibility.service.EnterpriseVerificationService.get_verification_for_user_and_org",
            return_value=verification,
        ), patch("eligibility.verify_member", return_value=verification,), patch(
            "flask_login.utils._get_user"
        ) as current_user:
            flask_user = MagicMock()
            flask_user.id = 1
            current_user.return_value = flask_user
            enterprise.onboard_member()
            # Then
            assert user.active_tracks[0].modified_by == "1"
            assert user.active_tracks[0].name == target_track
