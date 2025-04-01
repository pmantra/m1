import os
from unittest.mock import patch

import pytest

from eligibility.utils.e9y_test_utils import is_non_prod


@pytest.mark.parametrize(
    argnames="environment,expected",
    argvalues=[
        ("prod", False),
        ("production", False),
        ("qa1", True),
        ("qa2", True),
        ("staging", True),
        ("development", True),
        ("local", True),
        ("custom", True),
    ],
    ids=["prod1", "prod2", "qa1", "qa2", "staging", "development", "local", "custom"],
)
def test_local_environment(environment, expected):
    with patch.dict(os.environ, {"ENVIRONMENT": environment}):
        assert is_non_prod() == expected
