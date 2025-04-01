from unittest.mock import patch

from common.document_mapper.helpers import (
    partial_ratio,
    receipt_validation_ops_view_enabled,
)


def test_receipt_validation_ops_view_enabled():
    with patch("maven.feature_flags.str_variation") as mock_flag:
        mock_flag.return_value = "CCRM"
        assert (
            receipt_validation_ops_view_enabled("CCRM New York Manhattan Park Avenue")
            == True
        )


def test_receipt_validation_ops_view_enabled_below_threshold():
    with patch("maven.feature_flags.str_variation") as mock_flag:
        mock_flag.return_value = "Spring Fertility"
        assert receipt_validation_ops_view_enabled("Spring Medical") == False


def test_partial_ratio():
    # Exact matches
    assert partial_ratio("CCRM", "CCRM") == 100.0

    # Substring matches
    assert partial_ratio("CCRM", "CCRM Manhattan") == 100.0
    assert partial_ratio("Spring Fertility", "Spring Fertility NYC") == 100.0
    assert partial_ratio("CCRM Manhattan", "CCRM") == 100.0
    assert partial_ratio("Spring Fertility NYC", "Spring Fertility") == 100.0

    # Non-matches
    assert partial_ratio("CCRM", "Spring") < 80.0
    assert partial_ratio("Sprng", "Spring") >= 80.0
    # Test a clear non-match that will be below 80%
    assert partial_ratio("Spring Fertility", "Spring Medical") < 80.0
    assert partial_ratio("Spring Fertility", "Sprng Fertlty") > 80.0
