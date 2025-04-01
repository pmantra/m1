import pytest
import yaml
from maven import feature_flags

from braze import WHITELIST
from braze.pytests.factories import (
    ConnectedContentFieldFactory,
    ResourceConnectedContentFactory,
    ResourceConnectedContentTrackPhaseFactory,
)
from models.images import Image


@pytest.fixture
def launch_darkly_test_data():
    with feature_flags.test_data() as td:
        yield td


@pytest.fixture
def braze_ips():
    with WHITELIST.open() as stream:
        yaml_data = yaml.safe_load(stream)
        braze_ips = yaml_data["braze"]["whitelist-ips"]
        return braze_ips


@pytest.fixture
def resource_1(factories, enterprise_user):
    resource_1 = factories.ResourceFactory()
    resource_1.connected_content_type = "email1"
    resource_1.image = Image(filetype="jpg", storage_key="image")
    resource_1.body = "resource body 1"
    resource_1.title = "resource title 1"

    # Specify connected content fields for this resource
    resource_connected_content = ResourceConnectedContentFactory()
    connected_content_field = ConnectedContentFieldFactory()
    connected_content_field.name = "blerp"
    resource_connected_content.field = connected_content_field
    resource_connected_content.value = "blah"
    resource_1.connected_content_fields = [resource_connected_content]

    # Build track phase for resource_1
    resource_track_phase = ResourceConnectedContentTrackPhaseFactory()
    resource_track_phase.resource_id = resource_1.id
    resource_track_phase.track_name = enterprise_user.active_tracks[0].name
    resource_track_phase.phase_name = (
        enterprise_user.current_member_track.current_phase.name
    )

    return resource_1


@pytest.fixture
def resource_2(factories, enterprise_user):
    resource_2 = factories.ResourceFactory()
    resource_2.connected_content_type = "email2"
    resource_2.image = Image(filetype="jpg", storage_key="image2")
    resource_2.body = "resource body 2"
    resource_2.title = "resource title 2"

    # Build track phase for resource_2
    resource_track_phase = ResourceConnectedContentTrackPhaseFactory()
    resource_track_phase.resource_id = resource_2.id
    resource_track_phase.track_name = enterprise_user.active_tracks[0].name
    resource_track_phase.phase_name = (
        enterprise_user.current_member_track.current_phase.name
    )

    return resource_2


@pytest.fixture
def resource_3(factories, enterprise_user):
    resource_3 = factories.ResourceFactory()
    resource_3.connected_content_type = "email3"
    resource_3.body = "resource body 3"
    resource_3.title = "resource title 3"

    # Build track phase for resource_3
    resource_track_phase = ResourceConnectedContentTrackPhaseFactory()
    resource_track_phase.resource_id = resource_3.id
    resource_track_phase.track_name = enterprise_user.active_tracks[0].name
    resource_track_phase.phase_name = (
        enterprise_user.current_member_track.current_phase.name
    )

    return resource_3


@pytest.fixture
def mock_braze_user_profile():
    return {
        "created_at": "2020-07-10T15:00:00.000Z",
        "external_id": "123",
        "user_aliases": [{"alias_name": "user_123", "alias_label": "some_label"}],
        "braze_id": "5fbd99bac125ca40511f2cb1",
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "example@braze.com",
        "country": "US",
        "language": "en",
        "time_zone": "Eastern Time (US & Canada)",
        "email_subscribe": "subscribed",
        "custom_attributes": {
            "Registration date": "2021-06-28T15:00:00.000Z",
            "state": "NY",
            "onboarding_state": "assessments",
        },
        "custom_events": [
            {
                "name": "password_reset",
                "first": "2021-06-28T17:02:43.032Z",
                "last": "2021-06-28T17:02:43.032Z",
                "count": 1,
            },
        ],
    }
