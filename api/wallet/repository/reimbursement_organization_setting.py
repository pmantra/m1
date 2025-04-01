from __future__ import annotations

from typing import Optional, TypedDict

import ddtrace.ext
import sqlalchemy

from storage import connection
from utils.log import logger

trace_wrapper = ddtrace.tracer.wrap(span_type=ddtrace.ext.SpanTypes.SQL)
log = logger(__name__)


class ReimbursementOrg(TypedDict):
    reimbursement_org_settings_id: str
    name: Optional[str]


class ReimbursementOrgSettingNameGetResponse(TypedDict):
    org_setting_name: str | None
    error_message: str | None


class ReimbursementOrganizationSettingsRepository:
    def __init__(self, session: Optional[sqlalchemy.orm.scoping.ScopedSession] = None):
        self.session = session or connection.db.session

    @trace_wrapper
    def get_reimbursement_orgs(
        self,
        name_filter: Optional[str],
        ros_id_filter: list[int],
        limit: int,
        offset: int,
    ) -> list[ReimbursementOrg]:
        lower_name_filter = "" if name_filter is None else name_filter.lower()

        query_str = """
            SELECT r.id AS reimbursement_org_settings_id, COALESCE(r.name, o.name) AS name
            FROM reimbursement_organization_settings r LEFT JOIN organization o ON o.id = r.organization_id
            WHERE LOWER(TRIM(COALESCE(r.name, o.name))) LIKE CONCAT('%', TRIM(:lower_name_filter), '%') COLLATE utf8mb4_bin 
        """

        params = {
            "lower_name_filter": lower_name_filter,
            "offset": offset,
            "limit": limit,
        }

        # If ros_id_filter is not empty, add the filter condition
        if ros_id_filter:
            query_str += " AND r.id IN :ros_id_filter"
            # Convert list to tuple for SQL compatibility
            params["ros_id_filter"] = tuple(ros_id_filter)

        query_str += " ORDER BY r.created_at LIMIT :limit OFFSET :offset;"

        reimbursement_orgs = self.session.execute(query_str, params).fetchall()

        return [
            ReimbursementOrg(
                reimbursement_org_settings_id=str(reimbursement_org[0]),
                name=reimbursement_org[1],
            )
            for reimbursement_org in reimbursement_orgs
        ]

    @trace_wrapper
    def get_reimbursement_org_count(
        self, name_filter: Optional[str], ros_id_filter: list[int]
    ) -> int:
        lower_name_filter = "" if name_filter is None else name_filter.lower()

        query_str = """
             SELECT COUNT(*) FROM reimbursement_organization_settings r LEFT JOIN organization o ON o.id = r.organization_id
             WHERE LOWER(TRIM(COALESCE(r.name, o.name))) LIKE CONCAT('%', TRIM(:lower_name_filter), '%') COLLATE utf8mb4_bin
       """

        params = {
            "lower_name_filter": lower_name_filter,
        }

        # If ros_id_filter is not empty, add the filter condition
        if ros_id_filter:
            query_str += " AND r.id IN :ros_id_filter"
            # Convert list to tuple for SQL compatibility
            params["ros_id_filter"] = tuple(ros_id_filter)

        query_str += ";"

        return self.session.execute(query_str, params).scalar()

    @trace_wrapper
    def get_reimbursement_org_setting_name(
        self, ros_id: int
    ) -> ReimbursementOrgSettingNameGetResponse:
        get_name_query = """
            SELECT COALESCE(o.display_name, o.name) 
            FROM reimbursement_organization_settings r 
            LEFT JOIN organization o ON o.id = r.organization_id
            WHERE r.id = :ros_id
        """

        result = self.session.execute(
            get_name_query,
            {
                "ros_id": ros_id,
            },
        ).fetchone()

        if result is None:
            return ReimbursementOrgSettingNameGetResponse(
                org_setting_name=None,
                error_message="Cannot find the reimbursement organization setting",
            )

        if len(result) != 1:
            return ReimbursementOrgSettingNameGetResponse(
                org_setting_name=None,
                error_message="Error in querying for org name",
            )

        org_setting_name = result[0]
        if org_setting_name is None:
            return ReimbursementOrgSettingNameGetResponse(
                org_setting_name=None,
                error_message="Cannot find the reimbursement org name in mono",
            )
        else:
            return ReimbursementOrgSettingNameGetResponse(
                org_setting_name=org_setting_name,
                error_message=None,
            )
