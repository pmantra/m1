from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import List, Tuple

import ddtrace

SERVICE_NS_TAG = "service_ns"
TEAM_NS_TAG = "team_ns"
CALLER_TAG = "caller"
TRACKING_ID = "tracking_id"
USER_ID_TAG = "maven.user_id"
PRIORITY_TAG = "priority"
WORKFLOW_TAG = "workflow"


class APIPriority(str, enum.Enum):
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    NONE = "none"


@dataclass
class APIMetadata:
    service_ns: str = "none"
    priority: APIPriority = APIPriority.NONE
    workflows: List[str] = field(default_factory=list)

    @property
    def team_ns(self) -> str:
        if self.service_ns in service_ns_team_mapper:
            return service_ns_team_mapper[self.service_ns]
        # ideally this should not happen, each service_ns should map to a team owner
        return "none"

    def get_values(self) -> Tuple[str, str, str, List[str]]:
        return self.service_ns, self.team_ns, self.priority.value, self.workflows


# will keep updating
# intentionally put everything in lowercase
# NOTE that here we use the simplest regex rule to match anything for the dynamic content in url
# we may consider refactoring it if there is a need for more strict check
# NOTE: endpoint_service mappers are sorted in reverse order to ensure stricter matching
data_admin_endpoint_service_ns_mapper = {
    "/data-admin/": APIMetadata("data-admin"),
    "/data-admin/cross_site_login": APIMetadata("data-admin"),
    "/data-admin/reset/database": APIMetadata("data-admin"),
    "/data-admin/publish/spec": APIMetadata("data-admin"),
    "/data-admin/upload/spec": APIMetadata("data-admin"),
    "/data-admin/actions/run_task": APIMetadata("data-admin"),
}
admin_endpoint_service_ns_mapper = {
    "/admin/walletuserinvite/new/": APIMetadata("wallet"),
    "/admin/walletuserinvite/export/(.+?)/": APIMetadata("wallet"),
    "/admin/walletuserinvite/edit/": APIMetadata("wallet"),
    "/admin/walletuserinvite/details/": APIMetadata("wallet"),
    "/admin/walletuserinvite/delete/": APIMetadata("wallet"),
    "/admin/walletuserinvite/ajax/update/": APIMetadata("wallet"),
    "/admin/walletuserinvite/ajax/lookup/": APIMetadata("wallet"),
    "/admin/walletuserinvite/action/": APIMetadata("wallet"),
    "/admin/walletuserinvite/": APIMetadata("wallet"),
    "/admin/walletuserconsent/new/": APIMetadata("wallet"),
    "/admin/walletuserconsent/export/(.+?)/": APIMetadata("wallet"),
    "/admin/walletuserconsent/edit/": APIMetadata("wallet"),
    "/admin/walletuserconsent/details/": APIMetadata("wallet"),
    "/admin/walletuserconsent/delete/": APIMetadata("wallet"),
    "/admin/walletuserconsent/ajax/update/": APIMetadata("wallet"),
    "/admin/walletuserconsent/ajax/lookup/": APIMetadata("wallet"),
    "/admin/walletuserconsent/action/": APIMetadata("wallet"),
    "/admin/walletuserconsent/": APIMetadata("wallet"),
    "/admin/walletexpensesubtype/new/": APIMetadata("wallet"),
    "/admin/walletexpensesubtype/export/(.+?)/": APIMetadata("wallet"),
    "/admin/walletexpensesubtype/edit/": APIMetadata("wallet"),
    "/admin/walletexpensesubtype/details/": APIMetadata("wallet"),
    "/admin/walletexpensesubtype/delete/": APIMetadata("wallet"),
    "/admin/walletexpensesubtype/ajax/update/": APIMetadata("wallet"),
    "/admin/walletexpensesubtype/ajax/lookup/": APIMetadata("wallet"),
    "/admin/walletexpensesubtype/action/": APIMetadata("wallet"),
    "/admin/walletexpensesubtype/": APIMetadata("wallet"),
    "/admin/walletclientreports/new/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreports/export/(.+?)/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreports/edit/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreports/details/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreports/delete/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreports/ajax/update/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreports/ajax/lookup/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreports/action/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreports/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreportreimbursements/new/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreportreimbursements/export/(.+?)/": APIMetadata(
        "wallet_reporting"
    ),
    "/admin/walletclientreportreimbursements/edit/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreportreimbursements/details/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreportreimbursements/delete/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreportreimbursements/ajax/update/": APIMetadata(
        "wallet_reporting"
    ),
    "/admin/walletclientreportreimbursements/ajax/lookup/": APIMetadata(
        "wallet_reporting"
    ),
    "/admin/walletclientreportreimbursements/action/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreportreimbursements/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreportconfiguration/new/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreportconfiguration/export/(.+?)/": APIMetadata(
        "wallet_reporting"
    ),
    "/admin/walletclientreportconfiguration/edit/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreportconfiguration/details/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreportconfiguration/delete/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreportconfiguration/ajax/update/": APIMetadata(
        "wallet_reporting"
    ),
    "/admin/walletclientreportconfiguration/ajax/lookup/": APIMetadata(
        "wallet_reporting"
    ),
    "/admin/walletclientreportconfiguration/action/": APIMetadata("wallet_reporting"),
    "/admin/walletclientreportconfiguration/": APIMetadata("wallet_reporting"),
    "/admin/wallet_tools/retry_request_edi": APIMetadata("wallet_payments"),
    "/admin/wallet_tools/retry_process_edi": APIMetadata("wallet_payments"),
    "/admin/wallet_tools/resubmit_alegeus_reimbursement": APIMetadata("wallet"),
    "/admin/wallet_tools/handle_smp_rx_file": APIMetadata("wallet_payments"),
    "/admin/wallet_tools/download_ih_file": APIMetadata("wallet"),
    "/admin/wallet_tools/copy_wallet": APIMetadata("wallet"),
    "/admin/wallet_tools": APIMetadata("wallet"),
    "/admin/wallet_client_report_transactional": APIMetadata("wallet_reporting"),
    "/admin/wallet_client_report_reimbursements_audit": APIMetadata("wallet_reporting"),
    "/admin/wallet_client_report_audit": APIMetadata("wallet_reporting"),
    "/admin/wallet_client_report": APIMetadata("wallet_reporting"),
    "/admin/virtualevent/zoom_info": APIMetadata("learn"),
    "/admin/virtualevent/new/": APIMetadata("learn"),
    "/admin/virtualevent/edit/": APIMetadata("learn"),
    "/admin/virtualevent/": APIMetadata("learn"),
    "/admin/verticalgroupversion/": APIMetadata("booking_flow"),
    "/admin/verticalgroup/new/": APIMetadata("booking_flow"),
    "/admin/verticalgroup/edit/": APIMetadata("booking_flow"),
    "/admin/verticalgroup/": APIMetadata("booking_flow"),
    "/admin/verticalaccessbytrack/new/": APIMetadata("booking_flow"),
    "/admin/verticalaccessbytrack/export/(.+?)/": APIMetadata("booking_flow"),
    "/admin/verticalaccessbytrack/edit/": APIMetadata("booking_flow"),
    "/admin/verticalaccessbytrack/details/": APIMetadata("booking_flow"),
    "/admin/verticalaccessbytrack/delete/": APIMetadata("booking_flow"),
    "/admin/verticalaccessbytrack/ajax/update/": APIMetadata("booking_flow"),
    "/admin/verticalaccessbytrack/ajax/lookup/": APIMetadata("booking_flow"),
    "/admin/verticalaccessbytrack/action/": APIMetadata("booking_flow"),
    "/admin/verticalaccessbytrack/": APIMetadata("booking_flow"),
    "/admin/userorganizationemployee/edit/": APIMetadata("eligibility_admin"),
    "/admin/userorganizationemployee/": APIMetadata("eligibility_admin"),
    "/admin/upload_provider_contracts/": APIMetadata("provider_payments"),
    "/admin/treatmentprocedure/revert_payer_accumulation": APIMetadata(
        "treatment_procedure"
    ),
    "/admin/treatmentprocedure/refund_all_bills": APIMetadata("treatment_procedure"),
    "/admin/treatmentprocedure/new/": APIMetadata("treatment_procedure"),
    "/admin/treatmentprocedure/export/(.+?)/": APIMetadata("treatment_procedure"),
    "/admin/treatmentprocedure/edit/": APIMetadata("treatment_procedure"),
    "/admin/treatmentprocedure/details/": APIMetadata("treatment_procedure"),
    "/admin/treatmentprocedure/delete/": APIMetadata("treatment_procedure"),
    "/admin/treatmentprocedure/ajax/update/": APIMetadata("treatment_procedure"),
    "/admin/treatmentprocedure/ajax/lookup/": APIMetadata("treatment_procedure"),
    "/admin/treatmentprocedure/add_back_wallet_balance": APIMetadata(
        "treatment_procedure"
    ),
    "/admin/treatmentprocedure/action/": APIMetadata("treatment_procedure"),
    "/admin/treatmentprocedure/": APIMetadata("treatment_procedure"),
    "/admin/tracks_extension/new/": APIMetadata("enrollments"),
    "/admin/tracks_extension/export/(.+?)/": APIMetadata("enrollments"),
    "/admin/tracks_extension/edit/": APIMetadata("enrollments"),
    "/admin/tracks_extension/do_extend": APIMetadata("enrollments"),
    "/admin/tracks_extension/details/": APIMetadata("enrollments"),
    "/admin/tracks_extension/delete/": APIMetadata("enrollments"),
    "/admin/tracks_extension/ajax/update/": APIMetadata("enrollments"),
    "/admin/tracks_extension/ajax/lookup/": APIMetadata("enrollments"),
    "/admin/tracks_extension/action/": APIMetadata("enrollments"),
    "/admin/tracks_extension/": APIMetadata("enrollments"),
    "/admin/rtetransaction/new/": APIMetadata("cost_breakdown"),
    "/admin/rtetransaction/export/(.+?)/": APIMetadata("cost_breakdown"),
    "/admin/rtetransaction/edit/": APIMetadata("cost_breakdown"),
    "/admin/rtetransaction/details/": APIMetadata("cost_breakdown"),
    "/admin/rtetransaction/delete/": APIMetadata("cost_breakdown"),
    "/admin/rtetransaction/ajax/update/": APIMetadata("cost_breakdown"),
    "/admin/rtetransaction/ajax/lookup/": APIMetadata("cost_breakdown"),
    "/admin/rtetransaction/action/": APIMetadata("cost_breakdown"),
    "/admin/rtetransaction/": APIMetadata("cost_breakdown"),
    "/admin/riskflag/": APIMetadata("health"),
    "/admin/risk_flags/member_risk_edit": APIMetadata("health"),
    "/admin/resource/new/": APIMetadata("learn"),
    "/admin/resource/edit/": APIMetadata("learn"),
    "/admin/resource/": APIMetadata("learn"),
    "/admin/replace_practitioner/": APIMetadata("care_team"),
    "/admin/reimbursementwalletusers/new/": APIMetadata("wallet"),
    "/admin/reimbursementwalletusers/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementwalletusers/edit/": APIMetadata("wallet"),
    "/admin/reimbursementwalletusers/details/": APIMetadata("wallet"),
    "/admin/reimbursementwalletusers/delete/": APIMetadata("wallet"),
    "/admin/reimbursementwalletusers/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementwalletusers/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementwalletusers/action/": APIMetadata("wallet"),
    "/admin/reimbursementwalletusers/": APIMetadata("wallet"),
    "/admin/reimbursementwalletplanhdhp/new/": APIMetadata("wallet_payments"),
    "/admin/reimbursementwalletplanhdhp/export/(.+?)/": APIMetadata("wallet_payments"),
    "/admin/reimbursementwalletplanhdhp/edit/": APIMetadata("wallet_payments"),
    "/admin/reimbursementwalletplanhdhp/details/": APIMetadata("wallet_payments"),
    "/admin/reimbursementwalletplanhdhp/delete/": APIMetadata("wallet_payments"),
    "/admin/reimbursementwalletplanhdhp/ajax/update/": APIMetadata("wallet_payments"),
    "/admin/reimbursementwalletplanhdhp/ajax/lookup/": APIMetadata("wallet_payments"),
    "/admin/reimbursementwalletplanhdhp/action/": APIMetadata("wallet_payments"),
    "/admin/reimbursementwalletplanhdhp/": APIMetadata("wallet_payments"),
    "/admin/reimbursementwalletglobalprocedures/new/": APIMetadata("direct_payment"),
    "/admin/reimbursementwalletglobalprocedures/export/(.+?)/": APIMetadata(
        "direct_payment"
    ),
    "/admin/reimbursementwalletglobalprocedures/edit/": APIMetadata("direct_payment"),
    "/admin/reimbursementwalletglobalprocedures/details/": APIMetadata(
        "direct_payment"
    ),
    "/admin/reimbursementwalletglobalprocedures/delete/": APIMetadata("direct_payment"),
    "/admin/reimbursementwalletglobalprocedures/ajax/update/": APIMetadata(
        "direct_payment"
    ),
    "/admin/reimbursementwalletglobalprocedures/ajax/lookup/": APIMetadata(
        "direct_payment"
    ),
    "/admin/reimbursementwalletglobalprocedures/action/": APIMetadata("direct_payment"),
    "/admin/reimbursementwalletglobalprocedures/": APIMetadata("direct_payment"),
    "/admin/reimbursementwalleteligibilitysyncmeta/new/": APIMetadata("wallet"),
    "/admin/reimbursementwalleteligibilitysyncmeta/export/(.+?)/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementwalleteligibilitysyncmeta/edit/": APIMetadata("wallet"),
    "/admin/reimbursementwalleteligibilitysyncmeta/details/": APIMetadata("wallet"),
    "/admin/reimbursementwalleteligibilitysyncmeta/delete/": APIMetadata("wallet"),
    "/admin/reimbursementwalleteligibilitysyncmeta/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementwalleteligibilitysyncmeta/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementwalleteligibilitysyncmeta/action/": APIMetadata("wallet"),
    "/admin/reimbursementwalleteligibilitysyncmeta/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdebitcard/new/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdebitcard/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdebitcard/edit/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdebitcard/details/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdebitcard/delete/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdebitcard/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdebitcard/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdebitcard/action/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdebitcard/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcards/new/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcards/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcards/edit/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcards/details/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcards/delete/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcards/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcards/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcards/action/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcards/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcard/new/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcard/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcard/edit/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcard/details/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcard/delete/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcard/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcard/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcard/action/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboardcard/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboard/new/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboard/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboard/edit/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboard/details/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboard/delete/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboard/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboard/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboard/action/": APIMetadata("wallet"),
    "/admin/reimbursementwalletdashboard/": APIMetadata("wallet"),
    "/admin/reimbursementwalletcategoryruleevaluationresult/new/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementwalletcategoryruleevaluationresult/export/(.+?)/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementwalletcategoryruleevaluationresult/edit/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementwalletcategoryruleevaluationresult/details/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementwalletcategoryruleevaluationresult/delete/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementwalletcategoryruleevaluationresult/ajax/update/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementwalletcategoryruleevaluationresult/ajax/lookup/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementwalletcategoryruleevaluationresult/action/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementwalletcategoryruleevaluationresult/": APIMetadata("wallet"),
    "/admin/reimbursementwalletblacklist/new/": APIMetadata("wallet"),
    "/admin/reimbursementwalletblacklist/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementwalletblacklist/edit/": APIMetadata("wallet"),
    "/admin/reimbursementwalletblacklist/details/": APIMetadata("wallet"),
    "/admin/reimbursementwalletblacklist/delete/": APIMetadata("wallet"),
    "/admin/reimbursementwalletblacklist/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementwalletblacklist/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementwalletblacklist/action/": APIMetadata("wallet"),
    "/admin/reimbursementwalletblacklist/": APIMetadata("wallet"),
    "/admin/reimbursementwalletbillingconsent/new/": APIMetadata("direct_payment"),
    "/admin/reimbursementwalletbillingconsent/export/(.+?)/": APIMetadata(
        "direct_payment"
    ),
    "/admin/reimbursementwalletbillingconsent/edit/": APIMetadata("direct_payment"),
    "/admin/reimbursementwalletbillingconsent/details/": APIMetadata("direct_payment"),
    "/admin/reimbursementwalletbillingconsent/delete/": APIMetadata("direct_payment"),
    "/admin/reimbursementwalletbillingconsent/ajax/update/": APIMetadata(
        "direct_payment"
    ),
    "/admin/reimbursementwalletbillingconsent/ajax/lookup/": APIMetadata(
        "direct_payment"
    ),
    "/admin/reimbursementwalletbillingconsent/action/": APIMetadata("direct_payment"),
    "/admin/reimbursementwalletbillingconsent/": APIMetadata("direct_payment"),
    "/admin/reimbursementwalletallowedcategorysettings/new/": APIMetadata("wallet"),
    "/admin/reimbursementwalletallowedcategorysettings/export/(.+?)/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementwalletallowedcategorysettings/edit/": APIMetadata("wallet"),
    "/admin/reimbursementwalletallowedcategorysettings/details/": APIMetadata("wallet"),
    "/admin/reimbursementwalletallowedcategorysettings/delete/": APIMetadata("wallet"),
    "/admin/reimbursementwalletallowedcategorysettings/ajax/update/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementwalletallowedcategorysettings/ajax/lookup/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementwalletallowedcategorysettings/action/": APIMetadata("wallet"),
    "/admin/reimbursementwalletallowedcategorysettings/": APIMetadata("wallet"),
    "/admin/reimbursementwallet/new/": APIMetadata("wallet"),
    "/admin/reimbursementwallet/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementwallet/edit/": APIMetadata("wallet"),
    "/admin/reimbursementwallet/details/": APIMetadata("wallet"),
    "/admin/reimbursementwallet/delete/": APIMetadata("wallet"),
    "/admin/reimbursementwallet/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementwallet/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementwallet/action/": APIMetadata("wallet"),
    "/admin/reimbursementwallet/": APIMetadata("wallet"),
    "/admin/reimbursementtransaction/new/": APIMetadata("wallet"),
    "/admin/reimbursementtransaction/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementtransaction/edit/": APIMetadata("wallet"),
    "/admin/reimbursementtransaction/details/": APIMetadata("wallet"),
    "/admin/reimbursementtransaction/delete/": APIMetadata("wallet"),
    "/admin/reimbursementtransaction/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementtransaction/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementtransaction/action/": APIMetadata("wallet"),
    "/admin/reimbursementtransaction/": APIMetadata("wallet"),
    "/admin/reimbursementservicecategory/new/": APIMetadata("wallet"),
    "/admin/reimbursementservicecategory/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementservicecategory/edit/": APIMetadata("wallet"),
    "/admin/reimbursementservicecategory/details/": APIMetadata("wallet"),
    "/admin/reimbursementservicecategory/delete/": APIMetadata("wallet"),
    "/admin/reimbursementservicecategory/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementservicecategory/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementservicecategory/action/": APIMetadata("wallet"),
    "/admin/reimbursementservicecategory/": APIMetadata("wallet"),
    "/admin/reimbursementrequestsource/new/": APIMetadata("wallet"),
    "/admin/reimbursementrequestsource/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementrequestsource/edit/": APIMetadata("wallet"),
    "/admin/reimbursementrequestsource/details/": APIMetadata("wallet"),
    "/admin/reimbursementrequestsource/delete/": APIMetadata("wallet"),
    "/admin/reimbursementrequestsource/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementrequestsource/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementrequestsource/action/": APIMetadata("wallet"),
    "/admin/reimbursementrequestsource/": APIMetadata("wallet"),
    "/admin/reimbursementrequestexchangerates/new/": APIMetadata("wallet"),
    "/admin/reimbursementrequestexchangerates/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementrequestexchangerates/edit/": APIMetadata("wallet"),
    "/admin/reimbursementrequestexchangerates/details/": APIMetadata("wallet"),
    "/admin/reimbursementrequestexchangerates/delete/": APIMetadata("wallet"),
    "/admin/reimbursementrequestexchangerates/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementrequestexchangerates/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementrequestexchangerates/action/": APIMetadata("wallet"),
    "/admin/reimbursementrequestexchangerates/": APIMetadata("wallet"),
    "/admin/reimbursementrequestcategory/new/": APIMetadata("wallet"),
    "/admin/reimbursementrequestcategory/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementrequestcategory/edit/": APIMetadata("wallet"),
    "/admin/reimbursementrequestcategory/details/": APIMetadata("wallet"),
    "/admin/reimbursementrequestcategory/delete/": APIMetadata("wallet"),
    "/admin/reimbursementrequestcategory/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementrequestcategory/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementrequestcategory/action/": APIMetadata("wallet"),
    "/admin/reimbursementrequestcategory/": APIMetadata("wallet"),
    "/admin/reimbursementrequest/new/": APIMetadata("wallet_payments"),
    "/admin/reimbursementrequest/export/(.+?)/": APIMetadata("wallet_payments"),
    "/admin/reimbursementrequest/edit/": APIMetadata("wallet_payments"),
    "/admin/reimbursementrequest/document_mapping": APIMetadata("wallet_payments"),
    "/admin/reimbursementrequest/document_mapper_feedback": APIMetadata(
        "wallet_payments"
    ),
    "/admin/reimbursementrequest/details/": APIMetadata("wallet_payments"),
    "/admin/reimbursementrequest/delete/": APIMetadata("wallet_payments"),
    "/admin/reimbursementrequest/ajax/update/": APIMetadata("wallet_payments"),
    "/admin/reimbursementrequest/ajax/lookup/": APIMetadata("wallet_payments"),
    "/admin/reimbursementrequest/action/": APIMetadata("wallet_payments"),
    "/admin/reimbursementrequest/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplancoveragetier/new/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplancoveragetier/export/(.+?)/": APIMetadata(
        "wallet_payments"
    ),
    "/admin/reimbursementplancoveragetier/edit/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplancoveragetier/details/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplancoveragetier/delete/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplancoveragetier/ajax/update/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplancoveragetier/ajax/lookup/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplancoveragetier/action/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplancoveragetier/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplan/new/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplan/export/(.+?)/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplan/edit/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplan/details/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplan/delete/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplan/ajax/update/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplan/ajax/lookup/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplan/action/": APIMetadata("wallet_payments"),
    "/admin/reimbursementplan/": APIMetadata("wallet_payments"),
    "/admin/reimbursementorgsettingsexpensetype/new/": APIMetadata("wallet_payments"),
    "/admin/reimbursementorgsettingsexpensetype/export/(.+?)/": APIMetadata(
        "wallet_payments"
    ),
    "/admin/reimbursementorgsettingsexpensetype/edit/": APIMetadata("wallet_payments"),
    "/admin/reimbursementorgsettingsexpensetype/details/": APIMetadata(
        "wallet_payments"
    ),
    "/admin/reimbursementorgsettingsexpensetype/delete/": APIMetadata(
        "wallet_payments"
    ),
    "/admin/reimbursementorgsettingsexpensetype/ajax/update/": APIMetadata(
        "wallet_payments"
    ),
    "/admin/reimbursementorgsettingsexpensetype/ajax/lookup/": APIMetadata(
        "wallet_payments"
    ),
    "/admin/reimbursementorgsettingsexpensetype/action/": APIMetadata(
        "wallet_payments"
    ),
    "/admin/reimbursementorgsettingsexpensetype/": APIMetadata("wallet_payments"),
    "/admin/reimbursementorgsettingsallowedcategoryrule/new/": APIMetadata("wallet"),
    "/admin/reimbursementorgsettingsallowedcategoryrule/export/(.+?)/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementorgsettingsallowedcategoryrule/edit/": APIMetadata("wallet"),
    "/admin/reimbursementorgsettingsallowedcategoryrule/details/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementorgsettingsallowedcategoryrule/delete/": APIMetadata("wallet"),
    "/admin/reimbursementorgsettingsallowedcategoryrule/ajax/update/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementorgsettingsallowedcategoryrule/ajax/lookup/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementorgsettingsallowedcategoryrule/action/": APIMetadata("wallet"),
    "/admin/reimbursementorgsettingsallowedcategoryrule/": APIMetadata("wallet"),
    "/admin/reimbursementorgsettingcategoryassociation/new/": APIMetadata("wallet"),
    "/admin/reimbursementorgsettingcategoryassociation/export/(.+?)/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementorgsettingcategoryassociation/edit/": APIMetadata("wallet"),
    "/admin/reimbursementorgsettingcategoryassociation/details/": APIMetadata("wallet"),
    "/admin/reimbursementorgsettingcategoryassociation/delete/": APIMetadata("wallet"),
    "/admin/reimbursementorgsettingcategoryassociation/ajax/update/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementorgsettingcategoryassociation/ajax/lookup/": APIMetadata(
        "wallet"
    ),
    "/admin/reimbursementorgsettingcategoryassociation/action/": APIMetadata("wallet"),
    "/admin/reimbursementorgsettingcategoryassociation/": APIMetadata("wallet"),
    "/admin/reimbursementorganizationsettings/new/": APIMetadata("wallet"),
    "/admin/reimbursementorganizationsettings/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursementorganizationsettings/edit/": APIMetadata("wallet"),
    "/admin/reimbursementorganizationsettings/details/": APIMetadata("wallet"),
    "/admin/reimbursementorganizationsettings/delete/": APIMetadata("wallet"),
    "/admin/reimbursementorganizationsettings/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursementorganizationsettings/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursementorganizationsettings/action/": APIMetadata("wallet"),
    "/admin/reimbursementorganizationsettings/": APIMetadata("wallet"),
    "/admin/reimbursementcyclecredits/new/": APIMetadata("direct_payment"),
    "/admin/reimbursementcyclecredits/export/(.+?)/": APIMetadata("direct_payment"),
    "/admin/reimbursementcyclecredits/edit/": APIMetadata("direct_payment"),
    "/admin/reimbursementcyclecredits/details/": APIMetadata("direct_payment"),
    "/admin/reimbursementcyclecredits/delete/": APIMetadata("direct_payment"),
    "/admin/reimbursementcyclecredits/ajax/update/": APIMetadata("direct_payment"),
    "/admin/reimbursementcyclecredits/ajax/lookup/": APIMetadata("direct_payment"),
    "/admin/reimbursementcyclecredits/action/": APIMetadata("direct_payment"),
    "/admin/reimbursementcyclecredits/": APIMetadata("direct_payment"),
    "/admin/reimbursementclaim/new/": APIMetadata("wallet_payments"),
    "/admin/reimbursementclaim/export/(.+?)/": APIMetadata("wallet_payments"),
    "/admin/reimbursementclaim/edit/": APIMetadata("wallet_payments"),
    "/admin/reimbursementclaim/details/": APIMetadata("wallet_payments"),
    "/admin/reimbursementclaim/delete/": APIMetadata("wallet_payments"),
    "/admin/reimbursementclaim/ajax/update/": APIMetadata("wallet_payments"),
    "/admin/reimbursementclaim/ajax/lookup/": APIMetadata("wallet_payments"),
    "/admin/reimbursementclaim/action/": APIMetadata("wallet_payments"),
    "/admin/reimbursementclaim/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccounttype/new/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccounttype/export/(.+?)/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccounttype/edit/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccounttype/details/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccounttype/delete/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccounttype/ajax/update/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccounttype/ajax/lookup/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccounttype/action/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccounttype/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccount/new/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccount/export/(.+?)/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccount/edit/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccount/details/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccount/delete/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccount/ajax/update/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccount/ajax/lookup/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccount/action/": APIMetadata("wallet_payments"),
    "/admin/reimbursementaccount/": APIMetadata("wallet_payments"),
    "/admin/reimbursement_request_calculator/submit": APIMetadata("cost_breakdown"),
    "/admin/reimbursement_request_calculator/save": APIMetadata("cost_breakdown"),
    "/admin/reimbursement_request_calculator/": APIMetadata("cost_breakdown"),
    "/admin/reimbursement_dashboard/new/": APIMetadata("wallet"),
    "/admin/reimbursement_dashboard/export/(.+?)/": APIMetadata("wallet"),
    "/admin/reimbursement_dashboard/edit/": APIMetadata("wallet"),
    "/admin/reimbursement_dashboard/document_mapping": APIMetadata("wallet_payments"),
    "/admin/reimbursement_dashboard/document_mapper_feedback": APIMetadata(
        "wallet_payments"
    ),
    "/admin/reimbursement_dashboard/details/": APIMetadata("wallet"),
    "/admin/reimbursement_dashboard/delete/": APIMetadata("wallet"),
    "/admin/reimbursement_dashboard/ajax/update/": APIMetadata("wallet"),
    "/admin/reimbursement_dashboard/ajax/lookup/": APIMetadata("wallet"),
    "/admin/reimbursement_dashboard/action/": APIMetadata("wallet"),
    "/admin/reimbursement_dashboard/": APIMetadata("wallet"),
    "/admin/questionset/duplicate": APIMetadata("clinical_documentation"),
    "/admin/questionnaireglobalprocedure/new/": APIMetadata("clinic_management"),
    "/admin/questionnaireglobalprocedure/export/(.+?)/": APIMetadata(
        "clinic_management"
    ),
    "/admin/questionnaireglobalprocedure/edit/": APIMetadata("clinic_management"),
    "/admin/questionnaireglobalprocedure/details/": APIMetadata("clinic_management"),
    "/admin/questionnaireglobalprocedure/delete/": APIMetadata("clinic_management"),
    "/admin/questionnaireglobalprocedure/ajax/update/": APIMetadata(
        "clinic_management"
    ),
    "/admin/questionnaireglobalprocedure/ajax/lookup/": APIMetadata(
        "clinic_management"
    ),
    "/admin/questionnaireglobalprocedure/action/": APIMetadata("clinic_management"),
    "/admin/questionnaireglobalprocedure/": APIMetadata("clinic_management"),
    "/admin/question/duplicate": APIMetadata("clinical_documentation"),
    "/admin/proceduresview/": APIMetadata("direct_payment"),
    "/admin/preference/new/": APIMetadata("enrollments"),
    "/admin/preference/export/(.+?)/": APIMetadata("enrollments"),
    "/admin/preference/edit/": APIMetadata("enrollments"),
    "/admin/preference/details/": APIMetadata("enrollments"),
    "/admin/preference/delete/": APIMetadata("enrollments"),
    "/admin/preference/ajax/update/": APIMetadata("enrollments"),
    "/admin/preference/ajax/lookup/": APIMetadata("enrollments"),
    "/admin/preference/action/": APIMetadata("enrollments"),
    "/admin/preference/": APIMetadata("enrollments"),
    "/admin/practitionertrackvgc/new/": APIMetadata("care_team"),
    "/admin/practitionertrackvgc/details/": APIMetadata("care_team"),
    "/admin/practitionertrackvgc/ajax/lookup/": APIMetadata("care_team"),
    "/admin/practitionertrackvgc/action/": APIMetadata("care_team"),
    "/admin/practitionertrackvgc/": APIMetadata("care_team"),
    "/admin/practitionerprofile/bookable_times/": APIMetadata("booking_flow"),
    "/admin/practitionercontract/new/": APIMetadata("provider_payments"),
    "/admin/practitionercontract/export/(.+?)/": APIMetadata("provider_payments"),
    "/admin/practitionercontract/edit/": APIMetadata("provider_payments"),
    "/admin/practitionercontract/details/": APIMetadata("provider_payments"),
    "/admin/practitionercontract/delete/": APIMetadata("provider_payments"),
    "/admin/practitionercontract/ajax/update/": APIMetadata("provider_payments"),
    "/admin/practitionercontract/ajax/lookup/": APIMetadata("provider_payments"),
    "/admin/practitionercontract/action/": APIMetadata("provider_payments"),
    "/admin/practitionercontract/": APIMetadata("provider_payments"),
    "/admin/practitioner_specialty_bulk_update/upload": APIMetadata("booking_flow"),
    "/admin/practitioner_specialty_bulk_update/": APIMetadata("booking_flow"),
    "/admin/post/edit/": APIMetadata("community_forum"),
    "/admin/post/clear_cache/": APIMetadata("community_forum"),
    "/admin/post/": APIMetadata("community_forum"),
    "/admin/populartopic/": APIMetadata("learn"),
    "/admin/pharmacyprescription/new/": APIMetadata("pharmacy"),
    "/admin/pharmacyprescription/export/(.+?)/": APIMetadata("pharmacy"),
    "/admin/pharmacyprescription/edit/": APIMetadata("pharmacy"),
    "/admin/pharmacyprescription/details/": APIMetadata("pharmacy"),
    "/admin/pharmacyprescription/delete/": APIMetadata("pharmacy"),
    "/admin/pharmacyprescription/ajax/update/": APIMetadata("pharmacy"),
    "/admin/pharmacyprescription/ajax/lookup/": APIMetadata("pharmacy"),
    "/admin/pharmacyprescription/action/": APIMetadata("pharmacy"),
    "/admin/pharmacyprescription/": APIMetadata("pharmacy"),
    "/admin/payment_tools": APIMetadata("provider_payments"),
    "/admin/payeraccumulationreports/submit": APIMetadata("payer_accumulation"),
    "/admin/payeraccumulationreports/overwrite": APIMetadata("payer_accumulation"),
    "/admin/payeraccumulationreports/new/": APIMetadata("payer_accumulation"),
    "/admin/payeraccumulationreports/export/(.+?)/": APIMetadata("payer_accumulation"),
    "/admin/payeraccumulationreports/edit/": APIMetadata("payer_accumulation"),
    "/admin/payeraccumulationreports/download": APIMetadata("payer_accumulation"),
    "/admin/payeraccumulationreports/diff": APIMetadata("payer_accumulation"),
    "/admin/payeraccumulationreports/details/": APIMetadata("payer_accumulation"),
    "/admin/payeraccumulationreports/delete/": APIMetadata("payer_accumulation"),
    "/admin/payeraccumulationreports/ajax/update/": APIMetadata("payer_accumulation"),
    "/admin/payeraccumulationreports/ajax/lookup/": APIMetadata("payer_accumulation"),
    "/admin/payeraccumulationreports/action/": APIMetadata("payer_accumulation"),
    "/admin/payeraccumulationreports/": APIMetadata("payer_accumulation"),
    "/admin/payer/new/": APIMetadata("payer_accumulation"),
    "/admin/payer/export/(.+?)/": APIMetadata("payer_accumulation"),
    "/admin/payer/edit/": APIMetadata("payer_accumulation"),
    "/admin/payer/details/": APIMetadata("payer_accumulation"),
    "/admin/payer/delete/": APIMetadata("payer_accumulation"),
    "/admin/payer/ajax/update/": APIMetadata("payer_accumulation"),
    "/admin/payer/ajax/lookup/": APIMetadata("payer_accumulation"),
    "/admin/payer/action/": APIMetadata("payer_accumulation"),
    "/admin/payer/": APIMetadata("payer_accumulation"),
    "/admin/orgdirectpaymentinvoicereport/new/": APIMetadata(
        "direct_payment_invoice_report"
    ),
    "/admin/orgdirectpaymentinvoicereport/export/(.+?)/": APIMetadata(
        "direct_payment_invoice_report"
    ),
    "/admin/orgdirectpaymentinvoicereport/edit/": APIMetadata(
        "direct_payment_invoice_report"
    ),
    "/admin/orgdirectpaymentinvoicereport/details/": APIMetadata(
        "direct_payment_invoice_report"
    ),
    "/admin/orgdirectpaymentinvoicereport/delete/": APIMetadata(
        "direct_payment_invoice_report"
    ),
    "/admin/orgdirectpaymentinvoicereport/ajax/update/": APIMetadata(
        "direct_payment_invoice_report"
    ),
    "/admin/orgdirectpaymentinvoicereport/ajax/lookup/": APIMetadata(
        "direct_payment_invoice_report"
    ),
    "/admin/orgdirectpaymentinvoicereport/action/": APIMetadata(
        "direct_payment_invoice_report"
    ),
    "/admin/orgdirectpaymentinvoicereport/": APIMetadata(
        "direct_payment_invoice_report"
    ),
    "/admin/organizationinvoicingsettings/new/": APIMetadata(
        "direct_payment_invoicing_setting"
    ),
    "/admin/organizationinvoicingsettings/export/(.+?)/": APIMetadata(
        "direct_payment_invoicing_setting"
    ),
    "/admin/organizationinvoicingsettings/edit/": APIMetadata(
        "direct_payment_invoicing_setting"
    ),
    "/admin/organizationinvoicingsettings/details/": APIMetadata(
        "direct_payment_invoicing_setting"
    ),
    "/admin/organizationinvoicingsettings/delete/": APIMetadata(
        "direct_payment_invoicing_setting"
    ),
    "/admin/organizationinvoicingsettings/ajax/update/": APIMetadata(
        "direct_payment_invoicing_setting"
    ),
    "/admin/organizationinvoicingsettings/ajax/lookup/": APIMetadata(
        "direct_payment_invoicing_setting"
    ),
    "/admin/organizationinvoicingsettings/action/": APIMetadata(
        "direct_payment_invoicing_setting"
    ),
    "/admin/organizationinvoicingsettings/": APIMetadata(
        "direct_payment_invoicing_setting"
    ),
    "/admin/organizationemployeedependent/edit/": APIMetadata("eligibility_admin"),
    "/admin/organizationemployeedependent/": APIMetadata("eligibility_admin"),
    "/admin/organizationemployee/edit/": APIMetadata("eligibility_admin"),
    "/admin/organizationemployee/details/": APIMetadata("eligibility_admin"),
    "/admin/organizationemployee/create/": APIMetadata("eligibility_admin"),
    "/admin/organizationemployee/ajax/lookup/": APIMetadata("eligibility_admin"),
    "/admin/organizationemployee/": APIMetadata("eligibility_admin"),
    "/admin/needsassessment/edit/": APIMetadata("assessments"),
    "/admin/needsassessment/": APIMetadata("assessments"),
    "/admin/monthly_payments/sign_stripe_tos": APIMetadata("provider_payments"),
    "/admin/monthly_payments/invoice/": APIMetadata("provider_payments"),
    "/admin/monthly_payments/incomplete_invoices": APIMetadata("provider_payments"),
    "/admin/monthly_payments/generate_invoices": APIMetadata("provider_payments"),
    "/admin/monthly_payments/generate_fees": APIMetadata("provider_payments"),
    "/admin/monthly_payments/existing_invoice": APIMetadata("provider_payments"),
    "/admin/monthly_payments/": APIMetadata("provider_payments"),
    "/admin/membertrack/edit/": APIMetadata("tracks"),
    "/admin/membertrack/ajax/lookup/": APIMetadata("tracks"),
    "/admin/membertrack/action/": APIMetadata("tracks"),
    "/admin/membertrack/": APIMetadata("tracks"),
    "/admin/memberriskflag/": APIMetadata("health"),
    "/admin/memberprofile/new/": APIMetadata("member_profile"),
    "/admin/memberprofile/edit/": APIMetadata("member_profile"),
    "/admin/memberprofile/": APIMetadata("member_profile"),
    "/admin/memberpreference/new/": APIMetadata("enrollments"),
    "/admin/memberpreference/export/(.+?)/": APIMetadata("enrollments"),
    "/admin/memberpreference/edit/": APIMetadata("enrollments"),
    "/admin/memberpreference/details/": APIMetadata("enrollments"),
    "/admin/memberpreference/delete/": APIMetadata("enrollments"),
    "/admin/memberpreference/ajax/update/": APIMetadata("enrollments"),
    "/admin/memberpreference/ajax/lookup/": APIMetadata("enrollments"),
    "/admin/memberpreference/action/": APIMetadata("enrollments"),
    "/admin/memberpreference/": APIMetadata("enrollments"),
    "/admin/memberpractitionerassociation/new/": APIMetadata("care_team"),
    "/admin/memberpractitionerassociation/edit/": APIMetadata("care_team"),
    "/admin/memberpractitionerassociation/ajax/lookup/": APIMetadata("care_team"),
    "/admin/memberpractitionerassociation/": APIMetadata("care_team"),
    "/admin/memberhealthplan/new/": APIMetadata("health_plans"),
    "/admin/memberhealthplan/export/(.+?)/": APIMetadata("health_plans"),
    "/admin/memberhealthplan/edit/": APIMetadata("health_plans"),
    "/admin/memberhealthplan/details/": APIMetadata("health_plans"),
    "/admin/memberhealthplan/delete/": APIMetadata("health_plans"),
    "/admin/memberhealthplan/ajax/update/": APIMetadata("health_plans"),
    "/admin/memberhealthplan/ajax/lookup/": APIMetadata("health_plans"),
    "/admin/memberhealthplan/action/": APIMetadata("health_plans"),
    "/admin/memberhealthplan/": APIMetadata("health_plans"),
    "/admin/invoice/pay/": APIMetadata("provider_payments"),
    "/admin/invoice/edit/": APIMetadata("provider_payments"),
    "/admin/invoice/": APIMetadata("provider_payments"),
    "/admin/invite/edit/": APIMetadata("enrollments"),
    "/admin/invite/": APIMetadata("enrollments"),
    "/admin/ingestionmeta/new/": APIMetadata("direct_payment"),
    "/admin/ingestionmeta/export/(.+?)/": APIMetadata("direct_payment"),
    "/admin/ingestionmeta/edit/": APIMetadata("direct_payment"),
    "/admin/ingestionmeta/details/": APIMetadata("direct_payment"),
    "/admin/ingestionmeta/delete/": APIMetadata("direct_payment"),
    "/admin/ingestionmeta/ajax/update/": APIMetadata("direct_payment"),
    "/admin/ingestionmeta/ajax/lookup/": APIMetadata("direct_payment"),
    "/admin/ingestionmeta/action/": APIMetadata("direct_payment"),
    "/admin/ingestionmeta/": APIMetadata("direct_payment"),
    "/admin/incentiveorganization/new/": APIMetadata("incentive"),
    "/admin/incentiveorganization/export/(.+?)/": APIMetadata("incentive"),
    "/admin/incentiveorganization/edit/": APIMetadata("incentive"),
    "/admin/incentiveorganization/details/": APIMetadata("incentive"),
    "/admin/incentiveorganization/delete/": APIMetadata("incentive"),
    "/admin/incentiveorganization/ajax/update/": APIMetadata("incentive"),
    "/admin/incentiveorganization/ajax/lookup/": APIMetadata("incentive"),
    "/admin/incentiveorganization/action/": APIMetadata("incentive"),
    "/admin/incentiveorganization/": APIMetadata("incentive"),
    "/admin/incentivefulfillment/new/": APIMetadata("incentive"),
    "/admin/incentivefulfillment/export/(.+?)/": APIMetadata("incentive"),
    "/admin/incentivefulfillment/edit/": APIMetadata("incentive"),
    "/admin/incentivefulfillment/details/": APIMetadata("incentive"),
    "/admin/incentivefulfillment/delete/": APIMetadata("incentive"),
    "/admin/incentivefulfillment/ajax/update/": APIMetadata("incentive"),
    "/admin/incentivefulfillment/ajax/lookup/": APIMetadata("incentive"),
    "/admin/incentivefulfillment/action/": APIMetadata("incentive"),
    "/admin/incentivefulfillment/": APIMetadata("incentive"),
    "/admin/incentive/new/": APIMetadata("incentive"),
    "/admin/incentive/export/(.+?)/": APIMetadata("incentive"),
    "/admin/incentive/edit/": APIMetadata("incentive"),
    "/admin/incentive/details/": APIMetadata("incentive"),
    "/admin/incentive/delete/": APIMetadata("incentive"),
    "/admin/incentive/ajax/update/": APIMetadata("incentive"),
    "/admin/incentive/ajax/lookup/": APIMetadata("incentive"),
    "/admin/incentive/action/": APIMetadata("incentive"),
    "/admin/incentive/": APIMetadata("incentive"),
    "/admin/inboundphonenumber/new/": APIMetadata("phone_support"),
    "/admin/inboundphonenumber/export/(.+?)/": APIMetadata("phone_support"),
    "/admin/inboundphonenumber/edit/": APIMetadata("phone_support"),
    "/admin/inboundphonenumber/details/": APIMetadata("phone_support"),
    "/admin/inboundphonenumber/delete/": APIMetadata("phone_support"),
    "/admin/inboundphonenumber/ajax/update/": APIMetadata("phone_support"),
    "/admin/inboundphonenumber/ajax/lookup/": APIMetadata("phone_support"),
    "/admin/inboundphonenumber/action/": APIMetadata("phone_support"),
    "/admin/inboundphonenumber/": APIMetadata("phone_support"),
    "/admin/healthplanyeartodatespend/new/": APIMetadata("pharmacy"),
    "/admin/healthplanyeartodatespend/export/(.+?)/": APIMetadata("pharmacy"),
    "/admin/healthplanyeartodatespend/edit/": APIMetadata("pharmacy"),
    "/admin/healthplanyeartodatespend/details/": APIMetadata("pharmacy"),
    "/admin/healthplanyeartodatespend/delete/": APIMetadata("pharmacy"),
    "/admin/healthplanyeartodatespend/ajax/update/": APIMetadata("pharmacy"),
    "/admin/healthplanyeartodatespend/ajax/lookup/": APIMetadata("pharmacy"),
    "/admin/healthplanyeartodatespend/action/": APIMetadata("pharmacy"),
    "/admin/healthplanyeartodatespend/": APIMetadata("pharmacy"),
    "/admin/gdpruserrequest/new/": APIMetadata("core_services"),
    "/admin/gdpruserrequest/export/(.+?)/": APIMetadata("core_services"),
    "/admin/gdpruserrequest/edit/": APIMetadata("core_services"),
    "/admin/gdpruserrequest/details/": APIMetadata("core_services"),
    "/admin/gdpruserrequest/delete/": APIMetadata("core_services"),
    "/admin/gdpruserrequest/ajax/update/": APIMetadata("core_services"),
    "/admin/gdpruserrequest/ajax/lookup/": APIMetadata("core_services"),
    "/admin/gdpruserrequest/action/": APIMetadata("core_services"),
    "/admin/gdpruserrequest/": APIMetadata("core_services"),
    "/admin/gdprdeletionbackup/new/": APIMetadata("core_services"),
    "/admin/gdprdeletionbackup/export/(.+?)/": APIMetadata("core_services"),
    "/admin/gdprdeletionbackup/edit/": APIMetadata("core_services"),
    "/admin/gdprdeletionbackup/details/": APIMetadata("core_services"),
    "/admin/gdprdeletionbackup/delete/": APIMetadata("core_services"),
    "/admin/gdprdeletionbackup/ajax/update/": APIMetadata("core_services"),
    "/admin/gdprdeletionbackup/ajax/lookup/": APIMetadata("core_services"),
    "/admin/gdprdeletionbackup/action/": APIMetadata("core_services"),
    "/admin/gdprdeletionbackup/": APIMetadata("core_services"),
    "/admin/fertilityclinicuserprofile/new/": APIMetadata("clinic_management"),
    "/admin/fertilityclinicuserprofile/export/(.+?)/": APIMetadata("clinic_management"),
    "/admin/fertilityclinicuserprofile/edit/": APIMetadata("clinic_management"),
    "/admin/fertilityclinicuserprofile/details/": APIMetadata("clinic_management"),
    "/admin/fertilityclinicuserprofile/delete/": APIMetadata("clinic_management"),
    "/admin/fertilityclinicuserprofile/ajax/update/": APIMetadata("clinic_management"),
    "/admin/fertilityclinicuserprofile/ajax/lookup/": APIMetadata("clinic_management"),
    "/admin/fertilityclinicuserprofile/action/": APIMetadata("clinic_management"),
    "/admin/fertilityclinicuserprofile/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocationemployerhealthplantier/new/": APIMetadata(
        "health_plans"
    ),
    "/admin/fertilitycliniclocationemployerhealthplantier/export/(.+?)/": APIMetadata(
        "health_plans"
    ),
    "/admin/fertilitycliniclocationemployerhealthplantier/edit/": APIMetadata(
        "health_plans"
    ),
    "/admin/fertilitycliniclocationemployerhealthplantier/details/": APIMetadata(
        "health_plans"
    ),
    "/admin/fertilitycliniclocationemployerhealthplantier/delete/": APIMetadata(
        "health_plans"
    ),
    "/admin/fertilitycliniclocationemployerhealthplantier/ajax/update/": APIMetadata(
        "health_plans"
    ),
    "/admin/fertilitycliniclocationemployerhealthplantier/ajax/lookup/": APIMetadata(
        "health_plans"
    ),
    "/admin/fertilitycliniclocationemployerhealthplantier/action/": APIMetadata(
        "health_plans"
    ),
    "/admin/fertilitycliniclocationemployerhealthplantier/": APIMetadata(
        "health_plans"
    ),
    "/admin/fertilitycliniclocationcontact/new/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocationcontact/export/(.+?)/": APIMetadata(
        "clinic_management"
    ),
    "/admin/fertilitycliniclocationcontact/edit/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocationcontact/details/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocationcontact/delete/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocationcontact/ajax/update/": APIMetadata(
        "clinic_management"
    ),
    "/admin/fertilitycliniclocationcontact/ajax/lookup/": APIMetadata(
        "clinic_management"
    ),
    "/admin/fertilitycliniclocationcontact/action/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocationcontact/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocation/new/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocation/export/(.+?)/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocation/edit/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocation/details/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocation/delete/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocation/ajax/update/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocation/ajax/lookup/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocation/action/": APIMetadata("clinic_management"),
    "/admin/fertilitycliniclocation/": APIMetadata("clinic_management"),
    "/admin/fertilityclinic/new/": APIMetadata("clinic_management"),
    "/admin/fertilityclinic/export/(.+?)/": APIMetadata("clinic_management"),
    "/admin/fertilityclinic/edit/": APIMetadata("clinic_management"),
    "/admin/fertilityclinic/details/": APIMetadata("clinic_management"),
    "/admin/fertilityclinic/delete/": APIMetadata("clinic_management"),
    "/admin/fertilityclinic/ajax/update/": APIMetadata("clinic_management"),
    "/admin/fertilityclinic/ajax/lookup/": APIMetadata("clinic_management"),
    "/admin/fertilityclinic/action/": APIMetadata("clinic_management"),
    "/admin/fertilityclinic/": APIMetadata("clinic_management"),
    "/admin/feeschedule/new/": APIMetadata("direct_payment"),
    "/admin/feeschedule/export/(.+?)/": APIMetadata("direct_payment"),
    "/admin/feeschedule/edit/": APIMetadata("direct_payment"),
    "/admin/feeschedule/details/": APIMetadata("direct_payment"),
    "/admin/feeschedule/delete/": APIMetadata("direct_payment"),
    "/admin/feeschedule/ajax/update/": APIMetadata("direct_payment"),
    "/admin/feeschedule/ajax/lookup/": APIMetadata("direct_payment"),
    "/admin/feeschedule/action/": APIMetadata("direct_payment"),
    "/admin/feeschedule/": APIMetadata("direct_payment"),
    "/admin/feeaccountingentry/edit/": APIMetadata("provider_payments"),
    "/admin/feeaccountingentry/ajax/update/": APIMetadata("provider_payments"),
    "/admin/feeaccountingentry/": APIMetadata("provider_payments"),
    "/admin/enrollment/": APIMetadata("enrollments"),
    "/admin/employerhealthplancoverage/new/": APIMetadata("health_plans"),
    "/admin/employerhealthplancoverage/export/(.+?)/": APIMetadata("health_plans"),
    "/admin/employerhealthplancoverage/edit/": APIMetadata("health_plans"),
    "/admin/employerhealthplancoverage/details/": APIMetadata("health_plans"),
    "/admin/employerhealthplancoverage/delete/": APIMetadata("health_plans"),
    "/admin/employerhealthplancoverage/ajax/update/": APIMetadata("health_plans"),
    "/admin/employerhealthplancoverage/ajax/lookup/": APIMetadata("health_plans"),
    "/admin/employerhealthplancoverage/action/": APIMetadata("health_plans"),
    "/admin/employerhealthplancoverage/": APIMetadata("health_plans"),
    "/admin/employerhealthplancostsharing/new/": APIMetadata("wallet_payments"),
    "/admin/employerhealthplancostsharing/export/(.+?)/": APIMetadata(
        "wallet_payments"
    ),
    "/admin/employerhealthplancostsharing/edit/": APIMetadata("wallet_payments"),
    "/admin/employerhealthplancostsharing/details/": APIMetadata("wallet_payments"),
    "/admin/employerhealthplancostsharing/delete/": APIMetadata("wallet_payments"),
    "/admin/employerhealthplancostsharing/ajax/update/": APIMetadata("wallet_payments"),
    "/admin/employerhealthplancostsharing/ajax/lookup/": APIMetadata("wallet_payments"),
    "/admin/employerhealthplancostsharing/action/": APIMetadata("wallet_payments"),
    "/admin/employerhealthplancostsharing/": APIMetadata("wallet_payments"),
    "/admin/employerhealthplan/new/": APIMetadata("health_plans"),
    "/admin/employerhealthplan/export/(.+?)/": APIMetadata("health_plans"),
    "/admin/employerhealthplan/edit/": APIMetadata("health_plans"),
    "/admin/employerhealthplan/details/": APIMetadata("health_plans"),
    "/admin/employerhealthplan/delete/": APIMetadata("health_plans"),
    "/admin/employerhealthplan/ajax/update/": APIMetadata("health_plans"),
    "/admin/employerhealthplan/ajax/lookup/": APIMetadata("health_plans"),
    "/admin/employerhealthplan/action/": APIMetadata("health_plans"),
    "/admin/employerhealthplan/": APIMetadata("health_plans"),
    "/admin/emaildomaindenylist/new/": APIMetadata("authentication"),
    "/admin/emaildomaindenylist/export/(.+?)/": APIMetadata("authentication"),
    "/admin/emaildomaindenylist/edit/": APIMetadata("authentication"),
    "/admin/emaildomaindenylist/details/": APIMetadata("authentication"),
    "/admin/emaildomaindenylist/delete/": APIMetadata("authentication"),
    "/admin/emaildomaindenylist/ajax/update/": APIMetadata("authentication"),
    "/admin/emaildomaindenylist/ajax/lookup/": APIMetadata("authentication"),
    "/admin/emaildomaindenylist/action/": APIMetadata("authentication"),
    "/admin/emaildomaindenylist/": APIMetadata("authentication"),
    "/admin/directpaymentinvoice/new/": APIMetadata("direct_payment_invoice"),
    "/admin/directpaymentinvoice/export/(.+?)/": APIMetadata("direct_payment_invoice"),
    "/admin/directpaymentinvoice/edit/": APIMetadata("direct_payment_invoice"),
    "/admin/directpaymentinvoice/details/": APIMetadata("direct_payment_invoice"),
    "/admin/directpaymentinvoice/delete/": APIMetadata("direct_payment_invoice"),
    "/admin/directpaymentinvoice/ajax/update/": APIMetadata("direct_payment_invoice"),
    "/admin/directpaymentinvoice/ajax/lookup/": APIMetadata("direct_payment_invoice"),
    "/admin/directpaymentinvoice/action/": APIMetadata("direct_payment_invoice"),
    "/admin/directpaymentinvoice/": APIMetadata("direct_payment_invoice"),
    "/admin/direct_payment_tools/wallet_configuration_report": APIMetadata(
        "direct_payment"
    ),
    "/admin/direct_payment_tools": APIMetadata("direct_payment"),
    "/admin/countrycurrencycode/new/": APIMetadata("wallet"),
    "/admin/countrycurrencycode/export/(.+?)/": APIMetadata("wallet"),
    "/admin/countrycurrencycode/edit/": APIMetadata("wallet"),
    "/admin/countrycurrencycode/details/": APIMetadata("wallet"),
    "/admin/countrycurrencycode/delete/": APIMetadata("wallet"),
    "/admin/countrycurrencycode/ajax/update/": APIMetadata("wallet"),
    "/admin/countrycurrencycode/ajax/lookup/": APIMetadata("wallet"),
    "/admin/countrycurrencycode/action/": APIMetadata("wallet"),
    "/admin/countrycurrencycode/": APIMetadata("wallet"),
    "/admin/costbreakdownirsminimumdeductible/new/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdownirsminimumdeductible/export/(.+?)/": APIMetadata(
        "cost_breakdown"
    ),
    "/admin/costbreakdownirsminimumdeductible/edit/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdownirsminimumdeductible/details/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdownirsminimumdeductible/delete/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdownirsminimumdeductible/ajax/update/": APIMetadata(
        "cost_breakdown"
    ),
    "/admin/costbreakdownirsminimumdeductible/ajax/lookup/": APIMetadata(
        "cost_breakdown"
    ),
    "/admin/costbreakdownirsminimumdeductible/action/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdownirsminimumdeductible/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdown/new/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdown/export/(.+?)/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdown/edit/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdown/details/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdown/delete/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdown/ajax/update/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdown/ajax/lookup/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdown/action/": APIMetadata("cost_breakdown"),
    "/admin/costbreakdown/": APIMetadata("cost_breakdown"),
    "/admin/cost_breakdown_calculator/submit": APIMetadata("cost_breakdown"),
    "/admin/cost_breakdown_calculator/procedurelist": APIMetadata("cost_breakdown"),
    "/admin/cost_breakdown_calculator/multipleprocedures/submit": APIMetadata(
        "cost_breakdown"
    ),
    "/admin/cost_breakdown_calculator/linkreimbursement": APIMetadata("cost_breakdown"),
    "/admin/cost_breakdown_calculator/confirm": APIMetadata("cost_breakdown"),
    "/admin/cost_breakdown_calculator/cliniclocationlist": APIMetadata(
        "cost_breakdown"
    ),
    "/admin/cost_breakdown_calculator/check_existing/(.+?)": APIMetadata(
        "cost_breakdown"
    ),
    "/admin/cost_breakdown_calculator/": APIMetadata("cost_breakdown"),
    "/admin/connectedcontentfield/": APIMetadata("content_campaigns"),
    "/admin/clienttrack/details/": APIMetadata("tracks"),
    "/admin/clienttrack/": APIMetadata("tracks"),
    "/admin/categoryversion/": APIMetadata("community_forum"),
    "/admin/category/new/": APIMetadata("community_forum"),
    "/admin/category/edit/": APIMetadata("community_forum"),
    "/admin/category/clear_cache/": APIMetadata("community_forum"),
    "/admin/category/": APIMetadata("community_forum"),
    "/admin/care_team_control_center/global_prep_buffer": APIMetadata(
        "care_advocate_load_balancing"
    ),
    "/admin/care_team_control_center/global_booking_buffer": APIMetadata(
        "care_advocate_load_balancing"
    ),
    "/admin/care_team_control_center": APIMetadata("care_advocate_load_balancing"),
    "/admin/ca_member_transitions/transition_templates": APIMetadata(
        "admin_care_advocate_member_transitions"
    ),
    "/admin/ca_member_transitions/transition_logs": APIMetadata(
        "admin_care_advocate_member_transitions"
    ),
    "/admin/ca_member_transitions/submit": APIMetadata(
        "admin_care_advocate_member_transitions"
    ),
    "/admin/ca_member_transitions/": APIMetadata(
        "admin_care_advocate_member_transitions"
    ),
    "/admin/ca_member_transition_templates/edit/": APIMetadata(
        "admin_care_advocate_member_transitions"
    ),
    "/admin/bmsproduct/new/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsproduct/export/(.+?)/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsproduct/edit/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsproduct/details/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsproduct/delete/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsproduct/ajax/update/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsproduct/ajax/lookup/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsproduct/action/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsproduct/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsorder/new/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsorder/export/(.+?)/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsorder/edit/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsorder/details/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsorder/delete/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsorder/ajax/update/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsorder/ajax/lookup/": APIMetadata("breast_milk_shipping"),
    "/admin/bmsorder/action/": APIMetadata("wallet"),
    "/admin/bmsorder/": APIMetadata("breast_milk_shipping"),
    "/admin/block_list": APIMetadata("authz"),
    "/admin/bill/update_payment_method_on_bill": APIMetadata("billing"),
    "/admin/bill/process_bill": APIMetadata("billing"),
    "/admin/bill/new_clinic": APIMetadata("billing"),
    "/admin/bill/new/": APIMetadata("billing"),
    "/admin/bill/export/(.+?)/": APIMetadata("billing"),
    "/admin/bill/edit/": APIMetadata("billing"),
    "/admin/bill/details/": APIMetadata("billing"),
    "/admin/bill/delete/": APIMetadata("billing"),
    "/admin/bill/create_refund_from_paid_bill": APIMetadata("billing"),
    "/admin/bill/cancel_bill": APIMetadata("billing"),
    "/admin/bill/ajax/update/": APIMetadata("billing"),
    "/admin/bill/ajax/lookup/": APIMetadata("billing"),
    "/admin/bill/action/": APIMetadata("billing"),
    "/admin/bill/": APIMetadata("billing"),
    "/admin/backfill_org_sub_populations": APIMetadata("eligibility"),
    "/admin/auto_practitioner_invite/send": APIMetadata("practitioner_profile"),
    "/admin/authzuserscope/new/": APIMetadata("authz"),
    "/admin/authzuserscope/export/(.+?)/": APIMetadata("authz"),
    "/admin/authzuserscope/edit/": APIMetadata("authz"),
    "/admin/authzuserscope/details/": APIMetadata("authz"),
    "/admin/authzuserscope/delete/": APIMetadata("authz"),
    "/admin/authzuserscope/ajax/update/": APIMetadata("authz"),
    "/admin/authzuserscope/ajax/lookup/": APIMetadata("authz"),
    "/admin/authzuserscope/action/": APIMetadata("authz"),
    "/admin/authzuserscope/": APIMetadata("authz"),
    "/admin/authzuserrole/new/": APIMetadata("authz"),
    "/admin/authzuserrole/export/(.+?)/": APIMetadata("authz"),
    "/admin/authzuserrole/edit/": APIMetadata("authz"),
    "/admin/authzuserrole/details/": APIMetadata("authz"),
    "/admin/authzuserrole/delete/": APIMetadata("authz"),
    "/admin/authzuserrole/ajax/update/": APIMetadata("authz"),
    "/admin/authzuserrole/ajax/lookup/": APIMetadata("authz"),
    "/admin/authzuserrole/action/": APIMetadata("authz"),
    "/admin/authzuserrole/": APIMetadata("authz"),
    "/admin/authzscope/new/": APIMetadata("authz"),
    "/admin/authzscope/export/(.+?)/": APIMetadata("authz"),
    "/admin/authzscope/edit/": APIMetadata("authz"),
    "/admin/authzscope/details/": APIMetadata("authz"),
    "/admin/authzscope/delete/": APIMetadata("authz"),
    "/admin/authzscope/ajax/update/": APIMetadata("authz"),
    "/admin/authzscope/ajax/lookup/": APIMetadata("authz"),
    "/admin/authzscope/action/": APIMetadata("authz"),
    "/admin/authzscope/": APIMetadata("authz"),
    "/admin/authzrolepermission/new/": APIMetadata("authz"),
    "/admin/authzrolepermission/export/(.+?)/": APIMetadata("authz"),
    "/admin/authzrolepermission/edit/": APIMetadata("authz"),
    "/admin/authzrolepermission/details/": APIMetadata("authz"),
    "/admin/authzrolepermission/delete/": APIMetadata("authz"),
    "/admin/authzrolepermission/ajax/update/": APIMetadata("authz"),
    "/admin/authzrolepermission/ajax/lookup/": APIMetadata("authz"),
    "/admin/authzrolepermission/action/": APIMetadata("authz"),
    "/admin/authzrolepermission/": APIMetadata("authz"),
    "/admin/authzrole/new/": APIMetadata("authz"),
    "/admin/authzrole/export/(.+?)/": APIMetadata("authz"),
    "/admin/authzrole/edit/": APIMetadata("authz"),
    "/admin/authzrole/details/": APIMetadata("authz"),
    "/admin/authzrole/delete/": APIMetadata("authz"),
    "/admin/authzrole/ajax/update/": APIMetadata("authz"),
    "/admin/authzrole/ajax/lookup/": APIMetadata("authz"),
    "/admin/authzrole/action/": APIMetadata("authz"),
    "/admin/authzrole/": APIMetadata("authz"),
    "/admin/authzpermission/new/": APIMetadata("authz"),
    "/admin/authzpermission/export/(.+?)/": APIMetadata("authz"),
    "/admin/authzpermission/edit/": APIMetadata("authz"),
    "/admin/authzpermission/details/": APIMetadata("authz"),
    "/admin/authzpermission/delete/": APIMetadata("authz"),
    "/admin/authzpermission/ajax/update/": APIMetadata("authz"),
    "/admin/authzpermission/ajax/lookup/": APIMetadata("authz"),
    "/admin/authzpermission/action/": APIMetadata("authz"),
    "/admin/authzpermission/": APIMetadata("authz"),
    "/admin/authz_bulk_insert": APIMetadata("authz"),
    "/admin/asyncencountersummary/new/": APIMetadata(
        "mpractice_clinical_documentation"
    ),
    "/admin/asyncencountersummary/export/(.+?)/": APIMetadata(
        "mpractice_clinical_documentation"
    ),
    "/admin/asyncencountersummary/edit/": APIMetadata(
        "mpractice_clinical_documentation"
    ),
    "/admin/asyncencountersummary/details/": APIMetadata(
        "mpractice_clinical_documentation"
    ),
    "/admin/asyncencountersummary/delete/": APIMetadata(
        "mpractice_clinical_documentation"
    ),
    "/admin/asyncencountersummary/ajax/update/": APIMetadata(
        "mpractice_clinical_documentation"
    ),
    "/admin/asyncencountersummary/ajax/lookup/": APIMetadata(
        "mpractice_clinical_documentation"
    ),
    "/admin/asyncencountersummary/action/": APIMetadata(
        "mpractice_clinical_documentation"
    ),
    "/admin/asyncencountersummary/": APIMetadata("mpractice_clinical_documentation"),
    "/admin/assignableadvocate/new/": APIMetadata("care_advocate_load_balancing"),
    "/admin/assignableadvocate/edit/": APIMetadata("care_advocate_load_balancing"),
    "/admin/assignableadvocate/": APIMetadata("care_advocate_load_balancing"),
    "/admin/assessmenttrack/new/": APIMetadata("assessments"),
    "/admin/assessmenttrack/": APIMetadata("assessments"),
    "/admin/assessmentlifecycle/": APIMetadata("assessments"),
    "/admin/assessment/new/": APIMetadata("assessments"),
    "/admin/assessment/edit/": APIMetadata("assessments"),
    "/admin/assessment/": APIMetadata("assessments"),
    "/admin/appointmentmetadata/new/": APIMetadata("mpractice_clinical_documentation"),
    "/admin/appointmentmetadata/edit/": APIMetadata("mpractice_clinical_documentation"),
    "/admin/appointmentmetadata/": APIMetadata("mpractice_clinical_documentation"),
    "/admin/appointmentfeecreator/": APIMetadata("provider_payments"),
    "/admin/annualinsurancequestionnaireresponse/new/": APIMetadata("wallet"),
    "/admin/annualinsurancequestionnaireresponse/export/(.+?)/": APIMetadata("wallet"),
    "/admin/annualinsurancequestionnaireresponse/edit/": APIMetadata("wallet"),
    "/admin/annualinsurancequestionnaireresponse/details/": APIMetadata("wallet"),
    "/admin/annualinsurancequestionnaireresponse/delete/": APIMetadata("wallet"),
    "/admin/annualinsurancequestionnaireresponse/ajax/update/": APIMetadata("wallet"),
    "/admin/annualinsurancequestionnaireresponse/ajax/lookup/": APIMetadata("wallet"),
    "/admin/annualinsurancequestionnaireresponse/action/": APIMetadata("wallet"),
    "/admin/annualinsurancequestionnaireresponse/": APIMetadata("wallet"),
    "/admin/allowedlist/new/": APIMetadata("authz"),
    "/admin/allowedlist/export/(.+?)/": APIMetadata("authz"),
    "/admin/allowedlist/edit/": APIMetadata("authz"),
    "/admin/allowedlist/details/": APIMetadata("authz"),
    "/admin/allowedlist/delete/": APIMetadata("authz"),
    "/admin/allowedlist/ajax/update/": APIMetadata("authz"),
    "/admin/allowedlist/ajax/lookup/": APIMetadata("authz"),
    "/admin/allowedlist/action/": APIMetadata("authz"),
    "/admin/allowedlist/": APIMetadata("authz"),
    "/admin/agreement/": APIMetadata("agreements"),
    "/admin/actions/tracks/transition": APIMetadata("tracks"),
    "/admin/actions/set_practitioner_prescription_info": APIMetadata("prescriptions"),
    "/admin/actions/process_bms_orders/": APIMetadata("breast_milk_shipping"),
    "/admin/actions/proactive_booking": APIMetadata("booking_flow"),
    "/admin/actions/get_affected_appointments": APIMetadata("appointments"),
    "/admin/actions/delete_user_permanently": APIMetadata("core_services"),
    "/admin/accumulationtreatmentmapping/new/": APIMetadata("payer_accumulation"),
    "/admin/accumulationtreatmentmapping/export/(.+?)/": APIMetadata(
        "payer_accumulation"
    ),
    "/admin/accumulationtreatmentmapping/edit/": APIMetadata("payer_accumulation"),
    "/admin/accumulationtreatmentmapping/details/": APIMetadata("payer_accumulation"),
    "/admin/accumulationtreatmentmapping/delete/": APIMetadata("payer_accumulation"),
    "/admin/accumulationtreatmentmapping/ajax/update/": APIMetadata(
        "payer_accumulation"
    ),
    "/admin/accumulationtreatmentmapping/ajax/lookup/": APIMetadata(
        "payer_accumulation"
    ),
    "/admin/accumulationtreatmentmapping/action/": APIMetadata("payer_accumulation"),
    "/admin/accumulationtreatmentmapping/": APIMetadata("payer_accumulation"),
}

# Metadata list for possible workflows
workflow_metadata_list = {
    # Member registers and confirms eligibility (Enrollments Flow)
    "register_and_confirm_eligibility",
    # Member selects a track (Onboarding Flow Audit)
    "select_track",
    # Member goes through onboarding (Onboarding Flow Audit)
    "onboarding",
    # Member active log in (Enrollments Audit)
    "active_login",
    # Member passive log in
    "passive_login",
    # Member accesses the homepage
    "member_accesses_homepage",
    # Member books provider video appointment (Booking Flow Audit)
    "member_books_video_appointment",
    # Member and provider have video appointment (Video Call Audit)
    "video_appointment",
    # Member and CA/CSR send messages (Messaging Audit)
    "send_messages_ca",
    # Member and Provider send messages
    "send_messages_provider",
    # Member engages with their care plan (Care Plan Audit)
    "member_engage_with_care_plan",
    # Care Advocate prepares for and conducts an appointment
    "care_advocate_perps_appt",
    # Member accesses Learn, reads article and saves
    "member_accesses_learn",
    # Member accesses Forums, navigates to program and reads posts
    "member_accesses_forums",
    # Member takes check-in, transition, or off-boarding assessment
    "member_takes_assessment",
    # Member accesses health profile
    "member_accesses_health_profile",
    # Member accesses Wallet dashboard
    "member_access_wallet",
    # Clinic user accesses clinic portal
    "clinic_user_accesses_portal",
}

# NOTE: endpoint_service mappers are sorted in reverse order to ensure stricter matching
api_endpoint_service_ns_mapper = {
    "/saml/consume/complete": APIMetadata(
        "authentication", APIPriority.P1, ["active_login"]
    ),
    "/saml/consume/begin": APIMetadata("authentication"),
    "/saml/consume/": APIMetadata("authentication"),
    "/join/(.+?)": APIMetadata("enrollments"),
    "/api/v2/video/session/(.+?)/token": APIMetadata("video"),
    "/api/v2/video/session": APIMetadata("video"),
    "/api/v2/users/(.+?)/patient_health_record": APIMetadata("health"),
    "/api/v2/pharmacies/search": APIMetadata("prescriptions"),
    "/api/v2/mpractice/appointments": APIMetadata(
        "mpractice_appointment",
        APIPriority.P1,
        ["video_appointment", "care_advocate_perps_appt"],
    ),
    "/api/v2/mpractice/appointment/(.+?)": APIMetadata(
        "mpractice_appointment",
        APIPriority.P1,
        ["video_appointment", "care_advocate_perps_appt"],
    ),
    "/api/v2/member/appointments/(.+?)/video_timestamp": APIMetadata("appointments"),
    "/api/v2/member/appointments/(.+?)/cancel": APIMetadata("appointments"),
    "/api/v2/member/appointments/(.+?)": APIMetadata("appointments"),
    "/api/v2/member/appointments": APIMetadata("appointments", APIPriority.P1),
    "/api/v2/clinical_documentation/structured_internal_notes": APIMetadata(
        "clinical_documentation", APIPriority.P1, ["care_advocate_perps_appt"]
    ),
    "/api/v2/clinical_documentation/questionnaire_answers": APIMetadata("appointments"),
    "/api/v2/clinical_documentation/provider_addenda": APIMetadata(
        "clinical_documentation", APIPriority.P1, ["care_advocate_perps_appt"]
    ),
    "/api/v2/clinical_documentation/post_appointment_notes": APIMetadata(
        "clinical_documentation", APIPriority.P1, ["care_advocate_perps_appt"]
    ),
    # this will be owned by clinical_documentation in the future
    "/api/v2/clinical_documentation/member_questionnaires": APIMetadata("appointments"),
    "/api/v2/appointments/reserve_payment_or_credits": APIMetadata("appointments"),
    "/api/v2/appointments/process_payments_for_cancel": APIMetadata("appointments"),
    "/api/v2/appointments/complete_payment": APIMetadata("appointments"),
    "/api/v2/appointments/(.+?)/video_timestamp": APIMetadata("appointments"),
    "/api/v2/appointments/(.+?)/cancel": APIMetadata("appointments"),
    "/api/v2/_/vertical_groupings": APIMetadata("booking_flow"),
    "/api/v1/zendesk/authentication": APIMetadata("messaging_system"),
    "/api/v1/webhook/health_data_collection": APIMetadata("health"),
    "/api/v1/virtual_events/(.+?)/user_registration": APIMetadata("learn"),
    "/api/v1/virtual_events/(.+?)": APIMetadata(
        "learn", APIPriority.NONE, ["member_accesses_learn"]
    ),
    "/api/v1/video/session/(.+?)/token": APIMetadata("video", APIPriority.P3),
    "/api/v1/video/session": APIMetadata("video", APIPriority.P3),
    "/api/v1/video/report_problem": APIMetadata("video", APIPriority.P3),
    "/api/v1/video/connection/(.+?)/heartbeat": APIMetadata("video", APIPriority.P1),
    "/api/v1/verticals-specialties": APIMetadata("booking_flow"),
    "/api/v1/verticals": APIMetadata("booking_flow"),
    "/api/v1/vendor/zendesk/message": APIMetadata("messaging_system"),
    "/api/v1/vendor/twilio/sms": APIMetadata(
        "appointment_notifications", APIPriority.P2
    ),
    "/api/v1/vendor/twilio/message_status": APIMetadata(
        "messaging_system", APIPriority.P2
    ),
    "/api/v1/vendor/surveymonkey/survey-completed-webhook": APIMetadata("wallet"),
    "/api/v1/vendor/stripe/webhooks": APIMetadata("provider_payments"),
    "/api/v1/vendor/stripe/reimbursements-webhook": APIMetadata("provider_payments"),
    "/api/v1/vendor/braze/connected_event_properties/(.+?)": APIMetadata("braze"),
    "/api/v1/vendor/braze/connected_content": APIMetadata("braze"),
    "/api/v1/vendor/braze/bulk_messaging": APIMetadata("messaging_system"),
    "/api/v1/users/verification_email": APIMetadata("authentication"),
    "/api/v1/users/start_delete_request/(.+?)": APIMetadata("core_services"),
    "/api/v1/users/sso_user_creation": APIMetadata(
        "authentication", APIPriority.NONE, ["register_and_confirm_eligibility"]
    ),
    "/api/v1/users/sso_relink": APIMetadata("authentication"),
    "/api/v1/users/restore/(.+?)": APIMetadata("core_services"),
    "/api/v1/users/profiles/practitioner": APIMetadata("practitioner_profile"),
    "/api/v1/users/profiles/member": APIMetadata("member_profile", APIPriority.P1),
    "/api/v1/users/me": APIMetadata("member_profile", APIPriority.P1),
    "/api/v1/users/(.+?)/setup": APIMetadata("authentication"),
    "/api/v1/users/(.+?)/recorded_answer_sets/(.+?)": APIMetadata("health"),
    "/api/v1/users/(.+?)/recorded_answer_sets": APIMetadata("health"),
    "/api/v1/users/(.+?)/recipient_information": APIMetadata("provider_payments"),
    "/api/v1/users/(.+?)/profiles/practitioner": APIMetadata("practitioner_profile"),
    "/api/v1/users/(.+?)/profiles/member": APIMetadata(
        "member_profile", APIPriority.P1, ["register_and_confirm_eligibility"]
    ),
    "/api/v1/users/(.+?)/pregnancy_and_related_conditions": APIMetadata("health"),
    "/api/v1/users/(.+?)/preferences": APIMetadata("member_profile", APIPriority.P1),
    "/api/v1/users/(.+?)/payment_methods/(.+?)": APIMetadata("wallet"),
    "/api/v1/users/(.+?)/payment_methods": APIMetadata("wallet"),
    "/api/v1/users/(.+?)/patient_profile": APIMetadata("member_care"),
    "/api/v1/users/(.+?)/patient_health_record": APIMetadata("health"),
    "/api/v1/users/(.+?)/password_reset": APIMetadata("login"),
    "/api/v1/users/(.+?)/organizations": APIMetadata(
        "tracks", APIPriority.P1, ["select_track"]
    ),
    "/api/v1/users/(.+?)/organization_employee": APIMetadata("eligibility"),
    "/api/v1/users/(.+?)/onboarding_state": APIMetadata("onboarding"),
    "/api/v1/users/(.+?)/notes": APIMetadata("clinical_documentation"),
    "/api/v1/users/(.+?)/my_patients": APIMetadata("clinical_documentation"),
    "/api/v1/users/(.+?)/member_communications/unsubscribe": APIMetadata(
        "account_settings"
    ),
    "/api/v1/users/(.+?)/member_communications/opt_in": APIMetadata("account_settings"),
    "/api/v1/users/(.+?)/member_communications": APIMetadata(
        "account_settings", APIPriority.P1, ["register_and_confirm_eligibility"]
    ),
    "/api/v1/users/(.+?)/locale": APIMetadata("user_locale"),
    "/api/v1/users/(.+?)/invite_partner_enabled": APIMetadata("enrollments"),
    "/api/v1/users/(.+?)/incentive": APIMetadata(
        "incentive", APIPriority.NONE, ["onboarding"]
    ),
    "/api/v1/users/(.+?)/health_profile": APIMetadata(
        "health",
        APIPriority.P2,
        [
            "register_and_confirm_eligibility",
            "select_track",
            "member_accesses_health_profile",
        ],
    ),
    "/api/v1/users/(.+?)/email_confirm": APIMetadata("authentication"),
    "/api/v1/users/(.+?)/devices": APIMetadata("appointment_notifications"),
    "/api/v1/users/(.+?)/credits": APIMetadata("wallet"),
    "/api/v1/users/(.+?)/courses": APIMetadata("learn"),
    "/api/v1/users/(.+?)/care_team/(.+?)": APIMetadata("care_team"),
    "/api/v1/users/(.+?)/care_team": APIMetadata(
        "care_team", APIPriority.P2, ["member_books_video_appointment"]
    ),
    "/api/v1/users/(.+?)/bank_accounts": APIMetadata("wallet"),
    "/api/v1/users/(.+?)/assessments/(.+?)": APIMetadata("assessments"),
    "/api/v1/users/(.+?)/assessments": APIMetadata("assessments"),
    "/api/v1/users/(.+?)/assessment_answers": APIMetadata("assessments"),
    "/api/v1/users/(.+?)/address": APIMetadata("prescriptions"),
    "/api/v1/users/(.+?)": APIMetadata(
        "authentication", APIPriority.NONE, ["register_and_confirm_eligibility"]
    ),
    "/api/v1/users": APIMetadata(
        "authentication", APIPriority.NONE, ["register_and_confirm_eligibility"]
    ),
    "/api/v1/unauthenticated/sms": APIMetadata("messaging_system"),
    "/api/v1/unauthenticated/gifting": APIMetadata("provider_payments"),
    "/api/v1/tracks/scheduled": APIMetadata("tracks"),
    "/api/v1/tracks/intro_appointment_eligibility": APIMetadata("tracks"),
    "/api/v1/tracks/inactive": APIMetadata("tracks"),
    "/api/v1/tracks/active": APIMetadata("tracks"),
    "/api/v1/tracks/(.+?)/start-transition": APIMetadata("tracks"),
    "/api/v1/tracks/(.+?)/scheduled": APIMetadata("tracks"),
    "/api/v1/tracks/(.+?)/renewal": APIMetadata("tracks"),
    "/api/v1/tracks/(.+?)/onboarding_assessment": APIMetadata("tracks"),
    "/api/v1/tracks/(.+?)/finish-transition": APIMetadata("tracks"),
    "/api/v1/tracks/(.+?)/cancel-transition": APIMetadata("tracks"),
    "/api/v1/tracks": APIMetadata("tracks"),
    "/api/v1/tags": APIMetadata("learn", APIPriority.P2),
    "/api/v1/search/(.+?)/click": APIMetadata("learn"),
    "/api/v1/search/(.+?)": APIMetadata("learn", APIPriority.P2),
    "/api/v1/risk-flags/member/(.+?)": APIMetadata("mpractice_core"),
    "/api/v1/resources": APIMetadata(
        "learn", APIPriority.P2, ["member_accesses_learn"]
    ),
    "/api/v1/reimbursement_wallets/(.+?)/upcoming_transactions": APIMetadata("wallet"),
    "/api/v1/reimbursement_wallets/(.+?)/insurance/annual_questionnaire/needs_survey": APIMetadata(
        "wallet", APIPriority.P1
    ),
    "/api/v1/reimbursement_wallets/(.+?)/insurance/annual_questionnaire/clinic_portal/needs_survey": APIMetadata(
        "wallet", APIPriority.P1
    ),
    "/api/v1/reimbursement_wallets/(.+?)/insurance/annual_questionnaire": APIMetadata(
        "wallet", APIPriority.P1
    ),
    "/api/v1/reimbursement_wallets/(.+?)/debit_card/lost_stolen": APIMetadata("wallet"),
    "/api/v1/reimbursement_wallets/(.+?)/debit_card": APIMetadata(
        "wallet", APIPriority.P1
    ),
    "/api/v1/reimbursement_wallets/(.+?)/bank_account": APIMetadata(
        "wallet", APIPriority.P1, ["member_access_wallet"]
    ),
    "/api/v1/reimbursement_wallet/state": APIMetadata("wallet", APIPriority.P1),
    "/api/v1/reimbursement_wallet/invitation/(.+?)": APIMetadata(
        "wallet", APIPriority.P1
    ),
    "/api/v1/reimbursement_wallet/dashboard": APIMetadata("wallet", APIPriority.P1),
    "/api/v1/reimbursement_wallet/available_currencies": APIMetadata(
        "wallet", APIPriority.P1
    ),
    "/api/v1/reimbursement_wallet/(.+?)/users": APIMetadata("wallet"),
    "/api/v1/reimbursement_wallet/(.+?)/add_user": APIMetadata("wallet"),
    "/api/v1/reimbursement_wallet/(.+?)": APIMetadata("wallet", APIPriority.P1),
    "/api/v1/reimbursement_wallet": APIMetadata(
        "wallet", APIPriority.P1, ["member_access_wallet"]
    ),
    "/api/v1/reimbursement_request/state": APIMetadata("wallet", APIPriority.P1),
    "/api/v1/reimbursement_request/(.+?)/sources": APIMetadata(
        "wallet", APIPriority.P1, ["member_access_wallet"]
    ),
    "/api/v1/reimbursement_request/(.+?)": APIMetadata(
        "wallet", APIPriority.P1, ["member_access_wallet"]
    ),
    "/api/v1/reimbursement_request": APIMetadata(
        "wallet", APIPriority.P1, ["member_access_wallet"]
    ),
    "/api/v1/referral_codes": APIMetadata("booking_flow"),
    "/api/v1/referral_code_uses": APIMetadata("booking_flow"),
    "/api/v1/referral_code_info": APIMetadata("booking_flow"),
    "/api/v1/questionnaires": APIMetadata("health"),
    "/api/v1/providers/messageable_providers": APIMetadata("booking_flow"),
    "/api/v1/providers/languages": APIMetadata("booking_flow"),
    "/api/v1/providers/(.+?)/profile": APIMetadata(
        "booking_flow", APIPriority.P2, ["member_books_video_appointment"]
    ),
    "/api/v1/providers": APIMetadata(
        "booking_flow", APIPriority.P1, ["member_books_video_appointment"]
    ),
    "/api/v1/promoted_needs": APIMetadata("booking_flow"),
    "/api/v1/products/(.+?)/availability": APIMetadata("booking_flow"),
    "/api/v1/products": APIMetadata("booking_flow"),
    "/api/v1/prescriptions/pharmacy_search/(.+?)": APIMetadata("prescriptions"),
    "/api/v1/prescriptions/patient_details/(.+?)": APIMetadata(
        "prescriptions", APIPriority.P2, ["video_appointment"]
    ),
    "/api/v1/prescriptions/errors/(.+?)": APIMetadata("prescriptions"),
    "/api/v1/pregnancy_and_related_conditions/(.+?)": APIMetadata("health"),
    "/api/v1/practitioners/dates_available": APIMetadata("booking_flow"),
    "/api/v1/practitioners/availabilities": APIMetadata(
        "booking_flow", APIPriority.P1, ["member_books_video_appointment"]
    ),
    "/api/v1/practitioners/(.+?)/schedules/recurring_blocks/(.+?)": APIMetadata(
        "provider_availability", APIPriority.P1, ["care_advocate_perps_appt"]
    ),
    "/api/v1/practitioners/(.+?)/schedules/recurring_blocks": APIMetadata(
        "provider_availability", APIPriority.P1, ["care_advocate_perps_appt"]
    ),
    "/api/v1/practitioners/(.+?)/schedules/events/(.+?)": APIMetadata(
        "provider_availability",
        APIPriority.P1,
        ["member_books_video_appointment", "care_advocate_perps_appt"],
    ),
    "/api/v1/practitioners/(.+?)/schedules/events": APIMetadata(
        "provider_availability",
        APIPriority.P1,
        ["member_books_video_appointment", "care_advocate_perps_appt"],
    ),
    "/api/v1/practitioners": APIMetadata("booking_flow"),
    "/api/v1/posts/(.+?)/bookmarks": APIMetadata(
        "community_forum", APIPriority.P3, ["member_accesses_forums"]
    ),
    "/api/v1/posts/(.+?)": APIMetadata(
        "community_forum", APIPriority.P3, ["member_accesses_forums"]
    ),
    "/api/v1/posts": APIMetadata(
        "community_forum", APIPriority.P3, ["member_accesses_forums"]
    ),
    "/api/v1/pharmacy_search": APIMetadata("prescriptions"),
    "/api/v1/overflow_report": APIMetadata("appointments"),
    "/api/v1/organizations/search": APIMetadata(
        "enrollments", APIPriority.P2, ["register_and_confirm_eligibility"]
    ),
    "/api/v1/organizations/(.+?)": APIMetadata("enrollments", APIPriority.P2),
    "/api/v1/organizations": APIMetadata(
        "enrollments", APIPriority.P2, ["register_and_confirm_eligibility"]
    ),
    "/api/v1/organization/(.+?)/inbound_phone_number": APIMetadata("virtual_care"),
    "/api/v1/oauth/token/validate": APIMetadata("authentication"),
    "/api/v1/oauth/token/revoke": APIMetadata("authentication"),
    "/api/v1/oauth/token/refresh": APIMetadata(
        "authentication", APIPriority.NONE, ["passive_login"]
    ),
    "/api/v1/oauth/token": APIMetadata(
        "authentication",
        APIPriority.P1,
        [
            "register_and_confirm_eligibility",
            "active_login",
            "care_advocate_perps_appt",
            "clinic_user_accesses_portal",
        ],
    ),
    "/api/v1/oauth/signup": APIMetadata("authentication"),
    "/api/v1/oauth/logout": APIMetadata("authentication"),
    "/api/v1/oauth/authorize": APIMetadata("authentication"),
    "/api/v1/needs": APIMetadata("booking_flow"),
    "/api/v1/mpractice/appointments": APIMetadata("mpractice_appointment"),
    "/api/v1/mpractice/appointment/(.+?)": APIMetadata("mpractice_appointment"),
    "/api/v1/mfa/verify": APIMetadata(
        "authentication", APIPriority.P1, ["active_login"]
    ),
    "/api/v1/mfa/resend_code": APIMetadata(
        "authentication", APIPriority.P1, ["active_login"]
    ),
    "/api/v1/mfa/remove": APIMetadata("authentication"),
    "/api/v1/mfa/force_enroll": APIMetadata("authentication"),
    "/api/v1/mfa/enroll": APIMetadata("authentication"),
    "/api/v1/mfa/enforcement": APIMetadata("authentication"),
    "/api/v1/mfa/company_mfa_sync": APIMetadata("authentication"),
    "/api/v1/message/products": APIMetadata(
        "messaging_system", APIPriority.P1, ["send_messages_provider"]
    ),
    "/api/v1/message/notifications_consent": APIMetadata(
        "messaging_system", APIPriority.P3
    ),
    "/api/v1/message/billing": APIMetadata(
        "messaging_system", APIPriority.P1, ["send_messages_provider"]
    ),
    "/api/v1/message/(.+?)/acknowledgement": APIMetadata("messaging_system"),
    "/api/v1/message/(.+?)": APIMetadata("messaging_system"),
    "/api/v1/members/search": APIMetadata(
        "mpractice_member_search_n_profile", APIPriority.P2, ["send_messages_ca"]
    ),
    "/api/v1/members/(.+?)/async_encounter_summaries": APIMetadata(
        "clinical_documentation"
    ),
    "/api/v1/members/(.+?)": APIMetadata("mpractice_member_search_n_profile"),
    "/api/v1/me/bookmarks": APIMetadata("community_forum", APIPriority.P3),
    "/api/v1/me": APIMetadata(
        "member_profile",
        APIPriority.P1,
        ["register_and_confirm_eligibility", "select_track"],
    ),
    "/api/v1/library/virtual_events/(.+?)": APIMetadata(
        "learn", APIPriority.P2, ["member_accesses_learn"]
    ),
    "/api/v1/library/on_demand_classes/(.+?)": APIMetadata(
        "learn", APIPriority.P2, ["member_accesses_learn"]
    ),
    "/api/v1/library/courses/(.+?)/member_statuses/(.+?)": APIMetadata("learn"),
    "/api/v1/library/courses/(.+?)/member_statuses": APIMetadata("learn"),
    "/api/v1/library/courses/(.+?)": APIMetadata("learn", APIPriority.P2),
    "/api/v1/library/courses": APIMetadata("learn", APIPriority.P2),
    "/api/v1/library/contentful/webhook": APIMetadata("learn"),
    "/api/v1/library/bookmarks/(.+?)": APIMetadata("learn"),
    "/api/v1/library/bookmarks": APIMetadata(
        "learn", APIPriority.NONE, ["member_accesses_learn"]
    ),
    "/api/v1/library/(.+?)": APIMetadata(
        "learn", APIPriority.P2, ["member_accesses_learn"]
    ),
    "/api/v1/launchdarkly_context": APIMetadata("feature_flags"),
    "/api/v1/invite/unclaimed": APIMetadata(
        "enrollments", APIPriority.NONE, ["register_and_confirm_eligibility"]
    ),
    "/api/v1/invite/(.+?)": APIMetadata("enrollments"),
    "/api/v1/invite": APIMetadata("enrollments"),
    "/api/v1/images/(.+?)/(.+?)": APIMetadata("member_profile"),
    "/api/v1/images/(.+?)": APIMetadata("member_profile"),
    "/api/v1/images": APIMetadata("member_profile"),
    "/api/v1/forums/categories": APIMetadata("community_forum", APIPriority.P3),
    "/api/v1/fileless_invite/claim": APIMetadata(
        "enrollments", APIPriority.P2, ["register_and_confirm_eligibility"]
    ),
    "/api/v1/fileless_invite": APIMetadata(
        "enrollments", APIPriority.P2, ["register_and_confirm_eligibility"]
    ),
    "/api/v1/features": APIMetadata(
        "tracks", APIPriority.P1, ["register_and_confirm_eligibility"]
    ),
    "/api/v1/direct_payment/treatment_procedure_questionnaires": APIMetadata(
        "clinic_portal"
    ),
    "/api/v1/direct_payment/treatment_procedure/member/(.+?)": APIMetadata(
        "treatment_procedure", APIPriority.NONE, ["clinic_user_accesses_portal"]
    ),
    "/api/v1/direct_payment/treatment_procedure/(.+?)": APIMetadata(
        "treatment_procedure"
    ),
    "/api/v1/direct_payment/treatment_procedure": APIMetadata(
        "treatment_procedure", APIPriority.NONE, ["clinic_user_accesses_portal"]
    ),
    "/api/v1/direct_payment/payments/reimbursement_wallet/estimates/(.+?)": APIMetadata(
        "direct_payment", APIPriority.P1
    ),
    "/api/v1/direct_payment/payments/reimbursement_wallet/(.+?)": APIMetadata(
        "direct_payment"
    ),
    "/api/v1/direct_payment/payments/estimate/(.+?)/detail": APIMetadata(
        "direct_payment"
    ),
    "/api/v1/direct_payment/payments/bill/(.+?)/detail": APIMetadata(
        "direct_payment", APIPriority.P1
    ),
    "/api/v1/direct_payment/notification/ingest_payment_gateway_event": APIMetadata(
        "direct_payment"
    ),
    "/api/v1/direct_payment/general/articles/(.+?)": APIMetadata("direct_payment"),
    "/api/v1/direct_payment/fertility_clinic_portal_help/articles/(.+?)": APIMetadata(
        "clinic_portal"
    ),
    "/api/v1/direct_payment/fertility_clinic_portal_help/articles": APIMetadata(
        "clinic_portal"
    ),
    "/api/v1/direct_payment/clinic/treatment_procedures": APIMetadata("clinic_portal"),
    "/api/v1/direct_payment/clinic/member-lookup": APIMetadata("direct_payment"),
    "/api/v1/direct_payment/clinic/me": APIMetadata("clinic_portal"),
    "/api/v1/direct_payment/clinic/fertility_clinics/(.+?)/procedures": APIMetadata(
        "clinic_portal"
    ),
    "/api/v1/direct_payment/clinic/fertility_clinics/(.+?)": APIMetadata(
        "clinic_portal"
    ),
    "/api/v1/direct_payment/clinic/check_access": APIMetadata("clinic_portal"),
    "/api/v1/direct_payment/billing_consent/reimbursement_wallet/(.+?)": APIMetadata(
        "billing"
    ),
    "/api/v1/direct_payment/billing/ingest_payment_gateway_event": APIMetadata(
        "billing"
    ),
    "/api/v1/direct_payment/billing/bill/(.+?)": APIMetadata("billing"),
    "/api/v1/direct_payment/benefits_experience_help/articles/(.+?)": APIMetadata(
        "clinic_portal"
    ),
    "/api/v1/direct_payment/benefits_experience_help/articles": APIMetadata(
        "clinic_portal"
    ),
    "/api/v1/dashboard-metadata/track/(.+?)": APIMetadata(
        "dashboard_metadata",
        APIPriority.NONE,
        ["member_accesses_homepage", "member_engage_with_care_plan"],
    ),
    "/api/v1/dashboard-metadata/practitioner": APIMetadata("dashboard_metadata"),
    "/api/v1/dashboard-metadata/personalization-flags": APIMetadata(
        "dashboard_metadata"
    ),
    "/api/v1/dashboard-metadata/marketplace": APIMetadata(
        "dashboard_metadata", APIPriority.NONE, ["member_accesses_homepage"]
    ),
    "/api/v1/dashboard-metadata/expired-track/(.+?)": APIMetadata(
        "dashboard_metadata", APIPriority.NONE, ["member_accesses_homepage"]
    ),
    "/api/v1/dashboard-metadata/assessment": APIMetadata("dashboard_metadata"),
    "/api/v1/dashboard-metadata": APIMetadata("dashboard_metadata"),
    "/api/v1/cypress_utils/providers/(.+?)": APIMetadata("appointments"),
    "/api/v1/cypress_utils/providers": APIMetadata("appointments"),
    "/api/v1/create_e9y_test_members_for_organization": APIMetadata("eligibility"),
    "/api/v1/content/resources/public/(.+?)": APIMetadata(
        "learn", APIPriority.P2, ["member_accesses_learn"]
    ),
    "/api/v1/content/resources/private/(.+?)": APIMetadata(
        "learn", APIPriority.NONE, ["member_accesses_learn"]
    ),
    "/api/v1/content/resources/metadata/(.+?)": APIMetadata(
        "learn", APIPriority.NONE, ["member_accesses_learn"]
    ),
    "/api/v1/content/resources/metadata": APIMetadata(
        "learn", APIPriority.NONE, ["member_accesses_learn"]
    ),
    "/api/v1/clinical_documentation/templates/(.+?)": APIMetadata(
        "clinical_documentation"
    ),
    "/api/v1/clinical_documentation/templates": APIMetadata("clinical_documentation"),
    "/api/v1/channels/unread": APIMetadata("messaging_system"),
    "/api/v1/channels": APIMetadata(
        "messaging_system", APIPriority.P1, ["send_messages_provider"]
    ),
    "/api/v1/channel/(.+?)/status": APIMetadata(
        "messaging_system", APIPriority.P1, ["send_messages_ca"]
    ),
    "/api/v1/channel/(.+?)/participants": APIMetadata("messaging_system"),
    "/api/v1/channel/(.+?)/messages": APIMetadata(
        "messaging_system",
        APIPriority.P1,
        ["send_messages_ca", "send_messages_provider"],
    ),
    "/api/v1/categories": APIMetadata(
        "community_forum", APIPriority.P3, ["member_accesses_forums"]
    ),
    "/api/v1/care_coaching_eligibility": APIMetadata("onboarding"),
    "/api/v1/care_advocates/search": APIMetadata(
        "care_advocate_member_matching", APIPriority.NONE, ["onboarding"]
    ),
    "/api/v1/care_advocates/pooled_availability": APIMetadata(
        "care_advocate_member_matching", APIPriority.NONE, ["onboarding"]
    ),
    "/api/v1/care_advocates/assign": APIMetadata(
        "care_advocate_member_matching", APIPriority.NONE, ["onboarding"]
    ),
    "/api/v1/care-team-assignment/reassign/(.+?)": APIMetadata(
        "care_advocate_member_matching"
    ),
    "/api/v1/braze_attachment": APIMetadata("braze"),
    "/api/v1/booking_flow_data": APIMetadata("booking_flow"),
    "/api/v1/booking_flow_availability": APIMetadata("booking_flow"),
    "/api/v1/booking_flow/search": APIMetadata(
        "booking_flow", APIPriority.P1, ["member_books_video_appointment"]
    ),
    "/api/v1/booking_flow/categories": APIMetadata("booking_flow", APIPriority.P1),
    "/api/v1/booking_flow": APIMetadata("booking_flow"),
    "/api/v1/bms_order": APIMetadata("breast_milk_shipping"),
    "/api/v1/availability_request": APIMetadata("booking_flow"),
    "/api/v1/availability_notification_request": APIMetadata("booking_flow"),
    "/api/v1/assets/(.+?)/url": APIMetadata("assets", APIPriority.P3),
    "/api/v1/assets/(.+?)/upload": APIMetadata("assets", APIPriority.P3),
    "/api/v1/assets/(.+?)/thumbnail": APIMetadata("assets", APIPriority.P3),
    "/api/v1/assets/(.+?)/download": APIMetadata("assets", APIPriority.P3),
    "/api/v1/assets/(.+?)": APIMetadata("assets", APIPriority.P3),
    "/api/v1/assets": APIMetadata("assets"),
    "/api/v1/assessments/(.+?)": APIMetadata("assessments"),
    "/api/v1/assessments": APIMetadata("assessments"),
    "/api/v1/appointments/(.+?)/reschedule": APIMetadata("appointments"),
    "/api/v1/appointments/(.+?)/notes": APIMetadata(
        "clinical_documentation",
        APIPriority.P1,
        ["video_appointment", "care_advocate_perps_appt"],
    ),
    "/api/v1/appointments/(.+?)/connection": APIMetadata("video", APIPriority.P1),
    "/api/v1/appointments/(.+?)": APIMetadata(
        "appointments",
        APIPriority.P1,
        [
            "member_books_video_appointment",
            "video_appointment",
            "care_advocate_perps_appt",
        ],
    ),
    "/api/v1/appointments": APIMetadata(
        "appointments",
        APIPriority.P1,
        [
            "onboarding",
            "member_accesses_homepage",
            "member_books_video_appointment",
            "video_appointment",
            "care_advocate_perps_appt",
        ],
    ),
    "/api/v1/api_key": APIMetadata("authentication"),
    "/api/v1/agreements/pending": APIMetadata("agreements"),
    "/api/v1/advocate-assignment/reassign/(.+?)": APIMetadata(
        "care_advocate_member_matching"
    ),
    "/api/v1/_/vertical_groupings": APIMetadata("booking_flow"),
    "/api/v1/_/vendor/zoom/webhook": APIMetadata("video", APIPriority.P2),
    "/api/v1/_/vendor/zendesksc/deflection/upcoming_appointments": APIMetadata(
        "messaging_system"
    ),
    "/api/v1/_/vendor/zendesksc/deflection/track_categories": APIMetadata(
        "messaging_system"
    ),
    "/api/v1/_/vendor/zendesksc/deflection/resource_search": APIMetadata(
        "messaging_system"
    ),
    "/api/v1/_/vendor/zendesksc/deflection/provider_search": APIMetadata(
        "messaging_system"
    ),
    "/api/v1/_/vendor/zendesksc/deflection/member_context": APIMetadata(
        "messaging_system"
    ),
    "/api/v1/_/vendor/zendesksc/deflection/category_needs": APIMetadata(
        "messaging_system"
    ),
    "/api/v1/_/vendor/zendesksc/deflection/cancel_appointment": APIMetadata(
        "messaging_system"
    ),
    "/api/v1/_/report_eligibility_verification_failure": APIMetadata("eligibility"),
    "/api/v1/_/password_strength_score": APIMetadata("login"),
    "/api/v1/_/metadata/vendor": APIMetadata("core_services"),
    "/api/v1/_/metadata": APIMetadata(
        "core_services", APIPriority.NONE, ["register_and_confirm_eligibility"]
    ),
    "/api/v1/_/manual_census_verification": APIMetadata("eligibility"),
    "/api/v1/_/geography/(.+?)": APIMetadata("member_profile"),
    "/api/v1/_/geography": APIMetadata("member_profile"),
    "/api/v1/_/agreements/(.+?)": APIMetadata("agreements", APIPriority.P3),
    "/api/v1/_/agreements": APIMetadata("agreements", APIPriority.P3),
    "/api/v1/-/wqs/wallet/(.+?)": APIMetadata("benefits_experience"),
    "/api/v1/-/wqs/wallet": APIMetadata("benefits_experience"),
    "/api/v1/-/wqs/reimbursement_org_setting_name/(.+?)": APIMetadata(
        "benefits_experience"
    ),
    "/api/v1/-/wqs/reimbursement_org": APIMetadata("benefits_experience"),
    "/api/v1/-/wallet_historical_spend/process_file": APIMetadata(
        "benefits_experience"
    ),
    "/api/v1/-/users/sync_user_data": APIMetadata("authentication"),
    "/api/v1/-/users/post_signup_steps": APIMetadata("authentication"),
    "/api/v1/-/users/get_org_id/(.+?)": APIMetadata("authentication"),
    "/api/v1/-/users/get_identities/(.+?)": APIMetadata("authentication"),
    "/api/v1/-/tracks/(.+?)": APIMetadata("tracks"),
    "/api/v1/-/sms": APIMetadata("messaging_system"),
    "/api/v1/-/search/content/(.+?)": APIMetadata("content"),
    "/api/v1/-/reimbursement_wallet/application/user_info": APIMetadata(
        "benefits_experience"
    ),
    "/api/v1/-/personalization/cohorts": APIMetadata("dashboard_metadata"),
    "/api/v1/-/library/videos": APIMetadata(
        "learn", APIPriority.P3, ["member_accesses_learn"]
    ),
    "/api/v1/-/health_profile_backfill": APIMetadata("mpractice_core"),
    "/api/v1/-/care_plans/activities_completed": APIMetadata("care_management"),
    "/api/v1/-/authn_migration/upsert_authn_data": APIMetadata("authentication"),
    "/api/v1/-/authn_migration/retrieve_authn_data/(.+?)": APIMetadata(
        "authentication"
    ),
    "/Join/(.+?)": APIMetadata("enrollments"),
}
endpoint_service_ns_mapper = {
    **admin_endpoint_service_ns_mapper,
    **api_endpoint_service_ns_mapper,
}

# Data admin "maker" classes are owned separately from the data-admin endpoints.
# The FixtureDataMaker temporarily overrides team_ns tags to make this clear in logging
data_admin_maker_ns_mapper = {
    "user": "authentication",
    "organization": "enrollments",
    "organization_employee": "eligibility",
    "organization_employee_dependent": "eligibility",
    "organization_external_id": "eligibility",
    "organization_module_extension": "tracks",
    "reimbursement_organization_settings": "wallet",
    "reimbursement_request": "wallet",
    "reimbursement_wallet": "wallet",
    "reimbursement_category": "wallet",
    "reimbursement_wallet_hdhp_plan": "direct_payment",
    "country_currency_code": "wallet",
    "role": "authentication",
    "treatment_procedure": "treatment_procedure",
    "member_bill": "billing",
    "fee_schedule": "direct_payment",
    "recorded_answer_set": "health",
    "questionnaire": "health",
    "question_set": "health",
    "question": "health",
    "answer": "health",
    "fertility_clinic": "clinic_portal",
    "fertility_clinic_location": "clinic_portal",
    "fertility_clinic_allowed_domain": "clinic_portal",
    "fertility_clinic_user_profile": "clinic_portal",
    "text_copy": "messaging_system",
    "popular_topic": "learn",
    "schedule_event": "appointments",
    "appointment": "appointments",
    "pooled_calendar_max": "care_advocate_load_balancing",
    "pooled_calendar_min": "care_advocate_load_balancing",
    "cas_with_availability": "care_advocate_load_balancing",
    "forum_post": "community_forum",
    "invoice": "provider_payments",
    "fee_accounting_entry": "provider_payments",
    "message": "messaging_system",
    "ca_member_transition_template": "care_advocate_member_matching",
    "ca_members": "care_advocate_member_matching",
    "practitioner_track_vgc": "care_advocate_member_matching",
    "track_change_reason": "tracks",
    "employer_health_plan": "wallet",
    "member_health_plan": "wallet",
    "cost_breakdown": "direct-payment",
    "payer": "direct-payment",
    "accumulation_mapping": "direct-payment",
    "accumulation_report": "direct-payment",
}

# make sure use underscore symbol to connect the words in the team names
service_ns_team_mapper = {
    "account_settings": "enrollments",
    "admin_care_advocate_member_transitions": "care_discovery",
    "agreements": "enrollments",
    "appointment_notifications": "virtual_care",
    "appointments": "care_discovery",
    "assessments": "care_management",
    "assets": "virtual_care",
    "authentication": "core_services",
    "authz": "core_services",
    "billing": "benefits_experience",
    "booking_flow": "care_discovery",
    "braze": "enrollments",
    "breast_milk_shipping": "payments_platform",
    "care_advocate_load_balancing": "care_discovery",
    "care_advocate_member_matching": "care_discovery",
    "care_team": "care_discovery",
    "clinic_management": "benefits_experience",
    "clinic_portal": "benefits_experience",
    "clinical_documentation": "mpractice_core",
    "community_forum": "content_and_community",
    "content_campaigns": "content_and_community",
    "core_services": "core_services",
    "cost_breakdown": "payments_platform",
    "dashboard_metadata": "content_and_community",
    "data-admin": "core_services",
    "direct_payment": "benefits_experience",
    "direct_payment_invoice": "benefits_experience",
    "direct_payment_invoice_report": "benefits_experience",
    "direct_payment_invoicing_setting": "benefits_experience",
    "eligibility": "eligibility",
    "eligibility_admin": "eligibility",
    "enrollments": "enrollments",
    "feature_flags": "engineering_experience",
    "gdpr_deletion": "core_services",
    "global_search": "ai_platform",
    "health": "mpractice_core",
    "health_plans": "payments_platform",
    "incentive": "care_discovery",
    "invoice": "benefits_experience",
    "learn": "content_and_community",
    "login": "core_services",
    "member_care": "mpractice_core",
    "member_profile": "enrollments",
    "messaging_system": "virtual_care",
    "misc": "core_services",
    "mpractice_appointment": "mpractice_core",
    "mpractice_clinical_documentation": "mpractice_core",
    "mpractice_core_web": "mpractice_core",
    "mpractice_member_search_n_profile": "mpractice_core",
    "onboarding": "enrollments",
    "payer_accumulation": "payments_platform",
    "pharmacy": "payments_platform",
    "phone_support": "virtual_care",
    "practitioner_profile": "care_discovery",
    "practitioner_settings": "mpractice_core",
    "prescriptions": "mpractice_core",
    "provider_availability": "mpractice_core",
    "provider_payments": "payments_platform",
    "tracks": "enrollments",
    "treatment_procedure": "benefits_experience",
    "user_locale": "enrollments",
    "video": "virtual_care",
    "wallet": "benefits_experience",
    "wallet_e9y": "benefits_experience",
    "wallet_payments": "payments_platform",
    "wallet_reporting": "payments_platform",
}


def get_endpoint_owner_info(
    endpoint: str, endpoint_prefix: str = "/api/"
) -> Tuple[str, str, str, List[str]]:
    if endpoint is None:
        return APIMetadata().get_values()

    if endpoint_prefix == "/api/":
        endpoint_service_ns_mapper_subset = api_endpoint_service_ns_mapper
    elif endpoint_prefix == "/admin/":
        endpoint_service_ns_mapper_subset = admin_endpoint_service_ns_mapper
    elif endpoint_prefix == "/data-admin/":
        endpoint_service_ns_mapper_subset = data_admin_endpoint_service_ns_mapper
    else:
        return APIMetadata().get_values()

    matched_endpoint = None
    for target_endpoint in endpoint_service_ns_mapper_subset:
        if re.match(rf"{target_endpoint}$", endpoint):
            matched_endpoint = target_endpoint
            break

    if matched_endpoint is None:
        return APIMetadata().get_values()

    return endpoint_service_ns_mapper_subset[matched_endpoint].get_values()


# this is a helper method for getting service_ns info for customized logs or metrics
def get_owner_tags_from_span(span=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    span = span or ddtrace.tracer.current_root_span()
    if span:
        service_ns = span.get_tag(SERVICE_NS_TAG)
        team_ns = span.get_tag(TEAM_NS_TAG)
        return service_ns, team_ns

    return None, None


def get_user_id_tag_from_span(span=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    span = span or ddtrace.tracer.current_root_span()
    if span:
        user_id = span.get_tag(USER_ID_TAG)
        return user_id

    return None


def get_priority_tag_from_span(span=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    span = span or ddtrace.tracer.current_root_span()
    if span:
        priority = span.get_tag(PRIORITY_TAG)
        return priority

    return None


def get_workflow_tags_from_span(span=None):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    span = span or ddtrace.tracer.current_root_span()
    if span:
        workflows = []
        for workflow in workflow_metadata_list:
            if span.get_tag(workflow) == "yes":
                workflows.append(workflow)
        return workflows
    return None


def inject_tags_info(span):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    inject_service_ns_info(span)
    inject_user_identity_info(span)
    inject_priority(span)
    inject_workflow(span)


def inject_service_ns_info(span):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not span:
        return

    service_ns, team_ns = get_owner_tags_from_span()
    if service_ns:
        span.set_tag(SERVICE_NS_TAG, str(service_ns))

    if team_ns:
        span.set_tag(TEAM_NS_TAG, str(team_ns))


# Inject the user_id tag to the span for easy look up logs. Once the event chain project is complete, it can be removed
def inject_user_identity_info(span):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not span:
        return

    user_id = get_user_id_tag_from_span()
    if user_id:
        span.set_tag(USER_ID_TAG, str(user_id))


def inject_priority(span):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not span:
        return

    priority = get_priority_tag_from_span()
    if priority:
        span.set_tag(PRIORITY_TAG, str(priority))


def inject_workflow(span):  # type: ignore[no-untyped-def] # Function is missing a type annotation
    if not span:
        return

    workflows = get_workflow_tags_from_span()
    if workflows:
        for workflow in workflows:
            span.set_tag(workflow, "yes")
