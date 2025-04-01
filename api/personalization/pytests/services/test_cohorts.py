from unittest import mock

from health.services.health_profile_service import HealthProfileService
from personalization.services.cohorts import PersonalizationCohortsService


def test_cohorts_service(factories):
    user = factories.EnterpriseUserFactory.create()
    health_profile_service = HealthProfileService(user)
    health_profile_service.set_json_field("sex_at_birth", "Male")
    cohorts_service = PersonalizationCohortsService(user)
    all_cohorts = cohorts_service.get_all()
    assert all_cohorts["sex_at_birth"] == "male"
    assert all_cohorts["targeted_for_ovulation_tracking"] == False
    assert all_cohorts["targeted_for_cycle_tracking"] == False
    assert all_cohorts["targeted_for_ovulation_medication"] == False


@mock.patch("personalization.services.cohorts.log")
@mock.patch("health.services.member_health_cohorts_service.HealthProfileService")
def test_cohorts_service_with_error(mock_health_profile, mock_log, factories):
    user = factories.EnterpriseUserFactory.create()
    mock_health_profile.return_value.get_sex_at_birth.side_effect = Exception
    cohorts_service = PersonalizationCohortsService(user)
    all_cohorts = cohorts_service.get_all()
    assert all_cohorts["sex_at_birth"] is None
    mock_log.warning.assert_called_once_with(
        "Exception getting cohort value, using default instead",
        cohort="sex_at_birth",
        exc_info=True,
    )
