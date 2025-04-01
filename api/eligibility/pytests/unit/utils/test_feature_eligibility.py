from unittest import mock

import pytest

from eligibility.e9y import model as e9y_model
from eligibility.utils import feature_eligibility


@pytest.mark.parametrize(
    argnames="feature_ids,filtered_ids,expected_ids",
    argvalues=[
        ([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], [1, 2, 3, 4, 5]),
        ([1, 2, 3, 4, 5], [1, 3, 5], [1, 3, 5]),
        ([1, 3, 5], [1, 2, 3, 4, 5], [1, 3, 5]),
        ([1, 2, 3, 4, 5], [], []),
    ],
    ids=[
        "exact_match",
        "sub_set",
        "super_set",
        "no_match",
    ],
)
def test_filter_ineligible_features(feature_ids, filtered_ids, expected_ids):
    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_eligible_features_for_user"
    ) as mock_get_eligible_features_for_user:
        # Given
        mock_get_eligible_features_for_user.return_value = filtered_ids
        # When
        filtered_feature_ids = feature_eligibility.filter_ineligible_features(
            user_id=1,
            feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
            feature_ids=feature_ids,
        )
        # Then
        assert filtered_feature_ids == expected_ids


def test_filter_ineligible_features_no_population():
    test_feature_ids = [1, 2, 3, 4, 5]

    with mock.patch(
        "eligibility.service.EnterpriseVerificationService.get_eligible_features_for_user"
    ) as mock_get_eligible_features_for_user:
        # Given
        mock_get_eligible_features_for_user.return_value = None
        # When
        filtered_feature_ids = feature_eligibility.filter_ineligible_features(
            user_id=1,
            feature_type=e9y_model.FeatureTypes.TRACK_FEATURE,
            feature_ids=test_feature_ids,
        )
        # Then
        assert filtered_feature_ids == test_feature_ids
