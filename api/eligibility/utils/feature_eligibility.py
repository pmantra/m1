from typing import List

from eligibility import service as e9y_svc


def filter_ineligible_features(
    user_id: int,
    feature_type: int,
    feature_ids: List[int],
) -> List[int]:
    svc = e9y_svc.EnterpriseVerificationService()
    eligible_feature_ids = svc.get_eligible_features_for_user(
        user_id=user_id, feature_type=feature_type
    )
    if eligible_feature_ids is None:
        return feature_ids
    return list(set(feature_ids) & set(eligible_feature_ids))
