import json
from typing import Optional, TypedDict

from flask import request

from common.services.api import InternalServiceResource
from utils.log import logger
from wallet.repository.reimbursement_organization_setting import (
    ReimbursementOrg,
    ReimbursementOrganizationSettingsRepository,
)

log = logger(__name__)

DEFAULT_LIMIT: int = 50
DEFAULT_OFFSET: int = 0


def string_to_dict(string_input: Optional[str]) -> Optional[dict]:
    if string_input is None:
        return None

    try:
        # parse as JSON
        result = json.loads(string_input)
        return result if isinstance(result, dict) else None
    except json.JSONDecodeError:
        # Not valid JSON
        return None


class ReimbursementOrgSettingsResource(InternalServiceResource):
    def get(self) -> tuple:
        args = request.args
        request_filter: Optional[str] = args.get("filter")

        request_filter_dict: Optional[dict] = string_to_dict(request_filter)
        ros_id_filter: list[int] = []

        if request_filter_dict is None:
            name_filter = request_filter
        else:
            name_filter = request_filter_dict.get("name")
            ros_id_filter = request_filter_dict.get("ros_id", [])

        limit: int = int(args.get("limit", "-1"))
        offset: int = int(args.get("offset", "-1"))
        log.info(
            "Received ReimbursementOrgSettings List request",
            org_name=name_filter,
            ros_ids=ros_id_filter,
            limit=limit,
            offset=offset,
        )

        if limit < 0:
            limit = DEFAULT_LIMIT
        if offset < 0:
            offset = DEFAULT_OFFSET

        reimbursement_org_setting_repo = ReimbursementOrganizationSettingsRepository()

        reimbursement_orgs = reimbursement_org_setting_repo.get_reimbursement_orgs(
            name_filter=name_filter,
            ros_id_filter=ros_id_filter,
            limit=limit,
            offset=offset,
        )
        reimbursement_orgs_count = (
            reimbursement_org_setting_repo.get_reimbursement_org_count(
                name_filter=name_filter, ros_id_filter=ros_id_filter
            )
        )

        log.info(
            "Returning ReimbursementOrgSettings List results",
            num_orgs=reimbursement_orgs_count,
        )

        return (
            ReimbursementOrgSettingsGetResponse(
                reimbursement_orgs=reimbursement_orgs,
                total_results=reimbursement_orgs_count,
            ),
            200,
        )


class ReimbursementOrgSettingsGetResponse(TypedDict):
    reimbursement_orgs: list[ReimbursementOrg]
    total_results: int
