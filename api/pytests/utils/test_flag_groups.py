from __future__ import annotations

import pytest

from utils.flag_groups import AllowedFlagTypes, FlagNameGroup


def test_FlagNameGroup_custom_join():
    TEST_GROUP = FlagNameGroup(
        group_type=AllowedFlagTypes.RELEASE,
        namespace="test_group",
        join_char="_",
    )
    assert TEST_GROUP._namespace == "test_group"
    assert TEST_GROUP.flag_names() == []

    with pytest.raises(AttributeError):
        TEST_GROUP.TEST_FLAG

    TEST_GROUP.TEST_FLAG = "test_flag"

    assert TEST_GROUP.TEST_FLAG == "release_test_group_test_flag"
    assert TEST_GROUP.flag_names() == ["release_test_group_test_flag"]

    with pytest.raises(AttributeError):
        TEST_GROUP.NOT_SET


def test_FlagNameGroup_no_namespace():
    with pytest.raises(ValueError):
        FlagNameGroup(
            group_type="",
            namespace=None,
        )
    with pytest.raises(ValueError):
        FlagNameGroup(
            group_type="",
            namespace="",
        )


@pytest.mark.parametrize(
    ("namespace", "join_char"),
    [
        ("UPPERNOTALLOWED", None),
        ("UNDERSCORE_NOT_ALLOWED", None),
        ("$*specials-not-allowed", None),
        ("mixed_seperator_not_allowed", "-"),
    ],
)
def test_FlagNameGroup_invalid_namespace(
    namespace,
    join_char,
):
    with pytest.raises(ValueError):
        FlagNameGroup(
            group_type="",
            namespace=namespace,
            join_char=join_char,
        )


def test_FlagNameGroup_invalid_group():
    with pytest.raises(ValueError):
        FlagNameGroup(
            group_type=None,
            namespace="ns",
        )
    with pytest.raises(ValueError):
        FlagNameGroup(
            group_type="FOO BAR BAZ",
            namespace="ns",
        )


def test_FlagNameGroup_default_join():
    TEST_GROUP = FlagNameGroup(
        group_type="",
        namespace="test-group",
    )
    assert TEST_GROUP._namespace == "test-group"
    assert TEST_GROUP.flag_names() == []

    TEST_GROUP.TEST_FLAG = "test-flag"
    assert TEST_GROUP.TEST_FLAG == "test-group-test-flag"
    assert TEST_GROUP.flag_names() == ["test-group-test-flag"]


def test_FlagNameGroup_group_type():
    TEST_GROUP = FlagNameGroup(
        group_type="",
        namespace="test-group",
    )
    assert TEST_GROUP._namespace == "test-group"
    assert TEST_GROUP.flag_names() == []

    TEST_GROUP.TEST_FLAG = "test-flag"
    assert TEST_GROUP.TEST_FLAG == "test-group-test-flag"
    assert TEST_GROUP.flag_names() == ["test-group-test-flag"]
