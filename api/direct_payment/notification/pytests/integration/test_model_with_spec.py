import os

import pytest
import yaml

from direct_payment.notification.models import (
    EventName,
    NotificationEventPayload,
    NotificationPayload,
)


@pytest.fixture
def openapi_yaml_dict_schemas():
    with open(
        # need this to have this work on the build server
        os.path.dirname(os.path.abspath(__file__)) + "/../../../openapi.yaml",
        "r",
    ) as stream:
        yaml_dict = yaml.safe_load(stream)
        return yaml_dict["components"]["schemas"]


@pytest.fixture
def notif_payload_schema(openapi_yaml_dict_schemas):
    return openapi_yaml_dict_schemas["NotificationPayload"]


@pytest.fixture
def notif_event_payload_schema(openapi_yaml_dict_schemas):
    return openapi_yaml_dict_schemas["NotificationEventPayload"]


@pytest.fixture()
def event_name_keys():
    return {
        v.value for v in NotificationEventPayload.EVENT_NAME_PROPERTIES_MAPPING.keys()
    }


class TestModelAndSpec:
    def test_notification_payload_schema(self, notif_payload_schema):
        # the data class properties match the yaml spec properties
        assert (
            NotificationPayload.__annotations__.keys()
            == notif_payload_schema["properties"].keys()
        )

    def test_notification_event_payload_schema(self, notif_event_payload_schema):
        assert (
            NotificationEventPayload.__annotations__.keys()
            == notif_event_payload_schema["properties"].keys()
        )
        event_name_keys = {
            v.value
            for v in NotificationEventPayload.EVENT_NAME_PROPERTIES_MAPPING.keys()
        }
        assert event_name_keys == set(
            notif_event_payload_schema["properties"]["event_name"]["enum"]
        )

    def test_all_event_names_mapped(self, notif_event_payload_schema, event_name_keys):
        assert event_name_keys == set(
            notif_event_payload_schema["properties"]["event_name"]["enum"]
        )

    def test_model_and_open_api_spec(
        self, openapi_yaml_dict_schemas, notif_payload_schema, event_name_keys
    ):

        # check that the different kinds of payloads are correctly mapped
        ref_strs = notif_payload_schema["properties"]["notification_event_payload"][
            "anyOf"
        ]
        refs = {ref["$ref"].split("/")[-1] for ref in ref_strs}

        # find the class that matches the schema and confirm that it lines up
        found_event_names = set()
        for ref in refs:
            # load the actual payload schmea
            mmb_payload_schema = openapi_yaml_dict_schemas[ref]
            mmb_schema_props = mmb_payload_schema["properties"]
            # the event name in the payload schema is the key to load the correct class.
            event_name = mmb_schema_props["event_name"]["enum"][0]
            found_event_names.add(event_name)
            class_ = NotificationEventPayload.EVENT_NAME_PROPERTIES_MAPPING[
                EventName(event_name)
            ]
            assert (
                class_.__annotations__.keys()
                == mmb_schema_props["event_properties"]["properties"].keys()
            )
        # 1 to 1 match between the mapped classes and the spec reference
        assert found_event_names == event_name_keys
