from common.services.api import InternalServiceResource
from wallet.repository.reimbursement_organization_setting import (
    ReimbursementOrganizationSettingsRepository,
    ReimbursementOrgSettingNameGetResponse,
)


class ReimbursementOrgSettingNameResource(InternalServiceResource):
    def get(self, ros_id: int) -> tuple[ReimbursementOrgSettingNameGetResponse, int]:
        reimbursement_org_setting_repo = ReimbursementOrganizationSettingsRepository()
        return (
            reimbursement_org_setting_repo.get_reimbursement_org_setting_name(ros_id),
            200,
        )
