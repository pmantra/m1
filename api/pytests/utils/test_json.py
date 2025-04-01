import json

import pytest

from utils.json import json_hook_restore_int_keys


@pytest.mark.parametrize(
    ["input", "expected"],
    [
        ({"key": "value"}, {"key": "value"}),
        ({123: "value"}, {123: "value"}),
        # Converting to int is the expected behavior.
        # see note on json_hook_restore_int_keys for details.
        ({"123": "value"}, {123: "value"}),
        # arbitrary nested dicts are supported
        (
            {"123": {"123": {"123": {"123": "value"}}}},
            {123: {123: {123: {123: "value"}}}},
        ),
        # value types are not modified
        ({"foo": "456"}, {"foo": "456"}),
        ({123: "456"}, {123: "456"}),
        ({123: 456}, {123: 456}),
    ],
)
def test_json_hook_restore_int_keys(input, expected):
    json_str = json.dumps(input)

    assert json.loads(json_str, object_hook=json_hook_restore_int_keys) == expected
